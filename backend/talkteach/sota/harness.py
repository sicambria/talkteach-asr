"""SOTA benchmark harness — run domains, measure metrics, produce results.

One harness to rule all 15 domains. Each domain run produces a SOTAResult
with score 0-1000, band name, metrics, and confidence intervals.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from talkteach.sota.datasets import (
    SOTA_CACHE,
    download,
    generate_synthetic_noise,
    load_clip_transcript_pairs,
)
from talkteach.sota.domains import ALL_DOMAINS, Domain
from talkteach.sota.scoring import (
    aggregate_headline,
    cer,
    confidence_interval,
    rtf,
    score_against_bands,
    wer,
)

_ENGINE_ALIASES = {
    "whisper-tiny": "tiny",
    "whisper-base": "base",
    "whisper-small": "small",
    "whisper-medium": "medium",
    "whisper-large": "large-v3",
}


def normalize_engine(name: str) -> str:
    """Map CLI/engine-filter names to faster-whisper model sizes.

    faster-whisper rejects names like "whisper-tiny" (it wants "tiny"); the SOTA
    domains/CLI use the "whisper-*" spelling, so normalize at the model boundary.
    """
    n = (name or "").strip()
    if n in _ENGINE_ALIASES:
        return _ENGINE_ALIASES[n]
    if n.startswith("whisper-"):
        return n[len("whisper-") :]
    return n or "tiny"


@dataclass
class SOTAResult:
    """Result from running one domain benchmark."""

    domain_id: str
    domain_name: str
    score_0_1000: int
    band: str
    metrics: dict[str, float] = field(default_factory=dict)
    confidence_95: dict[str, tuple[float, float]] = field(default_factory=dict)
    baseline_ref: str = ""
    sota_ref: str = ""
    num_samples: int = 0
    engine_used: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    git_commit: str = ""
    notes: str = ""
    directional: bool = False  # measured but under-powered → excluded from the headline mean
    directional_reason: str = ""


@dataclass
class Scoreboard:
    """Aggregated results across all domains."""

    domains: list[SOTAResult] = field(default_factory=list)
    overall_mean: float = 0.0
    overall_band: str = "bronze"
    generated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Coverage — how much of the 15-domain suite actually stands behind the headline.
    num_total: int = 0
    num_measured: int = 0
    num_eligible: int = 0  # measured AND adequately powered
    num_directional: int = 0  # measured but under-powered (excluded from the mean)
    num_unmeasured: int = 0

    @property
    def sorted_by_score(self) -> list[SOTAResult]:
        return sorted(self.domains, key=lambda r: r.score_0_1000, reverse=True)


class SOTAHarness:
    """Runs SOTA benchmarks across domains."""

    def __init__(
        self,
        engines: list[str] | None = None,
        data_root: Path | None = None,
        seed: int = 42,
        baseline_only: bool = False,
    ):
        self.engines = engines or ["tiny"]
        self.data_root = data_root or Path(
            os.environ.get("TALKTEACH_DATA_ROOT", Path.cwd() / "backend" / ".data")
        )
        self.seed = seed
        self.baseline_only = baseline_only
        self.cache_dir = SOTA_CACHE

    def ensure_data(self, domain: Domain) -> dict[str, Path]:
        """Download all datasets needed for a domain."""
        paths: dict[str, Path] = {}
        for ds_name in domain.data_filter:
            if ds_name == "wham_noise" or ds_name == "synthetic_noise":
                paths[ds_name] = generate_synthetic_noise(self.cache_dir)
            elif ds_name == "librispeech_test_clean":
                paths[ds_name] = download("librispeech_test_clean", self.cache_dir)
            elif ds_name == "librispeech_train_clean_100":
                paths[ds_name] = download("librispeech_train_clean_100", self.cache_dir)
            elif ds_name == "common_voice_en":
                paths[ds_name] = download(
                    "common_voice_en", self.cache_dir, split="test", max_samples=200
                )
            elif ds_name == "fleurs":
                paths[ds_name] = download("fleurs", self.cache_dir, split="test", max_samples=300)
            elif ds_name == "labelled_quality_set":
                paths[ds_name] = self.cache_dir / "labelled_quality_set"
                if not paths[ds_name].exists():
                    raise FileNotFoundError(
                        f"Labelled quality set not found at {paths[ds_name]}. "
                        f"Create it by labelling clips (see docs/sota-benchmarks/VALIDATION.md)."
                    )
        return paths

    def measure_base_wer(
        self,
        eval_dir: Path,
        engine_name: str = "tiny",
        max_clips: int = 100,
    ) -> dict[str, Any]:
        """Measure base (untrained) WER on an eval directory using faster-whisper."""
        from faster_whisper import WhisperModel

        pairs = load_clip_transcript_pairs(eval_dir, max_clips=max_clips)
        if not pairs:
            return {"wer": -1.0, "cer": -1.0, "num_clips": 0, "error": "no clips found"}

        model = WhisperModel(engine_name, device="cpu", compute_type="int8")
        references: list[str] = []
        hypotheses: list[str] = []
        per_clip_wer: list[float] = []

        for audio_path, ref_text in pairs:
            segments, _ = model.transcribe(str(audio_path), beam_size=5)
            hyp_text = " ".join(s.text.strip() for s in segments)
            ref_lower = ref_text.lower()
            hyp_lower = hyp_text.lower()
            references.append(ref_lower)
            hypotheses.append(hyp_lower)
            # Compute per-clip WER for meaningful CI
            per_clip_wer.append(wer([ref_lower], [hyp_lower]))

        clip_wer = wer(references, hypotheses)
        clip_cer = cer(references, hypotheses)

        return {
            "wer": clip_wer,
            "cer": clip_cer,
            "num_clips": len(pairs),
            "ci_95_wer": confidence_interval(per_clip_wer, seed=self.seed),
        }

    def measure_rtf(
        self,
        eval_dir: Path,
        engine_name: str = "tiny",
        max_clips: int = 20,
    ) -> dict[str, Any]:
        """Measure Real-Time Factor on an eval directory."""
        import soundfile as sf
        from faster_whisper import WhisperModel

        paths = (
            sorted(eval_dir.rglob("*.flac"))[:max_clips]
            or sorted(eval_dir.rglob("*.wav"))[:max_clips]
        )
        if not paths:
            return {"rtf": -1.0, "num_clips": 0, "error": "no audio files found"}

        model = WhisperModel(engine_name, device="cpu", compute_type="int8")
        rtf_values: list[float] = []
        total_dur = 0.0
        total_decode = 0.0

        for audio_path in paths:
            try:
                audio, sr = sf.read(str(audio_path))
                dur = len(audio) / sr
                t0 = time.perf_counter()
                segments, _ = model.transcribe(audio)
                for _ in segments:
                    pass
                decode_t = time.perf_counter() - t0
                rtf_values.append(decode_t / dur)
                total_dur += dur
                total_decode += decode_t
            except Exception:
                continue

        return {
            "rtf": rtf(total_dur, total_decode),
            "per_clip_rtf": rtf_values,
            "num_clips": len(rtf_values),
            "total_duration_s": total_dur,
            "total_decode_s": total_decode,
        }

    def measure_noise_robustness(
        self,
        clean_dir: Path,
        noise_dir: Path | None = None,
        engine_name: str = "tiny",
        max_clips: int = 30,
        snr_levels: list[float] | None = None,
    ) -> dict[str, Any]:
        """Measure WER at multiple SNR levels. Returns degradation curve."""
        import numpy as np
        import soundfile as sf
        from faster_whisper import WhisperModel

        snr_levels = snr_levels or [float("inf"), 20.0, 10.0, 5.0, 0.0]
        pairs = load_clip_transcript_pairs(clean_dir, max_clips=max_clips)
        if not pairs:
            return {"error": "no clips with transcripts found"}

        # Load noise samples
        noise_dir = noise_dir or generate_synthetic_noise(self.cache_dir)
        noise_paths = sorted(noise_dir.rglob("*.wav"))
        if not noise_paths:
            return {"error": "no noise samples found"}

        model = WhisperModel(engine_name, device="cpu", compute_type="int8")
        results: dict[str, float] = {}
        noise_idx = 0

        for snr in snr_levels:
            refs: list[str] = []
            hyps: list[str] = []

            for audio_path, ref_text in pairs:
                audio, sr = sf.read(str(audio_path))
                audio = audio.astype(np.float32)

                if snr == float("inf"):
                    noisy = audio
                else:
                    noise, _ = sf.read(str(noise_paths[noise_idx % len(noise_paths)]))
                    noise = noise.astype(np.float32)

                    # Trim or pad noise to match audio length
                    if len(noise) < len(audio):
                        reps = int(np.ceil(len(audio) / len(noise)))
                        noise = np.tile(noise, reps)
                    noise = noise[: len(audio)]

                    # Scale noise to achieve target SNR
                    signal_rms = np.sqrt(np.mean(audio**2)) + 1e-10
                    noise_rms = np.sqrt(np.mean(noise**2)) + 1e-10
                    desired_noise_rms = signal_rms / (10 ** (snr / 20))
                    noise = noise * (desired_noise_rms / (noise_rms + 1e-10))
                    noisy = audio + noise
                    noise_idx += 1

                segments, _ = model.transcribe(noisy)
                hyp_text = " ".join(s.text.strip() for s in segments)
                refs.append(ref_text.lower())
                hyps.append(hyp_text.lower())

            snr_label = "clean" if snr == float("inf") else f"snr_{int(snr)}db"
            results[snr_label] = wer(refs, hyps)

        return {"wer_by_snr": results, "num_clips": len(pairs)}

    def measure_speaker_equity(
        self,
        eval_dir: Path,
        engine_name: str = "tiny",
        max_clips: int = 100,
    ) -> dict[str, Any]:
        """Measure per-speaker WER variance on LibriSpeech."""
        import numpy as np
        from faster_whisper import WhisperModel

        # LibriSpeech structure: speaker_id/chapter_id/*.flac
        pairs = load_clip_transcript_pairs(eval_dir, max_clips=max_clips)
        if not pairs:
            return {"error": "no clips found"}

        # Group by speaker (parent directory = chapter, grandparent = speaker)
        speaker_clips: dict[str, list[tuple[Path, str]]] = {}
        for audio_path, ref in pairs:
            speaker = audio_path.parent.parent.name if audio_path.parent.parent else "unknown"
            speaker_clips.setdefault(speaker, []).append((audio_path, ref))

        model = WhisperModel(engine_name, device="cpu", compute_type="int8")
        per_speaker_wer: dict[str, float] = {}

        for speaker, clips in speaker_clips.items():
            refs: list[str] = []
            hyps: list[str] = []
            for audio_path, ref_text in clips:
                segments, _ = model.transcribe(str(audio_path), beam_size=5)
                hyp_text = " ".join(s.text.strip() for s in segments)
                refs.append(ref_text.lower())
                hyps.append(hyp_text.lower())
            if refs:
                per_speaker_wer[speaker] = wer(refs, hyps)

        values = list(per_speaker_wer.values())
        if len(values) < 2:
            return {"per_speaker_wer": per_speaker_wer, "error": "need at least 2 speakers"}

        arr = np.array(values)
        return {
            "per_speaker_wer": per_speaker_wer,
            "mean_wer": float(np.mean(arr)),
            "std_wer": float(np.std(arr, ddof=1)),
            "min_wer": float(np.min(arr)),
            "max_wer": float(np.max(arr)),
            "spread": float(np.max(arr) - np.min(arr)),
            "num_speakers": len(values),
        }

    def measure_data_efficiency(
        self,
        train_dir: Path,
        eval_dir: Path,
        engine_name: str = "tiny",
        data_minutes: list[float] | None = None,
    ) -> dict[str, Any]:
        """Measure WER at different amounts of training data."""
        data_minutes = data_minutes or [5, 15, 30, 60, 120]
        return {
            "data_minutes": data_minutes,
            "wer_by_minutes": {},
            "status": "skipped — training needed, use scripts/sota/validate_d05_data_efficiency.py",
        }

    def measure_director_accuracy(
        self,
        train_dir: Path,
        eval_dir: Path,
    ) -> dict[str, Any]:
        """Compare director picks vs. oracle (best of all options)."""
        return {
            "oracle_match_rate": -1.0,
            "status": "skipped — exhaustive sweep needed (validate_d13)",
        }

    def measure_export_fidelity(
        self,
        eval_dir: Path,
        engine_name: str = "tiny",
        max_clips: int = 50,
    ) -> dict[str, Any]:
        """WER drift from CT2-float32 to CT2-int8 on the same clips (D08).

        This measures the int8 *quantization* delta only — one of the three export
        targets the domain's bands name (ONNX fp16, safetensors). The float32
        reference is itself CTranslate2-float32, not the original PyTorch fp32 base.
        Hence the result is scope-partial and excluded from the headline.
        """
        from faster_whisper import WhisperModel

        pairs = load_clip_transcript_pairs(eval_dir, max_clips=max_clips)
        if not pairs:
            return {"wer_delta_export": -1.0, "num_clips": 0, "error": "no clips found"}

        def _wer_at(compute_type: str) -> float:
            model = WhisperModel(engine_name, device="cpu", compute_type=compute_type)
            refs: list[str] = []
            hyps: list[str] = []
            for audio_path, ref_text in pairs:
                segments, _ = model.transcribe(str(audio_path), beam_size=5)
                hyps.append(" ".join(s.text.strip() for s in segments).lower())
                refs.append(ref_text.lower())
            return wer(refs, hyps)

        wer_fp32 = _wer_at("float32")
        wer_int8 = _wer_at("int8")
        return {
            "wer_delta_export": abs(wer_int8 - wer_fp32),
            "wer_ct2_float32": wer_fp32,
            "wer_ct2_int8": wer_int8,
            "num_clips": len(pairs),
            "partial": "int8 quantization only (1 of 3 export targets; "
            "baseline is CT2-float32, not PyTorch fp32)",
        }

    def measure_decoding(
        self,
        eval_dir: Path,
        engine_name: str = "tiny",
        max_clips: int = 30,
        beam_sizes: tuple[int, ...] = (1, 5),
    ) -> dict[str, Any]:
        """Best WER across a beam-size sweep on read speech (D10).

        No hotword/OOV biasing on a domain-vocab set is measured (none exists),
        so this is scope-partial: it validates the decoder sweep, not the full
        domain-decoding claim.
        """
        from faster_whisper import WhisperModel

        pairs = load_clip_transcript_pairs(eval_dir, max_clips=max_clips)
        if not pairs:
            return {"domain_wer_optimal": -1.0, "num_clips": 0, "error": "no clips found"}

        model = WhisperModel(engine_name, device="cpu", compute_type="int8")
        wer_by_beam: dict[str, float] = {}
        for beam in beam_sizes:
            refs: list[str] = []
            hyps: list[str] = []
            for audio_path, ref_text in pairs:
                segments, _ = model.transcribe(str(audio_path), beam_size=beam)
                hyps.append(" ".join(s.text.strip() for s in segments).lower())
                refs.append(ref_text.lower())
            wer_by_beam[f"wer_beam_{beam}"] = wer(refs, hyps)

        best_key = min(wer_by_beam, key=lambda k: wer_by_beam[k])
        return {
            "domain_wer_optimal": wer_by_beam[best_key],
            "best_beam": int(best_key.rsplit("_", 1)[1]),
            **wer_by_beam,
            "num_clips": len(pairs),
            "partial": "beam sweep on general read speech only; "
            "no hotword/OOV domain-vocab biasing",
        }

    def measure_longform(
        self,
        eval_dir: Path,
        engine_name: str = "tiny",
        target_minutes: float = 10.0,
    ) -> dict[str, Any]:
        """WER drift from short clips to one concatenated long recording (D11).

        The long recording is built by concatenating read-speech clips up to
        ``target_minutes`` (a proxy shorter than the 60-min domain target, and not
        naturally continuous speech), so the result is scope-partial.
        """
        import numpy as np
        import soundfile as sf
        from faster_whisper import WhisperModel

        pairs = load_clip_transcript_pairs(eval_dir, max_clips=1000)
        if not pairs:
            return {"wer_delta_60min": -1.0, "num_clips": 0, "error": "no clips found"}

        model = WhisperModel(engine_name, device="cpu", compute_type="int8")
        target_s = target_minutes * 60.0
        arrays: list[Any] = []
        refs_short: list[str] = []
        hyps_short: list[str] = []
        total_s = 0.0

        for audio_path, ref_text in pairs:
            audio, sr = sf.read(str(audio_path))
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            audio = audio.astype(np.float32)
            segments, _ = model.transcribe(audio, beam_size=5)
            hyps_short.append(" ".join(s.text.strip() for s in segments).lower())
            refs_short.append(ref_text.lower())
            arrays.append(audio)
            total_s += len(audio) / sr
            if total_s >= target_s:
                break

        wer_short = wer(refs_short, hyps_short)
        long_audio = np.concatenate(arrays)
        long_ref = " ".join(refs_short)  # already lower-cased
        segments, _ = model.transcribe(long_audio, beam_size=5)
        long_hyp = " ".join(s.text.strip() for s in segments).lower()
        wer_long = wer([long_ref], [long_hyp])

        minutes = round(total_s / 60.0, 2)
        return {
            "wer_delta_60min": abs(wer_long - wer_short),
            "wer_short_clips": wer_short,
            "wer_longform": wer_long,
            "longform_minutes": minutes,
            "num_clips": len(arrays),
            "partial": f"proxy: {minutes} min of concatenated read speech, "
            "not 60 min of naturally continuous audio",
        }

    def measure_resource_efficiency(
        self,
        eval_dir: Path,
        engine_name: str = "tiny",
        max_clips: int = 20,
    ) -> dict[str, Any]:
        """Model disk footprint + peak RAM over some audio-minutes (D15).

        Scores the standing model disk footprint (the domain's SOTA anchor is
        "~50 MB disk"); peak RSS is reported but not scored, and the marginal
        per-audio-minute pipeline storage is not yet accounted — hence partial.
        """
        import os

        import psutil
        import soundfile as sf
        from faster_whisper import WhisperModel, download_model

        paths = (
            sorted(eval_dir.rglob("*.flac"))[:max_clips]
            or sorted(eval_dir.rglob("*.wav"))[:max_clips]
        )
        if not paths:
            return {"mb_per_audio_minute": -1.0, "num_clips": 0, "error": "no audio files found"}

        model_dir = Path(download_model(engine_name))
        disk_mb = sum(f.stat().st_size for f in model_dir.rglob("*") if f.is_file()) / (1024 * 1024)

        proc = psutil.Process(os.getpid())
        rss_before = proc.memory_info().rss
        model = WhisperModel(engine_name, device="cpu", compute_type="int8")
        peak_rss = proc.memory_info().rss
        total_audio_s = 0.0
        for p in paths:
            audio, sr = sf.read(str(p))
            total_audio_s += len(audio) / sr
            segments, _ = model.transcribe(str(p))
            for _ in segments:
                pass
            peak_rss = max(peak_rss, proc.memory_info().rss)

        return {
            "mb_per_audio_minute": disk_mb,  # standing model disk footprint (see partial note)
            "model_disk_mb": disk_mb,
            "peak_rss_mb": peak_rss / (1024 * 1024),
            "rss_delta_mb": (peak_rss - rss_before) / (1024 * 1024),
            "audio_minutes": round(total_audio_s / 60.0, 3),
            "num_clips": len(paths),
            "partial": "model disk footprint scored (per SOTA anchor); "
            "peak RAM reported not scored; marginal per-audio-min storage not accounted",
        }

    def run_domain(self, domain: Domain) -> SOTAResult:
        """Run a single domain benchmark and return a scored result."""
        import subprocess

        engine = normalize_engine(self.engines[0] if self.engines else "tiny")

        try:
            git_commit = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], text=True
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            git_commit = "unknown"

        result = SOTAResult(
            domain_id=domain.id,
            domain_name=domain.name,
            score_0_1000=0,
            band="unmeasured",
            sota_ref=domain.sota_1000_reference,
            engine_used=engine,
            git_commit=git_commit,
        )

        # Dispatch to the right measurement
        metrics: dict[str, Any] = {}
        notes = ""

        try:
            data_paths = self.ensure_data(domain) if domain.data_filter else {}

            if domain.id == "d01_wer_clean":
                eval_dir = data_paths.get("librispeech_test_clean")
                if eval_dir:
                    m = self.measure_base_wer(eval_dir, engine, max_clips=domain.min_samples)
                    metrics["wer"] = m["wer"]
                    metrics["cer"] = m.get("cer", -1.0)
                    metrics["num_clips"] = m.get("num_clips", 0)
                    if "ci_95_wer" in m:
                        result.confidence_95["wer"] = m["ci_95_wer"]
                else:
                    notes = (
                        "librispeech_test_clean not downloaded — run scripts/sota/download_data.sh"
                    )

            elif domain.id == "d02_wer_spontaneous":
                eval_dir = data_paths.get("common_voice_en")
                if eval_dir:
                    m = self.measure_base_wer(eval_dir, engine, max_clips=domain.min_samples)
                    metrics["wer"] = m["wer"]
                    metrics["cer"] = m.get("cer", -1.0)
                    metrics["num_clips"] = m.get("num_clips", 0)
                    if "ci_95_wer" in m:
                        result.confidence_95["wer"] = m["ci_95_wer"]
                else:
                    notes = "common_voice_en not downloaded"

            elif domain.id == "d04_rtf":
                eval_dir = data_paths.get("librispeech_test_clean")
                if eval_dir:
                    m = self.measure_rtf(eval_dir, engine, max_clips=20)
                    metrics["rtf"] = m["rtf"]
                    metrics["num_clips"] = m.get("num_clips", 0)
                else:
                    notes = "librispeech_test_clean not downloaded"

            elif domain.id == "d06_noise_robustness":
                clean_dir = data_paths.get("librispeech_test_clean")
                noise_dir = data_paths.get("synthetic_noise")
                if clean_dir:
                    m = self.measure_noise_robustness(clean_dir, noise_dir, engine)
                    if "wer_by_snr" in m:
                        metrics.update(m["wer_by_snr"])
                        metrics["num_clips"] = m.get("num_clips", 0)
                        clean_wer = m["wer_by_snr"].get("clean", 0)
                        snr0_wer = m["wer_by_snr"].get("snr_0db", 0)
                        if clean_wer > 0 and snr0_wer > 0:
                            metrics["wer_delta_at_0db"] = snr0_wer - clean_wer
                    else:
                        notes = m.get("error", "measurement failed")
                else:
                    notes = "librispeech_test_clean not downloaded"

            elif domain.id == "d12_speaker_equity":
                eval_dir = data_paths.get("librispeech_test_clean")
                if eval_dir:
                    m = self.measure_speaker_equity(eval_dir, engine, max_clips=domain.min_samples)
                    metrics["per_speaker_wer_std"] = m.get("std_wer", -1.0)
                    metrics["speaker_wer_spread"] = m.get("spread", -1.0)
                    metrics["num_speakers"] = m.get("num_speakers", 0)
                else:
                    notes = "librispeech_test_clean not downloaded"

            elif domain.id == "d08_export_fidelity":
                eval_dir = data_paths.get("librispeech_test_clean")
                if eval_dir:
                    m = self.measure_export_fidelity(eval_dir, engine, max_clips=domain.min_samples)
                    metrics.update(m)
                else:
                    notes = "librispeech_test_clean not downloaded"

            elif domain.id == "d10_decoding":
                eval_dir = data_paths.get("librispeech_test_clean")
                if eval_dir:
                    m = self.measure_decoding(eval_dir, engine, max_clips=domain.min_samples)
                    metrics.update(m)
                else:
                    notes = "librispeech_test_clean not downloaded"

            elif domain.id == "d11_longform":
                eval_dir = data_paths.get("librispeech_test_clean")
                if eval_dir:
                    m = self.measure_longform(eval_dir, engine)
                    metrics.update(m)
                else:
                    notes = "librispeech_test_clean not downloaded"

            elif domain.id == "d15_resource_efficiency":
                eval_dir = data_paths.get("librispeech_test_clean")
                if eval_dir:
                    m = self.measure_resource_efficiency(
                        eval_dir, engine, max_clips=domain.min_samples
                    )
                    metrics.update(m)
                else:
                    notes = "librispeech_test_clean not downloaded"

            elif domain.id == "d05_data_efficiency":
                notes = "Requires training at multiple data sizes — use validate_d05 script"
                metrics["wer_at_5min"] = -1.0

            elif domain.id == "d13_director_accuracy":
                notes = "Requires exhaustive oracle sweep — use validate_d13 script"
                metrics["oracle_match_rate"] = -1.0

            elif domain.id == "d14_quality_gate":
                notes = "Requires hand-labelled quality set — use validate_d14 script"
                metrics["quality_gate_auc"] = -1.0

            else:
                notes = f"Domain {domain.id} requires dedicated validation script"

            result.metrics = {
                k: float(v) if isinstance(v, float) else v for k, v in metrics.items()
            }
            result.num_samples = int(metrics.get("num_clips", metrics.get("num_speakers", 0)))
            result.notes = notes

            # Score against bands
            primary_metric = domain.metric
            value = None
            for key in metrics:
                if primary_metric in key or key == primary_metric:
                    v = metrics[key]
                    if isinstance(v, (int, float)) and v >= 0:
                        value = float(v)
                        break

            if value is not None and domain.bands:
                band_tuples = [(b.score, b.threshold) for b in domain.bands]
                score, band = score_against_bands(value, band_tuples, domain.higher_is_better)
                result.score_0_1000 = score
                result.band = band
            elif notes and "not downloaded" in notes:
                result.band = "unmeasured"
            elif notes:
                result.band = "pending"

        except Exception as e:
            result.notes = f"Error: {e}"
            result.band = "error"

        return result

    def run_all(
        self,
        domains: list[Domain] | None = None,
        cpu_only: bool = True,
    ) -> Scoreboard:
        """Run all requested domains and produce a scoreboard."""
        domains = domains or ALL_DOMAINS
        if cpu_only:
            domains = [d for d in domains if d.runnable_cpu]

        results: list[SOTAResult] = []
        for domain in domains:
            print(f"[sota] Running {domain.id}: {domain.name}...")
            result = self.run_domain(domain)
            print(f"  → Score: {result.score_0_1000}/1000  Band: {result.band}")
            if result.notes:
                print(f"  → {result.notes}")
            results.append(result)

        # Honest headline: mean over adequately-powered domains only, with
        # under-powered results flagged "directional" and excluded (see
        # scoring.aggregate_headline). This also annotates each result in place.
        headline = aggregate_headline(results)

        return Scoreboard(
            domains=results,
            overall_mean=headline["overall_mean"],
            overall_band=headline["overall_band"],
            num_total=headline["num_total"],
            num_measured=headline["num_measured"],
            num_eligible=headline["num_eligible"],
            num_directional=headline["num_directional"],
            num_unmeasured=headline["num_unmeasured"],
        )
