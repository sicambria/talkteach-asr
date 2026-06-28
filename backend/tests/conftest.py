"""Shared pytest fixtures.

The fast suite must NEVER trigger a real (multi-GB download + slow) Whisper
fine-tune, even when the `[ml]` extras are installed in the environment. The
engine decides real-vs-simulation partly on whether manifest clips exist on disk
(project/docs/DECISIONS.md D-012), and tests can leave real on-disk clips lying around in the
shared data dir — so we pin the simulation on globally here. The opt-in
end-to-end test (`-m integration`) clears this itself to exercise the real loop.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _force_training_simulation(monkeypatch):
    monkeypatch.setenv("TALKTEACH_FORCE_SIMULATION", "1")
