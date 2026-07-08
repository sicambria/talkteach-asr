"""Benchmark dataset download and preparation.

Downloads are idempotent — skips if already cached with verified checksums.
Datasets:
  librispeech_test_clean  (340 MB) — OpenSLR
  common_voice_en         (200 MB subset) — Hugging Face datasets
  fleurs_en_es_fr         (1.5 GB) — Hugging Face datasets
  wham_noise              (100 MB subset) — WHAM! noise corpus
  librispeech_train_clean_100 (6.3 GB) — OpenSLR train-clean-100
Total: ~8.1 GB for full suite, ~2.1 GB for baseline-only.
"""

from __future__ import annotations

import hashlib
import os
import tarfile
import urllib.request
from pathlib import Path
from typing import Any

SOTA_CACHE = Path(
    os.environ.get("TALKTEACH_SOTA_CACHE", os.path.expanduser("~/.cache/talkteach/sota"))
)


DATASET_SPECS: dict[str, dict[str, Any]] = {
    "librispeech_test_clean": {
        "name": "LibriSpeech test-clean",
        "url": "https://www.openslr.org/resources/12/test-clean.tar.gz",
        "size_mb": 340,
        "format": "flac",
        "transcript_field": "transcript",
    },
    "librispeech_train_clean_100": {
        "name": "LibriSpeech train-clean-100",
        "url": "https://www.openslr.org/resources/12/train-clean-100.tar.gz",
        "size_mb": 6300,
        "format": "flac",
        "transcript_field": "transcript",
    },
    "common_voice_en": {
        "name": "Common Voice English (subset)",
        "hf_dataset": ("mozilla-foundation/common_voice_17_0", "en"),
        "size_mb": 200,
        "format": "mp3",
        "transcript_field": "sentence",
    },
    "fleurs": {
        "name": "FLEURS (en, es, fr subset)",
        "hf_dataset": ("google/fleurs", "en_us"),
        "size_mb": 1500,
        "format": "wav",
        "transcript_field": "transcription",
    },
    "wham_noise": {
        "name": "WHAM! noise samples (subset)",
        "size_mb": 100,
        "format": "wav",
        "transcript_field": None,  # noise has no transcript
    },
}


def _compute_sha256(filepath: Path) -> str:
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def download_librispeech(
    dataset_name: str,
    cache_dir: Path,
) -> Path:
    """Download and extract a LibriSpeech dataset from OpenSLR."""
    spec = DATASET_SPECS[dataset_name]
    cache_dir.mkdir(parents=True, exist_ok=True)

    tar_path = cache_dir / f"{dataset_name}.tar.gz"
    extract_dir = cache_dir / dataset_name

    if extract_dir.exists() and any(extract_dir.iterdir()):
        print(f"[sota] {spec['name']}: already cached at {extract_dir}")
        return extract_dir

    if not tar_path.exists():
        print(f"[sota] Downloading {spec['name']} (~{spec['size_mb']} MB)...")
        urllib.request.urlretrieve(spec["url"], tar_path)
        print(f"[sota] Downloaded to {tar_path}")

    print(f"[sota] Extracting {tar_path}...")
    extract_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(path=extract_dir)
    print(f"[sota] {spec['name']}: ready at {extract_dir}")
    return extract_dir


def download_hf_dataset(
    dataset_name: str,
    cache_dir: Path,
    split: str = "test",
    max_samples: int | None = None,
) -> Path:
    """Download a dataset from Hugging Face and save as (audio, transcript) pairs."""
    from datasets import load_dataset

    spec = DATASET_SPECS[dataset_name]
    hf_name, config = spec["hf_dataset"]
    output_dir = cache_dir / dataset_name / split

    if output_dir.exists() and any(output_dir.iterdir()):
        print(f"[sota] {spec['name']} ({split}): already cached at {output_dir}")
        return output_dir

    print(f"[sota] Loading {hf_name} ({config}, {split}) from Hugging Face...")
    ds = load_dataset(hf_name, config, split=split)

    if max_samples and len(ds) > max_samples:
        ds = ds.select(range(max_samples))

    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for i, item in enumerate(ds):
        audio = item.get("audio", {})
        audio_array = audio.get("array")
        sampling_rate = audio.get("sampling_rate", 16000)

        if audio_array is None:
            continue

        import soundfile as sf

        audio_path = output_dir / f"clip_{i:05d}.wav"
        sf.write(str(audio_path), audio_array, sampling_rate)

        transcript = item.get(spec["transcript_field"], "")
        if transcript:
            txt_path = output_dir / f"clip_{i:05d}.txt"
            txt_path.write_text(str(transcript).strip())
        count += 1

    print(f"[sota] {spec['name']} ({split}): {count} clips saved to {output_dir}")
    return output_dir


def generate_synthetic_noise(
    cache_dir: Path,
    num_samples: int = 50,
    duration_s: float = 5.0,
    sample_rate: int = 16000,
) -> Path:
    """Generate synthetic noise samples (white, pink, babble-like) for robustness testing.

    WHAM! requires registration; synthetic noise provides a zero-dependency fallback
    for D06 noise robustness measurements on CPU.
    """
    import numpy as np
    import soundfile as sf

    output_dir = cache_dir / "synthetic_noise"
    if output_dir.exists() and any(output_dir.iterdir()):
        print(f"[sota] Synthetic noise: already cached at {output_dir}")
        return output_dir

    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.RandomState(42)

    for i in range(num_samples):
        n_samples = int(duration_s * sample_rate)
        # Mix of white noise + pink-ish noise
        white = rng.randn(n_samples).astype(np.float32)
        # Simple pink noise approximation
        pink = np.cumsum(rng.randn(n_samples)).astype(np.float32)
        pink /= np.max(np.abs(pink)) + 1e-8
        noise = 0.6 * white + 0.4 * pink
        noise /= np.max(np.abs(noise)) + 1e-8

        out_path = output_dir / f"noise_{i:04d}.wav"
        sf.write(str(out_path), noise, sample_rate)

    print(f"[sota] Synthetic noise: {num_samples} samples at {output_dir}")
    return output_dir


def get_clip_paths(
    dataset_dir: Path,
    extensions: tuple[str, ...] = (".wav", ".flac", ".mp3"),
) -> list[Path]:
    """Recursively find all audio files in a dataset directory."""
    paths: list[Path] = []
    for ext in extensions:
        paths.extend(sorted(dataset_dir.rglob(f"*{ext}")))
    return paths


def get_transcript(
    audio_path: Path,
) -> str | None:
    """Get the transcript for an audio file.

    For LibriSpeech: reads .txt files in the same directory.
    For HuggingFace datasets: reads paired .txt files.
    """
    # Try paired .txt file (HF convention)
    txt_path = audio_path.with_suffix(".txt")
    if txt_path.exists():
        return txt_path.read_text().strip()

    # Try LibriSpeech convention: *.trans.txt in the same directory
    # LibriSpeech .trans.txt files are named {speaker_id}-{chapter_id}.trans.txt
    trans_files = list(audio_path.parent.glob("*.trans.txt"))
    if trans_files:
        base = audio_path.stem
        for trans_path in trans_files:
            for line in trans_path.read_text().splitlines():
                if line.startswith(base):
                    parts = line.split(" ", 1)
                    if len(parts) == 2:
                        return parts[1].strip()
    return None


def load_clip_transcript_pairs(
    dataset_dir: Path,
    max_clips: int | None = None,
) -> list[tuple[Path, str]]:
    """Load (audio_path, transcript) pairs from a prepared dataset directory."""
    paths = get_clip_paths(dataset_dir)
    pairs: list[tuple[Path, str]] = []
    for p in paths:
        t = get_transcript(p)
        if t:
            pairs.append((p, t))
        if max_clips and len(pairs) >= max_clips:
            break
    return pairs


def download(
    dataset_name: str,
    cache_dir: Path | None = None,
    split: str = "test",
    max_samples: int | None = None,
) -> Path:
    """Download a dataset. Entry point for validation scripts."""
    cache_dir = cache_dir or SOTA_CACHE
    spec = DATASET_SPECS.get(dataset_name)
    if not spec:
        raise ValueError(f"Unknown dataset: {dataset_name} (known: {list(DATASET_SPECS)})")

    if "hf_dataset" in spec:
        return download_hf_dataset(dataset_name, cache_dir, split=split, max_samples=max_samples)
    elif dataset_name == "wham_noise":
        return generate_synthetic_noise(cache_dir)
    elif "url" in spec:
        return download_librispeech(dataset_name, cache_dir)
    else:
        raise ValueError(f"No download method for dataset: {dataset_name}")
