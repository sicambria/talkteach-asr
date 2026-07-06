"""Framework-light training helpers shared by every real ASR engine.

These were originally inside :mod:`_whisper_train`; they are engine-agnostic
(WER/CER, the smartness mapping, the simulate/real dispatch, checkpoint discovery,
the NaN-rollback guard, and a dependency-free training *simulation*), so the
wav2vec2-CTC engine reuses them rather than duplicating the logic. Nothing here
imports torch/transformers — jiwer is light and torch-free — so the module costs
nothing to import on a plain laptop and the helpers stay unit-testable directly.

:mod:`_whisper_train` re-exports the pure helpers for backward compatibility, so
``from talkteach.engines import _whisper_train as wt; wt.wer(...)`` still works.
"""

from __future__ import annotations

import json
import os
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from talkteach.director.types import TrainingPlan

    from .base import ProgressCallback, ShouldStop, TrainProgress


# --- simulate/real dispatch (DECISIONS.md D-012) -----------------------------


def should_simulate(manifest: list[dict], *, has_train_deps: bool) -> tuple[bool, str]:
    """Decide whether ``train()`` must fall back to the simulation (D-012).

    Returns ``(simulate, reason)``. We simulate when the training deps are
    missing, when ``TALKTEACH_FORCE_SIMULATION=1``, or when none of the manifest
    clips actually exist on disk (we cannot really train on audio we can't load).
    """
    if not has_train_deps:
        return True, "training deps (torch/transformers/peft) not installed"
    if os.environ.get("TALKTEACH_FORCE_SIMULATION") == "1":
        return True, "TALKTEACH_FORCE_SIMULATION=1"
    if not manifest:
        return True, "no training clips"
    if not any(os.path.isfile(item.get("path", "")) for item in manifest):
        return True, "no manifest clip exists on disk"
    return False, ""


# --- measured metrics (#2) ---------------------------------------------------


def _normalise(text: str) -> str:
    """Light normalisation for WER/CER: lowercase + collapse whitespace.

    Keeps the comparison case- and spacing-insensitive, which also makes the CTC
    engines (whose tokenizers emit uppercase) comparable to Whisper on equal terms.
    """
    return " ".join(text.lower().split())


def wer(references: list[str], hypotheses: list[str]) -> float:
    """Word Error Rate in [0, ~]. Thin, normalised wrapper over jiwer."""
    import jiwer

    refs = [_normalise(r) for r in references]
    hyps = [_normalise(h) for h in hypotheses]
    # jiwer treats an empty reference as undefined; guard so a degenerate eval
    # set returns a sane 1.0 (everything wrong) rather than raising.
    if not any(refs):
        return 1.0
    return float(jiwer.wer(refs, hyps))


def cer(references: list[str], hypotheses: list[str]) -> float:
    """Character Error Rate in [0, ~]. Thin, normalised wrapper over jiwer."""
    import jiwer

    refs = [_normalise(r) for r in references]
    hyps = [_normalise(h) for h in hypotheses]
    if not any(refs):
        return 1.0
    return float(jiwer.cer(refs, hyps))


def smartness_from_wer(wer_value: float) -> float:
    """Map WER → the easy-mode "smartness" meter = clamp(1 − WER, 0, 1) (#2)."""
    return max(0.0, min(1.0, 1.0 - wer_value))


# --- checkpoint discovery (#1/#17) -------------------------------------------


def find_latest_checkpoint(workdir: str) -> str | None:
    """Return the newest HF ``checkpoint-<step>`` dir in ``workdir`` (or None)."""
    if not os.path.isdir(workdir):
        return None
    best_step, best_path = -1, None
    for name in os.listdir(workdir):
        if name.startswith("checkpoint-"):
            tail = name[len("checkpoint-") :]
            if tail.isdigit() and os.path.isdir(os.path.join(workdir, name)):
                step = int(tail)
                if step > best_step:
                    best_step, best_path = step, os.path.join(workdir, name)
    return best_path


# --- NaN-rollback guard (safety rail #3) -------------------------------------


class NanRollbackGuard:
    """Detect a NaN/inf loss and roll back to the last good state (safety rail #3).

    HF's trainers already skip an individual non-finite *gradient* step, but a run
    that diverges into NaN should stop and restore the best checkpoint rather than
    save garbage. This pure helper holds that policy so it can be unit-tested
    without a trainer: feed it observed losses/checkpoints; ask whether to stop and
    which checkpoint to restore.
    """

    def __init__(self) -> None:
        self.last_good_checkpoint: str | None = None
        self.tripped = False

    def observe_good_checkpoint(self, path: str) -> None:
        self.last_good_checkpoint = path

    def is_finite(self, loss: float) -> bool:
        return loss == loss and loss not in (float("inf"), float("-inf"))

    def should_rollback(self, loss: float) -> bool:
        """True if ``loss`` is non-finite (NaN/inf) → caller stops + restores."""
        if not self.is_finite(loss):
            self.tripped = True
            return True
        return False


# --- dependency-free training simulation -------------------------------------


def _synthetic_smartness(epoch: int, total: int) -> float:
    """A plausible rising "smartness" (= 1 − WER) curve in [0, 1].

    Diminishing-returns shape that climbs toward ~0.92 but never hits 1.0.
    """
    progress = epoch / max(1, total)
    return round(0.92 * (1.0 - (1.0 - progress) ** 2), 4)


def simulate_training(
    plan: TrainingPlan,
    manifest: list[dict],
    workdir: str,
    progress: ProgressCallback | None,
    should_stop: ShouldStop | None,
    *,
    engine_label: str,
) -> TrainProgress:
    """Dependency-free stand-in for a real fine-tune (used when deps/audio absent).

    Emits a rising ``fraction`` and synthetic ``smartness`` curve, respects
    ``should_stop``, and writes one SIMULATION-marked JSON checkpoint per epoch so
    resume is demonstrable — mirroring the Whisper simulation but engine-agnostic.
    """
    from .base import TrainProgress

    os.makedirs(workdir, exist_ok=True)
    total = max(1, int(plan.epochs))
    start_epoch = _latest_sim_epoch(workdir) + 1

    if start_epoch > total:
        final = TrainProgress(
            epoch=total,
            total_epochs=total,
            fraction=1.0,
            smartness=_synthetic_smartness(total, total),
            message=f"Already taught! (resumed) [SIMULATION:{engine_label}]",
            done=True,
        )
        if progress is not None:
            progress(final)
        return final

    last = TrainProgress(
        epoch=start_epoch - 1,
        total_epochs=total,
        fraction=(start_epoch - 1) / total,
        smartness=None,
        message=f"Getting ready… [SIMULATION:{engine_label}]",
    )
    for epoch in range(start_epoch, total + 1):
        if should_stop is not None and should_stop():
            cancelled = TrainProgress(
                epoch=epoch - 1,
                total_epochs=total,
                fraction=(epoch - 1) / total,
                smartness=last.smartness,
                message=f"Stopped. Progress was saved. [SIMULATION:{engine_label}]",
                done=False,
            )
            if progress is not None:
                progress(cancelled)
            return cancelled
        time.sleep(0.0)
        smartness = _synthetic_smartness(epoch, total)
        _write_sim_checkpoint(workdir, plan, epoch, total, smartness, len(manifest), engine_label)
        last = TrainProgress(
            epoch=epoch,
            total_epochs=total,
            fraction=epoch / total,
            smartness=smartness,
            message=f"Learning… epoch {epoch} of {total} [SIMULATION:{engine_label}]",
            done=(epoch == total),
        )
        if progress is not None:
            progress(last)

    last.fraction = 1.0
    last.done = True
    last.message = f"All done — your computer got smarter! [SIMULATION:{engine_label}]"
    return last


def _sim_checkpoint_path(workdir: str, epoch: int) -> str:
    return os.path.join(workdir, f"checkpoint_epoch_{epoch}.json")


def _latest_sim_epoch(workdir: str) -> int:
    if not os.path.isdir(workdir):
        return 0
    best = 0
    for name in os.listdir(workdir):
        if name.startswith("checkpoint_epoch_") and name.endswith(".json"):
            stem = name[len("checkpoint_epoch_") : -len(".json")]
            if stem.isdigit():
                best = max(best, int(stem))
    return best


def _write_sim_checkpoint(
    workdir: str,
    plan: TrainingPlan,
    epoch: int,
    total: int,
    smartness: float,
    num_examples: int,
    engine_label: str,
) -> None:
    payload = {
        "mode": "SIMULATION",
        "marker": "SIMULATION",
        "engine": engine_label,
        "base_checkpoint": plan.base_checkpoint,
        "epoch": epoch,
        "total_epochs": total,
        "smartness": smartness,
        "num_examples": num_examples,
        "effective_batch": plan.effective_batch,
        "seed": plan.seed,
    }
    with open(_sim_checkpoint_path(workdir, epoch), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
