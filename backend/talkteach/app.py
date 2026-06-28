"""TalkTeach job server (FastAPI) — wires the director, audio, data, engines,
and reliability layers into the 10 endpoints the four-screen wizard calls.

Phase 0 contract: the whole server imports and runs with NO ML deps. Clip
analysis works for PCM WAV via the stdlib `wave` module (no ffmpeg needed);
training runs in the engine's dependency-free simulation; transcription degrades
gracefully (returns `available: false` instead of crashing) until `[ml]` is
installed.
"""

from __future__ import annotations

import dataclasses
import io
import threading
import uuid
import wave
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import config
from .audio.quality import ClipQuality, analyze_samples
from .data.project import ProjectDB
from .director import (
    DataProfile,
    EngineKind,
    build_plan,
    probe_hardware,
    probe_language,
    sufficiency,
)
from .engines import get_engine
from .engines.base import EngineUnavailableError, TrainProgress
from .reliability.preflight import run_preflight


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    config.ensure_dirs()
    from .obs import configure_logging

    configure_logging(config.DEFAULT_PROJECT_DIR)
    with _db() as db:
        if db.get_project() is None:
            db.init_project(name="My project", language_code=None)
        _reconcile_interrupted_runs(db)
    yield


def _reconcile_interrupted_runs(db: ProjectDB) -> int:
    """Job durability (#40): on startup, any run still marked 'running' in the DB
    was orphaned by a previous crash/close (the in-memory job is gone). Mark it
    'interrupted' so the UI can offer to resume — training resumes from the latest
    checkpoint in its workdir (see engines/_whisper_train.find_latest_checkpoint).
    """
    from .obs import get_logger

    stale = [r for r in db.list_runs() if r["status"] == "running"]
    for run in stale:
        db.update_run(run["id"], status="interrupted")
    if stale:
        get_logger("app").info("Reconciled %d interrupted run(s) on startup", len(stale))
    return len(stale)


app = FastAPI(title="TalkTeach", version="0.0.1", lifespan=_lifespan)

# The Tauri shell loads the UI from a local origin; allow it during dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- shared state -------------------------------------------------------------


def _db() -> ProjectDB:
    """Open the single Phase-0 project DB (one connection per call keeps SQLite
    happy across the main thread and background training threads via WAL)."""
    config.ensure_dirs()
    return ProjectDB.open(config.DEFAULT_DB_PATH)


# --- helpers ------------------------------------------------------------------


def _plan_to_dict(plan) -> dict:
    d = asdict(plan)
    d["engine"] = plan.engine.value
    d["compute"] = plan.compute.value
    d["precision"] = plan.precision.value
    d["effective_batch"] = plan.effective_batch
    return d


def _safe_ext(filename: str | None) -> str:
    """Recover a validated lowercase extension (no dot) from a client filename.

    Falls back to ``wav`` for missing/unknown extensions. The result is only ever
    used to build a *server-generated* storage name — never as a path component.
    """
    if not filename:
        return "wav"
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext if ext in config.ALLOWED_AUDIO_EXTENSIONS else "wav"


def _safe_clip_name(filename: str | None) -> str:
    """Generate a collision-free, traversal-proof storage name (security #7).

    A crafted filename like ``../../etc/passwd`` cannot escape the clip dir
    because the client string is discarded entirely; only a validated extension
    survives, appended to a random uuid. See project/docs/DECISIONS.md D-004.
    """
    return f"clip_{uuid.uuid4().hex}.{_safe_ext(filename)}"


async def _read_validated_upload(audio: UploadFile) -> bytes:
    """Read an upload, rejecting empty/oversized/non-audio payloads early (#9).

    Raises HTTP 400 (empty), 413 (too large), or 415 (not an audio type). The
    content-type check is lenient for browser blobs (audio/* and video/webm) but
    blocks obviously-wrong uploads (e.g. an ``application/x-msdownload`` .exe).
    """
    ctype = (audio.content_type or "").lower()
    raw_ext = Path(audio.filename).suffix.lower().lstrip(".") if audio.filename else ""
    # If the client both declares a non-audio content-type AND gives no allowed
    # audio extension, reject before reading the whole body.
    ctype_ok = not ctype or ctype.startswith(config.ALLOWED_AUDIO_CONTENT_PREFIXES)
    ext_ok = raw_ext in config.ALLOWED_AUDIO_EXTENSIONS
    if not ctype_ok and not ext_ok:
        raise HTTPException(
            status_code=415,
            detail="That doesn't look like a sound file. Try a WAV, MP3, or a recording.",
        )

    raw = await audio.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="That recording was empty.")
    if len(raw) > config.MAX_UPLOAD_BYTES:
        mb = config.MAX_UPLOAD_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"That file is too big — the limit is about {mb} MB per clip.",
        )
    return raw


def _decode_wav_bytes(data: bytes) -> tuple[np.ndarray, int] | None:
    """Decode PCM WAV to float32 mono-or-multichannel in [-1, 1], stdlib only.
    Returns None for non-WAV / unsupported payloads (caller degrades gracefully)."""
    try:
        with wave.open(io.BytesIO(data), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            sr = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
    except (wave.Error, EOFError, OSError):
        return None
    dtype: type[np.signedinteger]
    if sampwidth == 2:
        dtype, peak = np.int16, 32768.0
    elif sampwidth == 4:
        dtype, peak = np.int32, 2147483648.0
    elif sampwidth == 1:
        # 8-bit WAV is unsigned.
        arr = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        if n_channels > 1:
            arr = arr.reshape(-1, n_channels)
        return arr, sr
    else:
        return None
    arr = np.frombuffer(frames, dtype=dtype).astype(np.float32) / peak
    if n_channels > 1:
        arr = arr.reshape(-1, n_channels)
    return arr, sr


def _current_data_profile(db: ProjectDB) -> DataProfile:
    clips = db.list_clips()
    good = sum(c["duration_s"] for c in clips if c["is_good"]) / 60.0
    total = sum(c["duration_s"] for c in clips) / 60.0
    return DataProfile(good_minutes=good, total_minutes=total, clip_count=len(clips))


# --- request models -----------------------------------------------------------


class ProjectIn(BaseModel):
    name: str
    language_code: str | None = None


class DraftIn(BaseModel):
    clip_id: int


class TranscriptIn(BaseModel):
    text: str


class ExportIn(BaseModel):
    run_id: int
    fmt: str = "ctranslate2"


# --- endpoints ----------------------------------------------------------------


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "talkteach", "version": app.version}


@app.post("/api/project")
def create_project(body: ProjectIn) -> dict:
    with _db() as db:
        pid = db.init_project(name=body.name, language_code=body.language_code)
    return {"project_id": pid}


@app.get("/api/preflight")
def preflight() -> dict:
    report = run_preflight()
    return {
        "results": [asdict(r) | {"status": r.status.value} for r in report.results],
        "ok": report.ok,
        "can_train": report.can_train,
        "summary": report.summary,
    }


@app.post("/api/clips/analyze")
async def analyze_clip(audio: UploadFile) -> dict:
    """Analyze an uploaded clip, store it, and return the friendly verdict.

    Decodes PCM WAV with the stdlib (no ffmpeg). For other formats it accepts the
    clip but marks quality unknown so the flow never dead-ends."""
    raw = await _read_validated_upload(audio)
    config.ensure_dirs()
    decoded = _decode_wav_bytes(raw)
    clip_dir = config.DEFAULT_PROJECT_DIR / "clips"
    clip_dir.mkdir(parents=True, exist_ok=True)
    # Server-generated name: the client filename is never a path component (#7).
    dest = clip_dir / _safe_clip_name(audio.filename)
    dest.write_bytes(raw)

    if decoded is None:
        # Not a stdlib-readable PCM WAV (e.g. browser webm/opus, mp3, m4a). Try
        # the ffmpeg decoder (#10/#20); if it isn't installed, accept the clip but
        # flag it as not-yet-checked so the flow never dead-ends.
        from .audio.decode import AudioDecodeError, decode_to_samples

        try:
            decoded = decode_to_samples(str(dest))
        except AudioDecodeError:
            with _db() as db:
                cid = db.add_clip(
                    str(dest),
                    duration_s=0.0,
                    is_good=True,
                    issues=["not checked yet (install the audio pack)"],
                )
            return {
                "clip_id": cid,
                "ok": True,
                "checked": False,
                "issues": ["We saved it but couldn't listen to it yet."],
                "duration_s": 0.0,
            }

    samples, sr = decoded
    q: ClipQuality = analyze_samples(samples, sr)
    with _db() as db:
        cid = db.add_clip(str(dest), duration_s=q.duration_s, is_good=q.ok, issues=q.issues)
    out = asdict(q) | {"clip_id": cid, "checked": True, "verdict": q.verdict.value}
    return out


@app.get("/api/sufficiency")
def sufficiency_status() -> dict:
    with _db() as db:
        profile = _current_data_profile(db)
    res = sufficiency(profile, target_minutes=config.TARGET_GOOD_MINUTES)
    return {
        "status": res.status.value,
        "good_minutes": res.good_minutes,
        "target_minutes": res.target_minutes,
        "fraction": res.fraction,
        "messages": res.messages,
    }


@app.get("/api/clips")
def list_clips() -> dict:
    """Screen 2's clip list — every recorded clip with its current transcript (#19)."""
    with _db() as db:
        clips = db.list_clips()
    return {
        "clips": [
            {
                "id": c["id"],
                "duration_s": c["duration_s"],
                "is_good": c["is_good"],
                "issues": c["issues"],
                "transcript": c["transcript"] or "",
            }
            for c in clips
        ]
    }


@app.post("/api/clips/{clip_id}/transcript")
def save_transcript(clip_id: int, body: TranscriptIn) -> dict:
    """Persist a child's corrected transcript for one clip (#19)."""
    with _db() as db:
        if not any(c["id"] == clip_id for c in db.list_clips()):
            raise HTTPException(status_code=404, detail="That recording wasn't found.")
        db.update_transcript(clip_id, body.text)
    return {"ok": True, "clip_id": clip_id, "transcript": body.text}


@app.get("/api/prompts")
def prompts(lang: str | None = None, n: int | None = None) -> dict:
    """Karaoke sentences to read aloud (#21). The prompt is also the transcript."""
    from .prompts import available_languages, get_prompts

    return {"language": lang, "prompts": get_prompts(lang, n), "languages": available_languages()}


@app.get("/api/plan")
def plan_preview() -> dict:
    """The director's plan + plain-language rationale for Grown-up mode (#23).

    Built from the current hardware, recorded data, and language — the same plan
    "Teach!" would use — so a grown-up can see *why* before training starts.
    """
    with _db() as db:
        project = db.get_project() or {}
        profile = _current_data_profile(db)
    hw = probe_hardware(str(config.DEFAULT_PROJECT_DIR))
    lang = probe_language(project.get("language_code"))
    plan = build_plan(hw, profile, lang)
    return {
        "plan": _plan_to_dict(plan),
        "hardware": {
            "compute": hw.compute.value,
            "gpu_name": hw.gpu_name,
            "vram_gib": hw.vram_gib,
            "ram_gib": hw.ram_gib,
        },
    }


@app.post("/api/selftest")
def selftest() -> dict:
    """Seed a tiny toy dataset so 'Teach!' is verifiable on first run (#22)."""
    from .selftest import make_toy_dataset

    project_dir = config.DEFAULT_PROJECT_DIR
    manifest = make_toy_dataset(project_dir / "selftest", language=None)
    with _db() as db:
        for item in manifest:
            db.add_clip(
                item["path"],
                duration_s=item["duration_s"],
                is_good=True,
                issues=[],
                transcript=item["text"],
            )
    return {"seeded": len(manifest), "message": "Added a few practice sounds so you can try Teach!"}


@app.post("/api/transcribe/draft")
def draft_transcript(body: DraftIn) -> dict:
    with _db() as db:
        clips = {c["id"]: c for c in db.list_clips()}
    clip = clips.get(body.clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail="That recording wasn't found.")
    engine = get_engine(EngineKind.WHISPER_LORA)
    try:
        text = engine.transcribe(clip["path"])
    except EngineUnavailableError as e:
        return {"text": "", "available": False, "message": str(e)}
    with _db() as db:
        db.update_transcript(body.clip_id, text)
    return {"text": text, "available": True}


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile) -> dict:
    """The 'Try it' microphone."""
    raw = await _read_validated_upload(audio)
    config.ensure_dirs()
    tmp = config.DEFAULT_PROJECT_DIR / "try.wav"
    tmp.write_bytes(raw)
    engine = get_engine(EngineKind.WHISPER_LORA)
    try:
        text = engine.transcribe(str(tmp))
    except EngineUnavailableError as e:
        return {"text": "", "available": False, "message": str(e)}
    return {"text": text, "available": True}


# --- training jobs ------------------------------------------------------------

_jobs: dict[int, _Job] = {}
_jobs_lock = threading.Lock()


@dataclasses.dataclass
class _Job:
    run_id: int
    progress: TrainProgress
    cancel: threading.Event


def _run_training(run_id: int, plan, manifest: list[dict], workdir: str) -> None:
    cancel = _jobs[run_id].cancel
    # The director may select an engine that's only a Phase-2 scaffold (NeMo /
    # wav2vec2). If it isn't available, fall back to Whisper-LoRA so the flow
    # always completes rather than dead-ending (graceful-degradation contract).
    try:
        engine = get_engine(plan.engine)
        available, _why = engine.is_available()
        if not available and plan.engine != EngineKind.WHISPER_LORA:
            engine = get_engine(EngineKind.WHISPER_LORA)
    except NotImplementedError:
        engine = get_engine(EngineKind.WHISPER_LORA)

    def on_progress(p: TrainProgress) -> None:
        with _jobs_lock:
            _jobs[run_id].progress = p

    db = ProjectDB.open(config.DEFAULT_DB_PATH)
    try:
        db.update_run(run_id, status="running")
        final = engine.train(
            plan,
            manifest,
            workdir,
            progress=on_progress,
            should_stop=cancel.is_set,
        )
        with _jobs_lock:
            _jobs[run_id].progress = final
        if final.failed:
            db.update_run(run_id, status="failed")
        elif cancel.is_set() and not final.done:
            db.update_run(run_id, status="cancelled")
        else:
            wer = None if final.smartness is None else round(1.0 - final.smartness, 4)
            db.update_run(run_id, status="done", best_val_wer=wer, checkpoint_path=workdir)
    except Exception as e:  # never let a training thread die silently
        with _jobs_lock:
            _jobs[run_id].progress = TrainProgress(
                epoch=0,
                total_epochs=plan.epochs,
                fraction=0.0,
                smartness=None,
                message=f"Something went wrong: {e}",
                done=False,
                failed=True,
            )
        db.update_run(run_id, status="failed")
    finally:
        db.close()


@app.post("/api/train")
def start_training() -> dict:
    with _db() as db:
        project = db.get_project() or {}
        profile = _current_data_profile(db)
        gate = sufficiency(profile, target_minutes=config.TARGET_GOOD_MINUTES)
        if gate.status.value != "ready":
            raise HTTPException(
                status_code=409,
                detail=" ".join(gate.messages) or "Add more good recordings first.",
            )
        good_clips = db.list_clips(only_good=True)
        manifest = [{"path": c["path"], "text": c["transcript"] or ""} for c in good_clips]

        hw = probe_hardware(str(config.DEFAULT_PROJECT_DIR))
        lang = probe_language(project.get("language_code"))
        plan = build_plan(hw, profile, lang)
        run_id = db.create_run(
            engine=plan.engine.value,
            base_checkpoint=plan.base_checkpoint,
            plan_json=__import__("json").dumps(_plan_to_dict(plan)),
        )

    workdir = str(config.DEFAULT_PROJECT_DIR / "runs" / str(run_id))
    Path(workdir).mkdir(parents=True, exist_ok=True)
    initial = TrainProgress(
        epoch=0,
        total_epochs=plan.epochs,
        fraction=0.0,
        smartness=None,
        message="Getting ready to teach…",
        done=False,
        failed=False,
    )
    with _jobs_lock:
        _jobs[run_id] = _Job(run_id=run_id, progress=initial, cancel=threading.Event())
    threading.Thread(
        target=_run_training, args=(run_id, plan, manifest, workdir), daemon=True
    ).start()
    return {"run_id": run_id, "plan": _plan_to_dict(plan)}


@app.get("/api/train/{run_id}")
def training_status(run_id: int) -> dict:
    with _jobs_lock:
        job = _jobs.get(run_id)
        if job is not None:
            return asdict(job.progress)
    # Not in memory (e.g. server restarted) — reconstruct from the DB.
    with _db() as db:
        run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="That training run wasn't found.")
    done = run["status"] == "done"
    return {
        "epoch": 0,
        "total_epochs": 0,
        "fraction": 1.0 if done else 0.0,
        "smartness": (1.0 - run["best_val_wer"]) if run.get("best_val_wer") is not None else None,
        "message": f"Status: {run['status']}",
        "done": done,
        "failed": run["status"] == "failed",
    }


@app.post("/api/train/{run_id}/cancel")
def cancel_training(run_id: int) -> dict:
    with _jobs_lock:
        job = _jobs.get(run_id)
    if job is None:
        raise HTTPException(status_code=404, detail="That training run wasn't found.")
    job.cancel.set()
    return {"cancelled": True}


@app.post("/api/export")
def export_model(body: ExportIn) -> dict:
    with _db() as db:
        run = db.get_run(body.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="That model wasn't found.")
    model_dir = run.get("checkpoint_path") or str(
        config.DEFAULT_PROJECT_DIR / "runs" / str(body.run_id)
    )
    out_dir = str(config.DEFAULT_PROJECT_DIR / "exports" / str(body.run_id))
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    engine = get_engine(EngineKind.WHISPER_LORA)
    result = engine.export(model_dir, out_dir, fmt=body.fmt)
    return asdict(result)


@app.get("/api/runs")
def list_runs() -> dict:
    """All training runs with status — lets the UI offer to resume an interrupted
    one (job durability, #40)."""
    with _db() as db:
        runs = db.list_runs()
    return {
        "runs": [
            {
                "id": r["id"],
                "status": r["status"],
                "engine": r["engine"],
                "best_val_wer": r.get("best_val_wer"),
            }
            for r in runs
        ]
    }


@app.get("/api/help-bundle")
def help_bundle() -> Response:
    """Export a local, redacted help bundle (logs + system report) as a zip (#41).

    Nothing is sent anywhere — the grown-up downloads it and shares it
    deliberately (privacy posture, project/docs/DECISIONS.md D-008).
    """
    from .obs.logging import help_bundle_bytes

    data = help_bundle_bytes(config.DEFAULT_PROJECT_DIR)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=talkteach-help-bundle.zip"},
    )


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    main()
