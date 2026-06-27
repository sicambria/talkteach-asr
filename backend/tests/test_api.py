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

import numpy as np
import pytest

# faster-whisper present → the transcribe endpoint takes the real path (needs a
# model), so the "graceful without ML" assertion only holds when it's absent.
_FASTER_WHISPER = importlib.util.find_spec("faster_whisper") is not None

# Point the backend at a throwaway data dir BEFORE importing the app/config.
os.environ["TALKTEACH_DATA"] = tempfile.mkdtemp(prefix="talkteach-test-")

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


def test_full_training_flow():
    with TestClient(app) as client:
        # Fresh gate should block before there's enough good audio.
        before = client.get("/api/sufficiency").json()
        assert before["status"] == "blocked"

        # Seed enough GOOD minutes directly in the DB (40 × 60s = 40 min).
        with ProjectDB.open(config.DEFAULT_DB_PATH) as db:
            for i in range(40):
                db.add_clip(f"/seed/clip_{i}.wav", duration_s=60.0,
                            is_good=True, issues=[], transcript="hello there")

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
