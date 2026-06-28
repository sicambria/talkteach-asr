"""Shared pytest fixtures.

The fast suite must NEVER trigger a real (multi-GB download + slow) Whisper
fine-tune, even when the `[ml]` extras are installed in the environment. The
engine decides real-vs-simulation partly on whether manifest clips exist on disk
(project/docs/DECISIONS.md D-012), and tests can leave real on-disk clips lying around in the
shared data dir — so we pin the simulation on globally here. The opt-in
end-to-end test (`-m integration`) clears this itself to exercise the real loop.

Data-dir isolation (below) MUST happen at conftest import time, not in a fixture:
``talkteach.config`` reads ``TALKTEACH_DATA`` exactly once, when it is first
imported, and caches ``DATA_ROOT``/``DEFAULT_PROJECT_DIR`` as module constants.
pytest imports this conftest before any test module, so setting the env here binds
config to a throwaway dir no matter which test file triggers the first
``import talkteach.config`` — without it, a test file that imports config before
``test_api`` (e.g. ``test_benchmark_scoreboard`` in a partial run) would bind config
to the real ``~/.talkteach`` and the API tests would read the user's actual project.
"""

from __future__ import annotations

import os
import tempfile

import pytest

# Override unconditionally (not setdefault): tests must never touch real data, even
# if TALKTEACH_DATA is already set in the developer's/CI environment.
os.environ["TALKTEACH_DATA"] = tempfile.mkdtemp(prefix="talkteach-test-")


@pytest.fixture(autouse=True)
def _force_training_simulation(monkeypatch):
    monkeypatch.setenv("TALKTEACH_FORCE_SIMULATION", "1")
