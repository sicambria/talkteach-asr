"""End-to-end API tests for the TalkTeach job server.

Exercises the whole four-screen flow over HTTP without requiring a GPU or models:
project → analyze a real WAV → sufficiency gate → train (simulation) → status →
export → transcription. The "graceful without ML" check is skipped when
faster-whisper is installed. Uses a throwaway data dir via env.
"""

from __future__ import annotations

import importlib.util
import io
import os
import tempfile
import time
import wave
from pathlib import Path

import numpy as np
import pytest

# faster-whisper present → the transcribe endpoint takes the real path (needs a
# model), so the "graceful without ML" assertion only holds when it's absent.
_FASTER_WHISPER = importlib.util.find_spec("faster_whisper") is not None

# The throwaway data dir is set in conftest.py at import time (before *any* test
# module imports talkteach.config, which caches DATA_ROOT once). Doing it here too
# would only win when this file happens to import config first — see conftest.

from fastapi.testclient import TestClient  # noqa: E402

from talkteach import config  # noqa: E402
from talkteach.app import app  # noqa: E402
from talkteach.data.project import ProjectDB  # noqa: E402


def _good_wav_bytes(seconds: float = 1.5, sr: int = 16000) -> bytes:
    """A clean, healthy-level tone the quality checker should accept."""
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    sig = 0.2 * np.sin(2 * np.pi * 220 * t)
    sig += 0.01 * np.sin(2 * np.pi * 50 * t)  # a touch of texture, not noise
    pcm = (sig * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def test_health():
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200 and r.json()["ok"] is True


def test_create_project():
    with TestClient(app) as client:
        r = client.post("/api/project", json={"name": "Cat words", "language_code": "en"})
        assert r.status_code == 200
        assert isinstance(r.json()["project_id"], int)


def test_preflight_shape():
    with TestClient(app) as client:
        r = client.get("/api/preflight")
        body = r.json()
        assert "results" in body and "can_train" in body and "summary" in body
        assert all({"name", "status", "detail"} <= set(c) for c in body["results"])


def test_analyze_good_wav():
    with TestClient(app) as client:
        files = {"audio": ("good.wav", _good_wav_bytes(), "audio/wav")}
        r = client.post("/api/clips/analyze", files=files)
        body = r.json()
        assert r.status_code == 200
        assert body["checked"] is True
        assert body["ok"] is True, body.get("issues")
        assert body["duration_s"] > 1.0
        assert isinstance(body["clip_id"], int)


def test_analyze_non_wav_degrades_gracefully():
    with TestClient(app) as client:
        files = {"audio": ("voice.webm", b"\x1a\x45\xdf\xa3not-a-wav", "audio/webm")}
        r = client.post("/api/clips/analyze", files=files)
        body = r.json()
        assert r.status_code == 200
        assert body["checked"] is False
        assert body["ok"] is True  # accepted, just not checked


def test_upload_path_traversal_is_contained():
    """A crafted ../ filename must NOT escape the clip dir (security #7)."""
    with TestClient(app) as client:
        evil = "../../../../tmp/pwned.wav"
        files = {"audio": (evil, _good_wav_bytes(0.8), "audio/wav")}
        r = client.post("/api/clips/analyze", files=files)
        assert r.status_code == 200
        clip_id = r.json()["clip_id"]

    clip_dir = (config.DEFAULT_PROJECT_DIR / "clips").resolve()
    with ProjectDB.open(config.DEFAULT_DB_PATH) as db:
        clip = next(c for c in db.list_clips() if c["id"] == clip_id)
    stored = Path(clip["path"]).resolve()
    # The stored file lives strictly inside the clip dir...
    assert clip_dir in stored.parents, stored
    # ...and the attacker-chosen basename was discarded for a generated one.
    assert "pwned" not in stored.name
    assert stored.name.startswith("clip_") and stored.suffix == ".wav"


def test_upload_empty_is_rejected():
    with TestClient(app) as client:
        files = {"audio": ("empty.wav", b"", "audio/wav")}
        r = client.post("/api/clips/analyze", files=files)
        assert r.status_code == 400


def test_upload_non_audio_is_rejected():
    with TestClient(app) as client:
        files = {"audio": ("malware.exe", b"MZ\x90\x00", "application/x-msdownload")}
        r = client.post("/api/clips/analyze", files=files)
        assert r.status_code == 415


def test_upload_too_large_is_rejected(monkeypatch):
    # Shrink the cap so we don't have to send 100 MB.
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 1024)
    with TestClient(app) as client:
        files = {"audio": ("big.wav", _good_wav_bytes(2.0), "audio/wav")}
        r = client.post("/api/clips/analyze", files=files)
        assert r.status_code == 413


def test_full_training_flow():
    with TestClient(app) as client:
        # Fresh gate should block before there's enough good audio.
        before = client.get("/api/sufficiency").json()
        assert before["status"] == "blocked"

        # Seed enough GOOD minutes directly in the DB (40 × 60s = 40 min).
        with ProjectDB.open(config.DEFAULT_DB_PATH) as db:
            for i in range(40):
                db.add_clip(
                    f"/seed/clip_{i}.wav",
                    duration_s=60.0,
                    is_good=True,
                    issues=[],
                    transcript="hello there",
                )

        after = client.get("/api/sufficiency").json()
        assert after["status"] == "ready"
        assert after["fraction"] == 1.0

        # Teach! → a real background (simulated) training run.
        r = client.post("/api/train")
        assert r.status_code == 200, r.text
        run_id = r.json()["run_id"]
        assert "plan" in r.json() and r.json()["plan"]["engine"]

        # Poll to completion.
        final = None
        for _ in range(200):
            final = client.get(f"/api/train/{run_id}").json()
            if final["done"] or final["failed"]:
                break
            time.sleep(0.02)
        assert final is not None and final["done"] is True, final
        assert final["failed"] is False
        assert final["smartness"] is not None and 0.0 <= final["smartness"] <= 1.0

        # Export the taught model.
        e = client.post("/api/export", json={"run_id": run_id, "fmt": "onnx"})
        assert e.status_code == 200
        assert "path" in e.json() and "format" in e.json()


def test_clips_list_and_save_correction():
    with TestClient(app) as client:
        # Add a clip, then list it and correct its transcript (#19).
        files = {"audio": ("good.wav", _good_wav_bytes(), "audio/wav")}
        cid = client.post("/api/clips/analyze", files=files).json()["clip_id"]

        listed = client.get("/api/clips").json()["clips"]
        assert any(c["id"] == cid for c in listed)

        r = client.post(f"/api/clips/{cid}/transcript", json={"text": "hello world"})
        assert r.status_code == 200 and r.json()["transcript"] == "hello world"

        again = client.get("/api/clips").json()["clips"]
        assert next(c for c in again if c["id"] == cid)["transcript"] == "hello world"


def test_save_correction_unknown_clip_404():
    with TestClient(app) as client:
        r = client.post("/api/clips/999999/transcript", json={"text": "x"})
        assert r.status_code == 404


def test_prompts_endpoint_returns_karaoke_sentences():
    with TestClient(app) as client:
        body = client.get("/api/prompts", params={"lang": "en", "n": 3}).json()
        assert len(body["prompts"]) == 3
        assert "en" in body["languages"]
        # Unknown language falls back to English, never empty.
        assert client.get("/api/prompts", params={"lang": "zz"}).json()["prompts"]


def test_languages_endpoint_lists_all_supported_languages():
    with TestClient(app) as client:
        body = client.get("/api/languages").json()
        langs = body["languages"]
        # The full Whisper set (~99), each with a code + display name.
        assert len(langs) > 90
        assert body["auto_detect"] is True
        codes = {item["code"] for item in langs}
        assert {"en", "hu", "ja", "ar"} <= codes
        by_code = {item["code"]: item["name"] for item in langs}
        assert by_code["en"] == "English"
        # Sorted by display name so the picker reads alphabetically.
        names = [item["name"] for item in langs]
        assert names == sorted(names)


def test_plan_preview_has_rationale():
    with TestClient(app) as client:
        body = client.get("/api/plan").json()
        assert body["plan"]["rationale"], "advanced mode needs the why"
        assert "engine" in body["plan"] and "hardware" in body


def test_selftest_seeds_clips_and_unblocks_flow():
    with TestClient(app) as client:
        n = client.post("/api/selftest").json()["seeded"]
        assert n > 0
        assert len(client.get("/api/clips").json()["clips"]) >= n


def test_runs_endpoint_lists_status():
    with TestClient(app) as client:
        body = client.get("/api/runs").json()
        assert "runs" in body and isinstance(body["runs"], list)
        # Each run row has the fields the resume UI needs.
        for r in body["runs"]:
            assert {"id", "status", "engine"} <= set(r)


def test_help_bundle_is_a_zip():
    import io as _io
    import zipfile as _zip

    with TestClient(app) as client:
        r = client.get("/api/help-bundle")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"
        # It's a real, openable zip containing the system report.
        with _zip.ZipFile(_io.BytesIO(r.content)) as zf:
            assert "report.json" in zf.namelist()


def test_export_dry_run_for_unknown_run_is_404():
    with TestClient(app) as client:
        r = client.post("/api/export", json={"run_id": 999999, "fmt": "ctranslate2"})
        assert r.status_code == 404


def test_train_blocked_without_data():
    # NOTE: this reloads `config`/`app` in place, mutating shared module state.
    # It must run AFTER the seeded-data tests above (relies on file definition
    # order). If a future reorder breaks the seeded tests, this is the cause.
    # A separate clean data dir so the gate is genuinely empty.
    import importlib

    os.environ["TALKTEACH_DATA"] = tempfile.mkdtemp(prefix="talkteach-empty-")
    importlib.reload(config)
    import talkteach.app as appmod

    importlib.reload(appmod)
    with TestClient(appmod.app) as client:
        r = client.post("/api/train")
        assert r.status_code == 409  # gate refuses; friendly message


@pytest.mark.skipif(
    _FASTER_WHISPER,
    reason="faster-whisper installed; the endpoint takes the real (model-requiring) path",
)
def test_transcribe_graceful_without_ml():
    with TestClient(app) as client:
        files = {"audio": ("try.wav", _good_wav_bytes(0.6), "audio/wav")}
        r = client.post("/api/transcribe", files=files)
        body = r.json()
        assert r.status_code == 200
        assert body["available"] is False  # no faster-whisper installed
        assert body["text"] == ""
        assert "message" in body


# --- benchmark "Arena" --------------------------------------------------------


def _poll_benchmark(client, bench_id, tries=300):
    final = None
    for _ in range(tries):
        final = client.get(f"/api/benchmark/{bench_id}").json()
        if final["done"]:
            break
        time.sleep(0.02)
    return final


def test_benchmark_options_lists_providers_and_engines():
    with TestClient(app) as client:
        opts = client.get("/api/benchmark/options").json()
        assert {t["provider"] for t in opts["tts"]} >= {"espeak", "piper"}
        assert {e["name"] for e in opts["engines"]} >= {"whisper", "wav2vec2"}
        # Every entry carries an availability flag so the picker can disable it.
        assert all("available" in e and "detail" in e for e in opts["engines"])
        assert all("available" in t for t in opts["tts"])
        # Languages we have real prompts for, incl. Hungarian, with a default.
        codes = {lang["code"] for lang in opts["languages"]}
        assert {"en", "hu"} <= codes
        assert opts["default_language"] in codes or opts["default_language"] == "en"


def test_benchmark_podium_with_medals(monkeypatch):
    """Drive the endpoint with a fake runner so we can assert the medal podium
    without downloading models — exercises on_cell streaming + payload medals."""
    import talkteach.app as appmod
    from talkteach.benchmark import BenchmarkReport, CellResult

    def fake_run(cfg, workdir, *, on_cell=None, should_stop=None):
        prompts = ["alpha one", "beta two"]
        cells = [
            CellResult(
                "piper",
                "whisper",
                "ok",
                voice="v",
                wer=0.1,
                cer=0.02,
                smartness=0.9,
                train_seconds=5.0,
                eval_clips=2,
                base_wer=0.5,
                delta_wer=0.4,
                per_clip_wer=[0.0, 0.2],
            ),
            CellResult(
                "piper",
                "wav2vec2",
                "ok",
                voice="v",
                wer=0.4,
                cer=0.1,
                smartness=0.6,
                train_seconds=3.0,
                eval_clips=2,
                base_wer=0.5,
                delta_wer=0.1,
                per_clip_wer=[0.3, 0.5],
            ),
        ]
        for c in cells:
            if on_cell:
                on_cell(c)
        return BenchmarkReport("arena", "en", 2, 2, cells=cells, eval_prompts=prompts)

    monkeypatch.setattr(appmod, "run_benchmark", fake_run)
    with TestClient(appmod.app) as client:
        bench_id = client.post("/api/benchmark", json={}).json()["benchmark_id"]
        final = _poll_benchmark(client, bench_id)
        assert final["done"] and not final["failed"], final
        board = final["report"]["scoreboard"]
        assert board[0]["engine"] == "whisper" and board[0]["medal"] == "gold"
        assert board[1]["engine"] == "wav2vec2" and board[1]["medal"] == "silver"
        assert final["report"]["head_to_head"]["whisper"]["wav2vec2"] == 2


def test_benchmark_cancel_and_unknown_404(monkeypatch):
    import talkteach.app as appmod
    from talkteach.benchmark import BenchmarkReport

    # A cooperative fake that runs until cancelled, so cancel actually transitions
    # the job (and no real model work spawns in the background daemon thread).
    def blocking_run(cfg, workdir, *, on_cell=None, should_stop=None):
        for _ in range(500):
            if should_stop and should_stop():
                break
            time.sleep(0.01)
        return BenchmarkReport("arena", "en", 0, 0)

    monkeypatch.setattr(appmod, "run_benchmark", blocking_run)
    with TestClient(appmod.app) as client:
        bench_id = client.post("/api/benchmark", json={}).json()["benchmark_id"]
        assert client.post(f"/api/benchmark/{bench_id}/cancel").json()["cancelled"] is True
        final = _poll_benchmark(client, bench_id)
        assert final["status"] == "cancelled", final
        assert client.get("/api/benchmark/does-not-exist").status_code == 404
        assert client.post("/api/benchmark/does-not-exist/cancel").status_code == 404


# --- Advanced-mode surfacing: export formats, metrics, captions (#57/#53/#48) ---


def test_export_formats_lists_real_and_scaffold():
    with TestClient(app) as client:
        r = client.get("/api/export/formats")
        assert r.status_code == 200
        body = r.json()
        assert body["default"] == "ctranslate2"
        fmts = {f["fmt"]: f for f in body["formats"]}
        assert fmts["ctranslate2"]["real"] is True  # ctranslate2 installed in CI venv
        assert fmts["torchscript"]["scaffold"] is True
        assert fmts["torchscript"]["real"] is False


def test_metrics_unknown_run_is_404():
    with TestClient(app) as client:
        r = client.get("/api/metrics/999999")
        assert r.status_code == 404


def test_metrics_reads_real_curve():
    from talkteach.obs import experiment

    with TestClient(app) as client:
        client.post("/api/project", json={"name": "metrics-proj"})
        with ProjectDB.open(config.DEFAULT_DB_PATH) as db:
            run_id = db.create_run(
                engine="whisper_lora", base_checkpoint="openai/whisper-tiny", plan_json="{}"
            )
        workdir = config.DEFAULT_PROJECT_DIR / "runs" / str(run_id)
        workdir.mkdir(parents=True, exist_ok=True)
        experiment.log_metrics(str(workdir), epoch=1, loss=1.2, wer=0.5)
        experiment.log_metrics(str(workdir), epoch=2, loss=0.8, wer=0.3)
        r = client.get(f"/api/metrics/{run_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["has_curve"] is True
        assert len(body["curve"]) == 2
        assert body["curve"][-1]["wer"] == 0.3


def test_transcribe_returns_captions(monkeypatch):
    import talkteach.app as appmod

    segs = [
        {"start": 0.0, "end": 1.0, "text": "hello"},
        {"start": 1.0, "end": 2.0, "text": "world"},
    ]

    class _FakeEngine:
        def transcribe_segments(self, path, options=None):
            return segs

    monkeypatch.setattr(appmod, "get_engine", lambda kind: _FakeEngine())
    with TestClient(app) as client:
        files = {"audio": ("try.wav", _good_wav_bytes(0.6), "audio/wav")}
        r = client.post("/api/transcribe", files=files)
        assert r.status_code == 200
        body = r.json()
        assert body["available"] is True
        assert body["segments"] == segs
        assert "hello" in body["text"] and "world" in body["text"]
        assert "-->" in body["srt"]
        assert body["vtt"].startswith("WEBVTT")


def test_transcribe_decode_options_build():
    # Advanced controls at defaults → no DecodeOptions (behaviour preserved).
    from talkteach.app import _decode_options

    assert _decode_options(5, "", None) is None
    opts = _decode_options(3, "cat, dog", 0.4)
    assert opts is not None
    assert opts.beam_size == 3
    assert opts.hotwords == ("cat", "dog")
    assert opts.temperature == (0.4,)


# --- Accuracy / "where it struggles" report (#52) ---


def test_eval_report_unknown_run_404():
    with TestClient(app) as client:
        r = client.get("/api/eval/999999")
        assert r.status_code == 404


def test_eval_report_shapes(monkeypatch):
    import talkteach.app as appmod

    class _FakeEngine:
        def transcribe(self, path, model_dir=None, base_checkpoint=None, options=None):
            return "the cat sat"

    monkeypatch.setattr(appmod, "get_engine", lambda kind: _FakeEngine())
    with TestClient(app) as client:
        client.post("/api/project", json={"name": "eval-proj"})
        with ProjectDB.open(config.DEFAULT_DB_PATH) as db:
            db.add_clip("a.wav", 1.0, True, [], transcript="the cat sat")
            db.add_clip("b.wav", 1.0, True, [], transcript="the dog ran")
            run_id = db.create_run(engine="whisper_lora", base_checkpoint="x", plan_json="{}")
            db.update_run(run_id, best_val_wer=0.25)
        r = client.get(f"/api/eval/{run_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["available"] is True
        assert body["n_clips"] == 2
        assert body["best_val_wer"] == 0.25
        assert "top_substitutions" in body["report"]
        assert body["hardest"][0]["reference"] == "the dog ran"  # the harder clip ranks first
        assert body["simulated"] is True  # no metrics.jsonl ⇒ best_val_wer is synthetic


def test_eval_report_skips_unreadable_clip(monkeypatch):
    import talkteach.app as appmod

    class _FlakyEngine:
        def transcribe(self, path, model_dir=None, base_checkpoint=None, options=None):
            if "bad" in path:
                raise RuntimeError("Format not recognised")  # not EngineUnavailableError
            return "the cat sat"

    monkeypatch.setattr(appmod, "get_engine", lambda kind: _FlakyEngine())
    with TestClient(app) as client:
        client.post("/api/project", json={"name": "eval-skip"})
        with ProjectDB.open(config.DEFAULT_DB_PATH) as db:
            db.add_clip("good.wav", 1.0, True, [], transcript="the cat sat")
            db.add_clip("bad.webm", 1.0, True, [], transcript="the dog ran")
            run_id = db.create_run(engine="whisper_lora", base_checkpoint="x", plan_json="{}")
        r = client.get(f"/api/eval/{run_id}")
        assert r.status_code == 200  # one bad clip must not 500 the whole report
        body = r.json()
        assert body["available"] is True
        assert len(body["issues"]) >= 1  # the undecodable clip(s) skipped + noted
        assert body["n_evaluated"] == body["n_clips"] - len(body["issues"])


# --- Dataset import (#47) ---


def test_import_folder_pairs_adds_clips():
    with TestClient(app) as client:
        client.post("/api/project", json={"name": "imp"})
        files = [
            ("files", ("mydata/hello.wav", _good_wav_bytes(0.5), "audio/wav")),
            ("files", ("mydata/hello.txt", b"hello there", "text/plain")),
        ]
        r = client.post("/api/import", files=files)
        assert r.status_code == 200
        assert r.json()["imported"] == 1
        clips = client.get("/api/clips").json()["clips"]
        assert any("hello there" in (c.get("transcript") or "") for c in clips)


def test_import_skips_traversal_filename():
    with TestClient(app) as client:
        client.post("/api/project", json={"name": "imp2"})
        files = [
            ("files", ("../evil.wav", _good_wav_bytes(0.3), "audio/wav")),
            ("files", ("mydata/ok.wav", _good_wav_bytes(0.3), "audio/wav")),
            ("files", ("mydata/ok.txt", b"ok now", "text/plain")),
        ]
        r = client.post("/api/import", files=files)
        assert r.status_code == 200
        assert r.json()["imported"] == 1  # only the safe pair; traversal file dropped
