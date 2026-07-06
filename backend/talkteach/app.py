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
import shutil
import threading
import uuid
import wave
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import cast

import numpy as np
from fastapi import FastAPI, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import __version__, config
from .audio.quality import ClipQuality, analyze_samples
from .benchmark import BenchmarkReport, run_benchmark, scoreboard_payload
from .data.project import ProjectDB
from .director import (
    DataProfile,
    EngineKind,
    build_plan,
    probe_hardware,
    probe_language,
    sufficiency,
    supported_languages,
)
from .engines import get_engine
from .engines.base import EngineUnavailableError, TrainProgress
from .obs import experiment
from .reliability.preflight import run_preflight
from .transcript.decode import DecodeOptions
from .transcript.subtitles import Segment, segments_to_srt, segments_to_text, segments_to_vtt
from .tts import available_providers, get_tts_provider


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


app = FastAPI(title="TalkTeach", version=__version__, lifespan=_lifespan)

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


class BenchmarkIn(BaseModel):
    """A request to run the TTS×ASR Arena. ``tts``/``engines`` are spec dicts in the
    same shape ``benchmarks/*.yaml`` use (the subset the user ticked); empty lists
    fall back to the built-in defaults. Clip counts override the defaults too."""

    tts: list[dict] = []
    engines: list[dict] = []
    languages: list[str] = []  # languages to cover; empty → the project/`language`
    language: str | None = None
    train_clips: int | None = None
    eval_clips: int | None = None
    name: str = "arena"


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
    """Persist the user's corrected transcript for one clip (#19)."""
    with _db() as db:
        if not any(c["id"] == clip_id for c in db.list_clips()):
            raise HTTPException(status_code=404, detail="That recording wasn't found.")
        db.update_transcript(clip_id, body.text)
    return {"ok": True, "clip_id": clip_id, "transcript": body.text}


@app.get("/api/languages")
def languages() -> dict:
    """Every speech language the model can be trained for (#36).

    The ~99 Whisper languages (code + English name) that populate the New-Project
    picker. Languages outside this set are still trainable — the director switches
    the base model to wav2vec2/XLS-R — and `auto_detect` (no language chosen) lets
    Whisper identify it. See director/language.py and project/docs/LANGUAGES.md.
    """
    return {"languages": supported_languages(), "auto_detect": True}


@app.get("/api/prompts")
def prompts(lang: str | None = None, n: int | None = None) -> dict:
    """Karaoke sentences to read aloud (#21). The prompt is also the transcript."""
    from .prompts import available_languages, get_prompts

    return {"language": lang, "prompts": get_prompts(lang, n), "languages": available_languages()}


@app.get("/api/plan")
def plan_preview() -> dict:
    """The director's plan + plain-language rationale for Advanced mode (#23).

    Built from the current hardware, recorded data, and language — the same plan
    "Teach!" would use — so the user can see *why* before training starts.
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


def _decode_options(
    beam_size: int, hotwords: str, temperature: float | None
) -> DecodeOptions | None:
    """Build a :class:`DecodeOptions` from Advanced-mode controls (#50), or ``None``
    when everything is left at defaults so the decode behaves exactly as before."""
    words = tuple(w for w in (hotwords or "").replace(",", " ").split() if w)
    if beam_size == 5 and not words and temperature is None:
        return None
    kwargs: dict = {"beam_size": max(1, beam_size)}
    if words:
        kwargs["hotwords"] = words
    if temperature is not None:
        kwargs["temperature"] = (max(0.0, temperature),)
    return DecodeOptions(**kwargs)


@app.post("/api/transcribe")
async def transcribe(
    audio: UploadFile,
    beam_size: int = Form(5),
    hotwords: str = Form(""),
    temperature: float | None = Form(None),
) -> dict:
    """The 'Try it' microphone.

    Returns the recognised ``text`` plus timestamped ``segments`` and ready-to-save
    ``srt``/``vtt`` caption strings (#48), formatted server-side by the tested
    :mod:`talkteach.transcript.subtitles`. Optional Advanced-mode decode controls
    (``beam_size``/``hotwords``/``temperature``, #50) tune faster-whisper; omitted →
    today's defaults.
    """
    raw = await _read_validated_upload(audio)
    config.ensure_dirs()
    tmp = config.DEFAULT_PROJECT_DIR / "try.wav"
    tmp.write_bytes(raw)
    engine = get_engine(EngineKind.WHISPER_LORA)
    options = _decode_options(beam_size, hotwords, temperature)
    try:
        segments = cast("list[Segment]", engine.transcribe_segments(str(tmp), options=options))
    except EngineUnavailableError as e:
        return {
            "text": "",
            "available": False,
            "message": str(e),
            "segments": [],
            "srt": "",
            "vtt": "",
        }
    return {
        "text": segments_to_text(segments),
        "available": True,
        "segments": segments,
        "srt": segments_to_srt(segments),
        "vtt": segments_to_vtt(segments),
    }


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


# Export targets the picker offers (#57). ``dep`` is the import that makes the
# target real on this machine; ``scaffold`` marks honest dry-run-only formats
# (Whisper's `.generate()` resists torch.jit, so torchscript/gguf stay scaffolds).
_EXPORT_FORMATS: list[dict] = [
    {
        "fmt": "ctranslate2",
        "label": "CTranslate2 (fast offline CPU)",
        "dep": "ctranslate2",
        "scaffold": False,
    },
    {
        "fmt": "safetensors",
        "label": "HF safetensors (Transformers interop)",
        "dep": "transformers",
        "scaffold": False,
    },
    {"fmt": "onnx", "label": "ONNX (sherpa / edge)", "dep": "optimum", "scaffold": False},
    {"fmt": "torchscript", "label": "TorchScript (scaffold)", "dep": None, "scaffold": True},
    {"fmt": "gguf", "label": "GGUF / whisper.cpp (scaffold)", "dep": None, "scaffold": True},
]


@app.get("/api/export/formats")
def export_formats() -> dict:
    """The export targets the Advanced-mode picker shows, each flagged ``real`` when
    its converter is importable here vs an honest ``scaffold`` dry-run (#57)."""
    import importlib.util as _u

    out = []
    for f in _EXPORT_FORMATS:
        real = (not f["scaffold"]) and (f["dep"] is None or _u.find_spec(f["dep"]) is not None)
        out.append({"fmt": f["fmt"], "label": f["label"], "real": real, "scaffold": f["scaffold"]})
    return {"formats": out, "default": "ctranslate2"}


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


@app.get("/api/metrics/{run_id}")
def run_metrics(run_id: int) -> dict:
    """Local loss/WER curve for Advanced mode (#53). Reads the append-only
    ``metrics.jsonl`` the *real* trainer writes (D-008, no telemetry); a run with no
    curve was simulated or hasn't logged yet, so ``has_curve`` lets the UI say so
    honestly rather than draw synthetic numbers. ``best_val_wer`` is the held-out
    figure the smartness meter already uses."""
    with _db() as db:
        run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="That run wasn't found.")
    workdir = run.get("checkpoint_path") or str(config.DEFAULT_PROJECT_DIR / "runs" / str(run_id))
    curve = experiment.read_curve(workdir)
    return {
        "run_id": run_id,
        "status": run.get("status"),
        "best_val_wer": run.get("best_val_wer"),
        "curve": curve,
        "has_curve": bool(curve),
    }


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


# --- benchmark "Arena" jobs ---------------------------------------------------
#
# An advanced tool that runs the full TTS×ASR matrix and ranks the engines on an ELO
# podium (see talkteach.benchmark). It mirrors the training-job pattern above, but
# benchmarks are transient comparisons, so the registry is in-memory only (keyed by
# a UUID) — no SQLite run row and no startup reconciliation. Lazy/partial results
# stream as each cell completes; cross-thread access is guarded by _bench_lock.

# Always award a 3-deep podium (🥇🥈🥉); ties share a medal (assign_medals).
_BENCH_MEDALS = 3

# Built-in defaults (lifted from benchmarks/quick.yaml) so a minimal request runs.
_BENCH_DEFAULT_TTS: list[dict] = [
    {"provider": "espeak", "voice": "en"},
    {"provider": "piper", "voice": "en_US-lessac-low"},
]
# The interactive Arena offers a quick, CPU-runnable set (both in the `small`
# fairness bracket). The full small/medium/large matrix lives in benchmarks/full.yaml
# for a CLI run on a provisioned box — see project/docs/BENCHMARKING.md.
_BENCH_ENGINE_CATALOG: list[dict] = [
    {
        "name": "whisper",
        "label": "Whisper (LoRA)",
        "category": "small",
        "plan": {
            "engine": "whisper_lora",
            "base_checkpoint": "openai/whisper-tiny",
            "compute": "cpu",
            "precision": "fp32",
            "epochs": 1,
            "batch_size": 2,
            "learning_rate": 0.001,
            "lora_rank": 4,
            "freeze_encoder": True,
        },
    },
    {
        "name": "wav2vec2",
        "label": "wav2vec2 (CTC)",
        "category": "small",
        "plan": {
            "engine": "wav2vec2_ctc",
            "base_checkpoint": "facebook/wav2vec2-base-960h",
            "compute": "cpu",
            "precision": "fp32",
            "epochs": 1,
            "batch_size": 2,
            "learning_rate": 0.0001,
        },
    },
]

_bench_jobs: dict[str, _BenchJob] = {}
_bench_lock = threading.Lock()


@dataclasses.dataclass
class _BenchJob:
    id: str
    status: str  # "running" | "done" | "failed" | "cancelled"
    report: BenchmarkReport
    message: str
    medals: int
    cancel: threading.Event
    error: str | None = None


def _run_benchmark_job(job_id: str, cfg: dict, workdir: str) -> None:
    job = _bench_jobs[job_id]

    def on_cell(cell) -> None:
        # Stream partial progress: append under the lock the poll endpoint also
        # holds, so a concurrent read never sees a half-mutated cell list.
        with _bench_lock:
            job.report.cells.append(cell)
            job.message = f"Scored {len(job.report.cells)} combination(s)…"

    try:
        final = run_benchmark(cfg, workdir, on_cell=on_cell, should_stop=job.cancel.is_set)
        with _bench_lock:
            cancelled = job.cancel.is_set()
            job.report = final  # the full report carries eval_prompts + every cell
            job.status = "cancelled" if cancelled else "done"
            job.message = "Stopped." if cancelled else "Done — here are the results."
    except Exception as e:  # never let the thread die silently
        with _bench_lock:
            job.status = "failed"
            job.error = str(e)
            job.message = f"Something went wrong: {e}"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _engine_available(plan_cfg: dict) -> tuple[bool, str]:
    """Best-effort availability for an engine spec (so the picker can grey it out)."""
    from .director.plan_config import plan_from_config

    try:
        engine = get_engine(plan_from_config(plan_cfg).engine)
    except (KeyError, NotImplementedError) as exc:
        return False, str(exc)
    return engine.is_available()


# Display names for the languages we ship real prompt sets for (the only ones the
# Arena offers, so every contest reads sentences written in that language).
_LANG_NAMES = {
    "en": "English",
    "es": "Spanish",
    "de": "German",
    "hu": "Hungarian",
    "fr": "French",
    "it": "Italian",
}


@app.get("/api/benchmark/options")
def benchmark_options() -> dict:
    """What the Arena picker offers: TTS providers, ASR engines, and the languages we
    have real prompts for — each with an ``available`` flag so missing deps show
    disabled. ``default_language`` is the project's language, pre-selected if covered."""
    from .prompts import available_languages

    tts = []
    for name in available_providers():
        try:
            ok, msg = get_tts_provider(name).is_available()
        except Exception as exc:  # noqa: BLE001 - a bad provider shouldn't 500 the picker
            ok, msg = False, str(exc)
        default_voice = next(
            (t.get("voice") for t in _BENCH_DEFAULT_TTS if t["provider"] == name), None
        )
        tts.append({"provider": name, "available": ok, "detail": msg, "voice": default_voice})

    engines = []
    for spec in _BENCH_ENGINE_CATALOG:
        ok, msg = _engine_available(spec["plan"])
        engines.append(
            {
                "name": spec["name"],
                "label": spec["label"],
                "category": spec.get("category", "default"),
                "plan": spec["plan"],
                "available": ok,
                "detail": msg,
            }
        )

    languages = [{"code": c, "name": _LANG_NAMES.get(c, c)} for c in available_languages()]
    with _db() as db:
        proj = db.get_project() or {}
    default_language = proj.get("language_code") or "en"

    return {
        "tts": tts,
        "engines": engines,
        "languages": languages,
        "default_language": default_language,
        "defaults": {"train_clips": 6, "eval_clips": 6},
    }


@app.post("/api/benchmark")
def start_benchmark(body: BenchmarkIn) -> dict:
    """Kick off a full TTS×ASR matrix run in the background; returns its id to poll."""
    project = {}
    with _db() as db:
        project = db.get_project() or {}
    language = body.language or project.get("language_code") or "en"
    languages = body.languages or [language]
    cfg: dict = {
        "name": body.name,
        "language": language,
        "languages": languages,
        "tts": body.tts or _BENCH_DEFAULT_TTS,
        "engines": body.engines
        or [
            {"name": s["name"], "category": s.get("category", "default"), "plan": s["plan"]}
            for s in _BENCH_ENGINE_CATALOG
        ],
        "medals": _BENCH_MEDALS,
    }
    if body.train_clips is not None:
        cfg["train_clips"] = body.train_clips
    if body.eval_clips is not None:
        cfg["eval_clips"] = body.eval_clips

    bench_id = uuid.uuid4().hex
    workdir = str(config.DEFAULT_PROJECT_DIR / "benchmarks" / bench_id)
    Path(workdir).mkdir(parents=True, exist_ok=True)
    job = _BenchJob(
        id=bench_id,
        status="running",
        report=BenchmarkReport(name=body.name, language=language, train_clips=0, eval_clips=0),
        message="Getting the contest ready…",
        medals=_BENCH_MEDALS,
        cancel=threading.Event(),
    )
    with _bench_lock:
        _bench_jobs[bench_id] = job
    threading.Thread(target=_run_benchmark_job, args=(bench_id, cfg, workdir), daemon=True).start()
    return {"benchmark_id": bench_id}


@app.get("/api/benchmark/{bench_id}")
def benchmark_status(bench_id: str) -> dict:
    with _bench_lock:
        job = _bench_jobs.get(bench_id)
        if job is None:
            raise HTTPException(status_code=404, detail="That benchmark wasn't found.")
        # Snapshot the cell list under the lock so the (possibly long) ELO/payload
        # computation below runs on a stable matrix while on_cell keeps appending.
        snapshot = dataclasses.replace(job.report, cells=list(job.report.cells))
        status, message, medals = job.status, job.message, job.medals
    return {
        "status": status,
        "message": message,
        "done": status in ("done", "cancelled", "failed"),
        "failed": status == "failed",
        "report": scoreboard_payload(snapshot, medals=medals),
    }


@app.post("/api/benchmark/{bench_id}/cancel")
def cancel_benchmark(bench_id: str) -> dict:
    with _bench_lock:
        job = _bench_jobs.get(bench_id)
    if job is None:
        raise HTTPException(status_code=404, detail="That benchmark wasn't found.")
    job.cancel.set()
    return {"cancelled": True}


@app.get("/api/help-bundle")
def help_bundle() -> Response:
    """Export a local, redacted help bundle (logs + system report) as a zip (#41).

    Nothing is sent anywhere — the user downloads it and shares it
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
