"""Dataset import — bring an existing corpus, not just in-app recordings (#47).

Grown-ups often already have labelled audio: a folder of (clip, transcript) pairs,
a CSV/JSON manifest, a NeMo JSONL manifest, a Common Voice TSV export, or a
LibriSpeech tree. Each importer normalises to TalkTeach's one canonical manifest
shape — ``[{"path", "text", "duration_s"}, ...]`` (the same shape
``tts.synthesize_dataset`` and every engine consume) — so imported data flows
straight into the director, sufficiency gate, and training loop.

Pure stdlib parsing (csv/json/pathlib); durations are best-effort via the stdlib
``wave`` header for WAV, an optional guarded ``soundfile`` for other formats, else
``0.0`` (or the value the manifest already carries). No torch, no ffmpeg required to
*parse* — audio is only decoded at train time.
"""

from __future__ import annotations

import csv
import json
import os
import wave
from pathlib import Path

# Audio extensions we recognise when scanning a folder / resolving a clip path.
_AUDIO_EXTS = frozenset({".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus", ".webm", ".aac"})
# Column names different tools use for the audio path and the transcript.
_PATH_KEYS = ("path", "audio", "audio_filepath", "file", "filename", "wav", "clip")
_TEXT_KEYS = ("text", "transcript", "sentence", "transcription", "label", "words")


class DatasetImportError(ValueError):
    """A dataset could not be imported (missing files, unknown columns, empty)."""


def _wav_duration(path: str) -> float:
    """WAV duration via the stdlib header; 0.0 if not a readable WAV."""
    try:
        with wave.open(path, "rb") as w:
            rate = w.getframerate()
            return w.getnframes() / float(rate) if rate else 0.0
    except (wave.Error, OSError, EOFError):
        return 0.0


def _duration_s(path: str) -> float:
    """Best-effort clip duration. WAV via stdlib; other formats via guarded
    ``soundfile`` when installed; else 0.0 (training still works — it decodes then).
    """
    if path.lower().endswith(".wav"):
        return _wav_duration(path)
    try:
        import soundfile as sf  # guarded: optional, only if present

        info = sf.info(path)
        return float(info.frames) / float(info.samplerate) if info.samplerate else 0.0
    except Exception:
        return 0.0


def _entry(path: str, text: str, duration_s: float | None = None) -> dict:
    return {
        "path": path,
        "text": text.strip(),
        "duration_s": float(duration_s) if duration_s is not None else _duration_s(path),
    }


def _first(row: dict, keys: tuple[str, ...]) -> str | None:
    for k in keys:
        if k in row and str(row[k]).strip():
            return str(row[k])
    return None


def _resolve(path_field: str, root: Path) -> str:
    """Resolve a manifest path against ``root`` (absolute paths pass through)."""
    p = Path(path_field)
    return str(p if p.is_absolute() else (root / p))


# --- individual importers -----------------------------------------------------


def import_folder_pairs(directory: str | os.PathLike[str]) -> list[dict]:
    """A folder of ``clip.wav`` + sidecar ``clip.txt`` transcript pairs.

    For every audio file, reads the same-stem ``.txt`` as its transcript; audio
    without a sidecar (and empty transcripts) are skipped. Sorted by filename for
    determinism.
    """
    root = Path(directory)
    if not root.is_dir():
        raise DatasetImportError(f"not a directory: {directory}")
    manifest: list[dict] = []
    for audio in sorted(root.iterdir()):
        if audio.suffix.lower() not in _AUDIO_EXTS:
            continue
        sidecar = audio.with_suffix(".txt")
        if not sidecar.is_file():
            continue
        text = sidecar.read_text(encoding="utf-8").strip()
        if text:
            manifest.append(_entry(str(audio), text))
    return manifest


def import_csv(path: str | os.PathLike[str]) -> list[dict]:
    """A CSV/TSV manifest with a path column and a text column (header required).

    Delimiter is sniffed (``,`` or tab). Column names are matched flexibly against
    common conventions (``path``/``audio``/``file`` and ``text``/``sentence``/…).
    Relative paths resolve against the CSV's directory.
    """
    p = Path(path)
    root = p.parent
    with p.open(encoding="utf-8", newline="") as fh:
        sample = fh.read(2048)
        fh.seek(0)
        delim = "\t" if sample.count("\t") > sample.count(",") else ","
        reader = csv.DictReader(fh, delimiter=delim)
        rows = list(reader)
    if not rows:
        raise DatasetImportError(f"no rows in {path}")
    manifest: list[dict] = []
    for row in rows:
        path_field = _first(row, _PATH_KEYS)
        text = _first(row, _TEXT_KEYS)
        if not path_field or not text:
            continue
        dur = row.get("duration") or row.get("duration_s")
        manifest.append(
            _entry(
                _resolve(path_field, root),
                text,
                float(dur) if dur and str(dur).strip() else None,
            )
        )
    if not manifest:
        raise DatasetImportError(
            f"{path}: found no usable rows — need a path column ({'/'.join(_PATH_KEYS)}) "
            f"and a text column ({'/'.join(_TEXT_KEYS)})"
        )
    return manifest


def import_common_voice_tsv(
    path: str | os.PathLike[str], clips_dir: str | os.PathLike[str] | None = None
) -> list[dict]:
    """A Mozilla Common Voice ``*.tsv`` export (columns ``path`` + ``sentence``).

    Clip filenames in the TSV are relative to the dataset's ``clips/`` folder; pass
    ``clips_dir`` (defaults to a sibling ``clips/`` of the TSV).
    """
    p = Path(path)
    clips = Path(clips_dir) if clips_dir else p.parent / "clips"
    with p.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        rows = list(reader)
    manifest: list[dict] = []
    for row in rows:
        name = _first(row, _PATH_KEYS)
        text = _first(row, _TEXT_KEYS)
        if not name or not text:
            continue
        manifest.append(_entry(_resolve(name, clips), text))
    if not manifest:
        raise DatasetImportError(
            f"{path}: no path/sentence rows found (is this a Common Voice TSV?)"
        )
    return manifest


def import_json_manifest(path: str | os.PathLike[str]) -> list[dict]:
    """A JSON array **or** a NeMo-style JSONL manifest (one JSON object per line).

    Each record needs an audio-path field (``audio_filepath``/``path``/…) and a text
    field (``text``/``transcript``/…); a ``duration`` is used when present (NeMo
    manifests carry it). Relative paths resolve against the manifest's directory.
    """
    p = Path(path)
    root = p.parent
    text_body = p.read_text(encoding="utf-8").strip()
    records: list[dict]
    if text_body.startswith("["):
        records = json.loads(text_body)
    else:  # JSONL (NeMo) — one object per non-empty line
        records = [json.loads(line) for line in text_body.splitlines() if line.strip()]
    manifest: list[dict] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        path_field = _first(rec, _PATH_KEYS)
        text = _first(rec, _TEXT_KEYS)
        if not path_field or not text:
            continue
        dur = rec.get("duration") or rec.get("duration_s")
        manifest.append(
            _entry(_resolve(path_field, root), text, float(dur) if dur is not None else None)
        )
    if not manifest:
        raise DatasetImportError(f"{path}: no usable records (need an audio path + a transcript)")
    return manifest


def import_librispeech(directory: str | os.PathLike[str]) -> list[dict]:
    """A LibriSpeech tree: ``*.trans.txt`` files mapping ``<id> TRANSCRIPT`` to
    ``<id>.flac``/``.wav`` in the same folder. Walks recursively.
    """
    root = Path(directory)
    if not root.is_dir():
        raise DatasetImportError(f"not a directory: {directory}")
    manifest: list[dict] = []
    for trans in sorted(root.rglob("*.trans.txt")):
        folder = trans.parent
        for line in trans.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            utt_id, _, text = line.partition(" ")
            if not text:
                continue
            audio = None
            for ext in (".flac", ".wav"):
                cand = folder / f"{utt_id}{ext}"
                if cand.is_file():
                    audio = cand
                    break
            if audio is not None:
                manifest.append(_entry(str(audio), text))
    if not manifest:
        raise DatasetImportError(f"{directory}: no *.trans.txt utterances with matching audio")
    return manifest


# --- dispatcher ---------------------------------------------------------------

_KINDS = ("folder", "csv", "common_voice", "json", "nemo", "librispeech")


def import_dataset(source: str | os.PathLike[str], kind: str = "auto") -> list[dict]:
    """Import ``source`` into the canonical manifest, auto-detecting ``kind``.

    ``kind`` is one of ``folder``, ``csv``, ``common_voice``, ``json``/``nemo``,
    ``librispeech``, or ``auto`` (default). Auto-detection: a directory with any
    ``*.trans.txt`` is LibriSpeech, any other directory is a folder-of-pairs; a
    ``.json``/``.jsonl`` file is a JSON/NeMo manifest; a ``.tsv`` is Common Voice;
    any other file is a CSV.
    """
    src = Path(source)
    if kind == "auto":
        kind = _detect_kind(src)
    if kind == "folder":
        return import_folder_pairs(src)
    if kind == "librispeech":
        return import_librispeech(src)
    if kind in ("json", "nemo"):
        return import_json_manifest(src)
    if kind == "common_voice":
        return import_common_voice_tsv(src)
    if kind == "csv":
        return import_csv(src)
    raise DatasetImportError(f"unknown dataset kind {kind!r}; expected one of {_KINDS} or 'auto'")


def _detect_kind(src: Path) -> str:
    if src.is_dir():
        return "librispeech" if any(src.rglob("*.trans.txt")) else "folder"
    suffix = src.suffix.lower()
    if suffix in (".json", ".jsonl"):
        return "json"
    if suffix == ".tsv":
        return "common_voice"
    return "csv"
