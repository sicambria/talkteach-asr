"""Headless CLI — train / eval / export / import / subtitle / augment from a
terminal, no GUI (#54).

For power users, CI, and reproducible runs. It wraps the same pure modules the app
uses, so the terminal and the app agree by construction. Pure subcommands (``import``,
``eval``, ``augment``, ``metrics``) need no ML deps; the model subcommands
(``transcribe``, ``subtitle``, ``train``, ``export``) dispatch to an engine and fail
*gracefully* with a plain-language message when the ``[ml]`` deps are absent.

Entry point: ``talkteach`` (see ``[project.scripts]``), or ``python -m talkteach.cli``.
"""

from __future__ import annotations

import argparse
import json
import sys
import wave
from typing import TYPE_CHECKING, Any, cast

from talkteach.engines.base import EngineUnavailableError

if TYPE_CHECKING:
    from talkteach.transcript.subtitles import Segment


# --- small stdlib WAV helpers (keep `augment` dep-light) ----------------------
def _read_wav(path: str):  # noqa: ANN202
    import numpy as np

    with wave.open(path, "rb") as w:
        rate = w.getframerate()
        frames = w.readframes(w.getnframes())
        width = w.getsampwidth()
        channels = w.getnchannels()
    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}.get(width)
    if dtype is None:
        raise ValueError(f"unsupported WAV sample width: {width}")
    data = np.frombuffer(frames, dtype=dtype).astype("float32")
    if width == 2:
        data /= 32768.0
    elif width == 4:
        data /= 2147483648.0
    elif width == 1:
        data = (data - 128.0) / 128.0
    if channels == 2:
        data = data.reshape(-1, 2).mean(axis=1)
    return data, rate


def _write_wav(path: str, samples, rate: int) -> None:  # noqa: ANN001
    import numpy as np

    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def _emit(text: str, out: str | None) -> None:
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text if text.endswith("\n") else text + "\n")
    else:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")


# --- subcommands --------------------------------------------------------------


def _cmd_import(args: argparse.Namespace) -> int:
    from talkteach.data.import_manifest import DatasetImportError, import_dataset

    try:
        manifest = import_dataset(args.source, kind=args.kind)
    except DatasetImportError as exc:
        print(f"import failed: {exc}", file=sys.stderr)
        return 2
    _emit(json.dumps(manifest, indent=2), args.out)
    total_min = sum(m.get("duration_s", 0.0) for m in manifest) / 60.0
    print(f"imported {len(manifest)} clips ({total_min:.1f} min)", file=sys.stderr)
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    from talkteach.eval import error_report, normalized_vs_raw, per_utterance_wer

    refs = _read_lines(args.refs)
    hyps = _read_lines(args.hyps)
    if len(refs) != len(hyps):
        print(f"refs ({len(refs)}) and hyps ({len(hyps)}) differ in length", file=sys.stderr)
        return 2
    report = {
        "per_utterance": [
            {"index": s.index, "wer": s.wer, "cer": s.cer} for s in per_utterance_wer(refs, hyps)
        ],
        "errors": error_report(refs, hyps),
        "normalized_vs_raw": normalized_vs_raw(refs, hyps),
    }
    _emit(json.dumps(report, indent=2), args.out)
    return 0


def _cmd_augment(args: argparse.Namespace) -> int:
    from talkteach.audio import augment as aug

    samples, rate = _read_wav(args.source)
    if args.speed != 1.0:
        samples = aug.perturb_speed(samples, args.speed)
    if args.pitch != 0.0:
        try:
            samples = aug.perturb_pitch(samples, args.pitch, sample_rate=rate)
        except RuntimeError as exc:  # librosa missing → skip pitch, don't crash
            print(f"skipping --pitch: {exc}", file=sys.stderr)
    if args.noise:
        noise, _ = _read_wav(args.noise)
        samples = aug.mix_noise(samples, noise, snr_db=args.snr)
    _write_wav(args.out, samples, rate)
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


def _cmd_metrics(args: argparse.Namespace) -> int:
    from talkteach.obs import experiment as exp

    _emit(json.dumps(exp.summarize(args.workdir), indent=2), args.out)
    return 0


def _cmd_transcribe(args: argparse.Namespace) -> int:
    from talkteach.director.types import EngineKind
    from talkteach.engines import get_engine

    engine = get_engine(EngineKind.WHISPER_LORA)
    try:
        text = engine.transcribe(args.source, model_dir=args.model)
    except EngineUnavailableError as exc:
        print(f"transcribe unavailable: {exc}", file=sys.stderr)
        return 3
    _emit(text, args.out)
    return 0


def _cmd_subtitle(args: argparse.Namespace) -> int:
    from talkteach.director.types import EngineKind
    from talkteach.engines import get_engine
    from talkteach.transcript import segments_to_srt, segments_to_text, segments_to_vtt
    from talkteach.transcript.longform import transcribe_long

    engine = get_engine(EngineKind.WHISPER_LORA)
    segments: list[Any]
    try:
        if args.long:
            segments = transcribe_long(engine, args.source, model_dir=args.model)
        else:
            segments = engine.transcribe_segments(args.source, model_dir=args.model)
    except EngineUnavailableError as exc:
        print(f"subtitle unavailable: {exc}", file=sys.stderr)
        return 3
    writer = {"srt": segments_to_srt, "vtt": segments_to_vtt, "txt": segments_to_text}[args.format]
    _emit(writer(cast("list[Segment]", segments)), args.out)
    return 0


def _cmd_train(args: argparse.Namespace) -> int:
    from talkteach.director import build_plan, probe_hardware, probe_language
    from talkteach.director.types import DataProfile
    from talkteach.engines import get_engine

    manifest = json.loads(_read_text(args.manifest))
    minutes = sum(m.get("duration_s", 0.0) for m in manifest) / 60.0
    data = DataProfile(good_minutes=minutes, total_minutes=minutes, clip_count=len(manifest))
    plan = build_plan(probe_hardware(), data, probe_language(args.language))
    engine = get_engine(plan.engine)
    try:
        result = engine.train(plan, manifest, args.workdir, progress=_print_progress)
    except EngineUnavailableError as exc:
        print(f"train unavailable: {exc}", file=sys.stderr)
        return 3
    print(f"\n{result.message}", file=sys.stderr)
    return 0 if result.done else 1


def _cmd_export(args: argparse.Namespace) -> int:
    from talkteach.director.types import EngineKind
    from talkteach.engines import get_engine

    engine = get_engine(EngineKind.WHISPER_LORA)
    result = engine.export(args.model, args.out, fmt=args.format)
    print(f"{result.format}: {result.notes}", file=sys.stderr)
    return 0


# --- helpers ------------------------------------------------------------------


def _read_text(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _read_lines(path: str) -> list[str]:
    return [ln.rstrip("\n") for ln in _read_text(path).splitlines()]


def _print_progress(p) -> None:  # noqa: ANN001
    pct = int(p.fraction * 100)
    sys.stderr.write(f"\r[{pct:3d}%] {p.message}")
    sys.stderr.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="talkteach", description="TalkTeach headless CLI (#54).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_imp = sub.add_parser("import", help="import a dataset → canonical manifest JSON")
    p_imp.add_argument("source")
    p_imp.add_argument(
        "--kind",
        default="auto",
        choices=["auto", "folder", "csv", "common_voice", "json", "nemo", "librispeech"],
    )
    p_imp.add_argument("--out")
    p_imp.set_defaults(func=_cmd_import)

    p_eval = sub.add_parser("eval", help="WER/CER + error report over ref/hyp line files")
    p_eval.add_argument("--refs", required=True)
    p_eval.add_argument("--hyps", required=True)
    p_eval.add_argument("--out")
    p_eval.set_defaults(func=_cmd_eval)

    p_aug = sub.add_parser("augment", help="apply speed/pitch/noise augmentation to a WAV")
    p_aug.add_argument("source")
    p_aug.add_argument("--out", required=True)
    p_aug.add_argument("--speed", type=float, default=1.0)
    p_aug.add_argument("--pitch", type=float, default=0.0, help="semitones")
    p_aug.add_argument("--noise", help="WAV of noise to mix in")
    p_aug.add_argument("--snr", type=float, default=20.0, help="target SNR dB for --noise")
    p_aug.set_defaults(func=_cmd_augment)

    p_met = sub.add_parser("metrics", help="summarize a run's local metrics.jsonl (#53)")
    p_met.add_argument("workdir")
    p_met.add_argument("--out")
    p_met.set_defaults(func=_cmd_metrics)

    p_tr = sub.add_parser("transcribe", help="transcribe one clip (needs [ml])")
    p_tr.add_argument("source")
    p_tr.add_argument("--model", help="trained model / export dir")
    p_tr.add_argument("--out")
    p_tr.set_defaults(func=_cmd_transcribe)

    p_sub = sub.add_parser("subtitle", help="subtitle a file → SRT/VTT/txt (needs [ml])")
    p_sub.add_argument("source")
    p_sub.add_argument("--format", default="srt", choices=["srt", "vtt", "txt"])
    p_sub.add_argument("--long", action="store_true", help="chunk long files (#49)")
    p_sub.add_argument("--model")
    p_sub.add_argument("--out")
    p_sub.set_defaults(func=_cmd_subtitle)

    p_train = sub.add_parser("train", help="train from a manifest JSON (needs [ml])")
    p_train.add_argument("--manifest", required=True)
    p_train.add_argument("--workdir", required=True)
    p_train.add_argument("--language")
    p_train.set_defaults(func=_cmd_train)

    p_exp = sub.add_parser("export", help="export a trained model to a portable format")
    p_exp.add_argument("--model", required=True)
    p_exp.add_argument("--out", required=True)
    p_exp.add_argument(
        "--format",
        default="ctranslate2",
        choices=["ctranslate2", "onnx", "safetensors", "torchscript", "gguf"],
    )
    p_exp.set_defaults(func=_cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
