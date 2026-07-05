"""Engine adapter contract — the boundary between the director and ML frameworks.

The director (hardware/data/language probes + policy) produces a framework-free
``TrainingPlan``. An *engine adapter* is the only place in the backend that is
allowed to touch heavy ML libraries (torch, transformers, peft, faster-whisper,
ctranslate2). Everything in this module is import-light on purpose: it MUST
import with NONE of those installed, so the FastAPI job server, the director, and
the test suite all work on a plain laptop with no GPU.

How the methods map to the four child-facing screens:

* **Teach!**  -> :meth:`ASREngine.train` drives the training run, streaming
  :class:`TrainProgress` to the UI (a friendly "getting smarter" meter, not a
  loss curve). It checkpoints to ``workdir`` so a crashed/closed app can resume.
* **Try it** -> :meth:`ASREngine.transcribe` runs the trained (or base) model on
  one clip so the child can hear "what the computer heard".
* **Use on my computer** -> :meth:`ASREngine.export` packages the model into a
  portable runtime format (CTranslate2 by default) the family can run offline.
* **Grown-up mode** reads :meth:`ASREngine.is_available` to explain, in plain
  language, what (if anything) needs installing before the big button works.
"""

from __future__ import annotations

import abc
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # types.py is framework-free, but keep it behind TYPE_CHECKING so this module
    # has zero import cost and zero import-order coupling at runtime where the
    # annotations are strings (PEP 563 via `from __future__ import annotations`).
    from talkteach.director.types import TrainingPlan


class EngineUnavailableError(RuntimeError):
    """Raised when an engine is asked to do real work without its ML deps.

    The message is written for a *grown-up helping a child*, not an ML engineer:
    it names the missing piece and how to get it, and never dumps a traceback at
    the kid. UI code should catch this and show a gentle "ask a grown-up to
    install the training pack" card rather than crashing the app.
    """


@dataclass
class TrainProgress:
    """A single heartbeat of a training run, sized for a child-friendly meter.

    ``fraction`` drives the overall progress bar; ``smartness`` drives the
    separate "how smart is it getting?" indicator. We deliberately do NOT expose
    loss — kids (and most grown-ups) read "smartness" far better than "0.42 CE".
    """

    epoch: int
    total_epochs: int
    fraction: float  # overall progress in [0, 1]
    smartness: float | None  # 1 - val_WER on a held-out set, [0, 1]; None until first eval
    message: str
    done: bool = False
    failed: bool = False


@dataclass
class ExportResult:
    """Outcome of "Use on my computer" — where the portable model landed."""

    format: str  # e.g. "ctranslate2", "manifest" (dry-run placeholder)
    path: str  # directory or file the family can copy to another machine
    notes: str  # plain-language notes: what was produced / what deps are needed


# Callback / cancellation aliases, named for readability at call sites.
ProgressCallback = Callable[[TrainProgress], None]
ShouldStop = Callable[[], bool]


def _wav_duration_or_zero(audio_path: str) -> float:
    """Seconds of a WAV via the stdlib ``wave`` header (import-light); 0.0 on any
    non-WAV / unreadable file. Used by the default segment fallback so it needs no
    audio deps."""
    import contextlib
    import wave

    with contextlib.suppress(Exception), wave.open(audio_path, "rb") as w:
        rate = w.getframerate()
        if rate:
            return w.getnframes() / float(rate)
    return 0.0


class ASREngine(abc.ABC):
    """Abstract adapter every training engine implements.

    Subclasses (e.g. :class:`~talkteach.engines.whisper_lora.WhisperLoRAEngine`)
    own all heavy-dependency imports and isolate them so this package imports
    cleanly without any ML framework present.
    """

    @abc.abstractmethod
    def name(self) -> str:
        """Stable, human-readable engine name (shown in Grown-up mode)."""

    @abc.abstractmethod
    def is_available(self) -> tuple[bool, str]:
        """Report whether this engine can train *right now* on this machine.

        Returns ``(True, "")`` when every required dependency is importable.
        Otherwise returns ``(False, msg)`` where ``msg`` names the specific
        missing module(s) and tells a grown-up how to fix it (install the
        ``talkteach-backend[ml]`` extra). Drives the "Teach!" button's awake/
        asleep state and the Grown-up mode explanation.
        """

    @abc.abstractmethod
    def train(
        self,
        plan: TrainingPlan,
        manifest: list[dict],
        workdir: str,
        progress: ProgressCallback | None = None,
        should_stop: ShouldStop | None = None,
    ) -> TrainProgress:
        """Run the "Teach!" job and return the final :class:`TrainProgress`.

        Parameters
        ----------
        plan:
            The fully-resolved, zero-config :class:`TrainingPlan` from the
            director. The engine reads hyperparameters from here and never asks
            the user anything.
        manifest:
            Training examples as ``[{"path": <wav>, "text": <transcript>}, ...]``.
        workdir:
            Directory the engine OWNS for this run. Checkpoints are written here.
            Implementations should support *checkpoint-and-resume*: on entry,
            scan ``workdir`` for the latest checkpoint and continue from it, so a
            closed/crashed app can pick the run back up where it left off.
        progress:
            Optional callback invoked with a fresh :class:`TrainProgress` at each
            step so the UI meter advances live.
        should_stop:
            Optional cooperative-cancel predicate, polled between steps. When it
            returns ``True`` the engine stops cleanly (flushing a checkpoint) and
            returns a non-``done`` progress flagged as cancelled — it never kills
            the process or corrupts ``workdir``.

        Raises
        ------
        EngineUnavailableError
            If the engine's required deps are missing and no fallback applies.
        """

    @abc.abstractmethod
    def transcribe(
        self, audio_path: str, model_dir: str | None = None, base_checkpoint: str | None = None
    ) -> str:
        """ "Try it": transcribe one clip and return the recognised text.

        Uses the trained model in ``model_dir`` when given, else the base model.
        ``base_checkpoint`` (optional) names the *untrained* base to score with when
        no trained ``model_dir`` is supplied — the benchmark uses it to measure the
        delta a fine-tune buys (see :mod:`talkteach.benchmark`). Engines that can't
        score an arbitrary base may ignore it.
        Raises :class:`EngineUnavailableError` if inference deps are missing.
        """

    def transcribe_segments(
        self, audio_path: str, model_dir: str | None = None, base_checkpoint: str | None = None
    ) -> list[dict]:
        """Segment-returning decode for subtitles + long-form (#48/#49).

        Returns ``[{"start": float, "end": float, "text": str}, ...]`` in seconds.
        The default wraps :meth:`transcribe` into a single whole-clip segment
        (duration measured from a WAV header via stdlib ``wave``, else ``0.0``) so
        every engine works out of the box. Engines with a native segmenting
        decoder (e.g. faster-whisper) override this to return real per-utterance
        timestamps. Kept import-light — no heavy deps at this layer.
        """
        text = self.transcribe(audio_path, model_dir=model_dir, base_checkpoint=base_checkpoint)
        return [{"start": 0.0, "end": _wav_duration_or_zero(audio_path), "text": text}]

    @abc.abstractmethod
    def export(self, model_dir: str, out_dir: str, fmt: str = "ctranslate2") -> ExportResult:
        """ "Use on my computer": package ``model_dir`` into a portable format.

        Default ``fmt`` is CTranslate2 (fast, CPU-friendly, offline). Returns an
        :class:`ExportResult` describing what was produced and where.
        """
