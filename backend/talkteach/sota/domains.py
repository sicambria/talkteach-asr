"""15 SOTA benchmark domains — each with metric, method, band thresholds, and SOTA=1000 anchor.

Every threshold is anchored to a real-world production ASR system, not an abstract target.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Band:
    """A scoring band: (score, threshold_value, description)."""

    score: int
    threshold: float
    description: str


@dataclass
class Domain:
    """One SOTA benchmark domain."""

    id: str  # "d01_wer_clean"
    name: str  # "ASR Accuracy — Clean Speech"
    metric: str  # "wer" | "rtf" | "coverage" | ...
    description: str  # what it measures and why
    higher_is_better: bool  # False for WER/CER/RTF, True for coverage/rate
    bands: list[Band]  # sorted by score descending
    sota_1000_reference: str  # what real-world system achieves 1000
    engine_filter: list[str] = field(default_factory=list)  # applicable engine names
    data_filter: list[str] = field(default_factory=list)  # required datasets
    runnable_cpu: bool = True  # can run without GPU?
    min_samples: int = 50  # minimum eval clips for statistical validity


ALL_DOMAINS: list[Domain] = [
    # ── D01: ASR Accuracy — Clean Speech ──
    Domain(
        id="d01_wer_clean",
        name="ASR Accuracy — Clean Speech",
        metric="wer",
        description="WER on LibriSpeech test-clean (read speech, studio quality). "
        "The most cited ASR benchmark. SOTA=1000: whisper-large-v3 at ~1.8% WER.",
        higher_is_better=False,
        bands=[
            Band(1000, 0.010, "WER ≤ 1.0% — surpasses best known production ASR"),
            Band(950, 0.015, "WER ≤ 1.5% — whisper-large-v3 territory"),
            Band(900, 0.020, "WER ≤ 2.0% — near whisper-large-v3"),
            Band(800, 0.030, "WER ≤ 3.0% — strong fine-tuned OSS"),
            Band(700, 0.050, "WER ≤ 5.0% — usable for clean speech applications"),
            Band(600, 0.080, "WER ≤ 8.0% — functional baseline"),
        ],
        sota_1000_reference="whisper-large-v3 @ 1.8% WER on LibriSpeech test-clean (OpenAI, 2023)",
        engine_filter=["whisper_lora", "wav2vec2_ctc"],
        data_filter=["librispeech_test_clean"],
        runnable_cpu=True,
        min_samples=100,
    ),
    # ── D02: ASR Accuracy — Spontaneous Speech ──
    Domain(
        id="d02_wer_spontaneous",
        name="ASR Accuracy — Spontaneous/Conversational Speech",
        metric="wer",
        description="WER on Common Voice English test (accented, spontaneous, diverse mics). "
        "Measures real-world robustness beyond studio-quality read speech.",
        higher_is_better=False,
        bands=[
            Band(1000, 0.030, "WER ≤ 3.0% — best commercial API on conversational speech"),
            Band(950, 0.040, "WER ≤ 4.0% — excellent real-world performance"),
            Band(900, 0.050, "WER ≤ 5.0% — pro-grade conversational ASR"),
            Band(800, 0.080, "WER ≤ 8.0% — solid OSS on spontaneous speech"),
            Band(700, 0.120, "WER ≤ 12.0% — usable for many real-world tasks"),
            Band(600, 0.180, "WER ≤ 18.0% — functional baseline on diverse audio"),
        ],
        sota_1000_reference="Best commercial APIs on Common Voice en",
        engine_filter=["whisper_lora", "wav2vec2_ctc"],
        data_filter=["common_voice_en"],
        runnable_cpu=True,
        min_samples=100,
    ),
    # ── D03: Training Efficiency ──
    Domain(
        id="d03_train_efficiency",
        name="Training Efficiency — Time-to-Convergence",
        metric="gpu_hours",
        description="Normalized GPU-hours to reach 90% of final WER on 1 hour of training data. "
        "CPU hours are converted via a 10× factor (CPU ≈ 10× slower than A100 for Whisper).",
        higher_is_better=False,
        bands=[
            Band(1000, 0.3, "≤ 0.3 GPU-hours — near-instant fine-tuning"),
            Band(950, 0.5, "≤ 0.5 GPU-hours — whisper-tiny on A100 converges in ~10 min"),
            Band(900, 1.0, "≤ 1.0 GPU-hour — efficient fine-tune"),
            Band(800, 2.0, "≤ 2.0 GPU-hours — reasonable training time"),
            Band(700, 4.0, "≤ 4.0 GPU-hours — moderate cost"),
            Band(600, 8.0, "≤ 8.0 GPU-hours — trainable on a single GPU overnight"),
        ],
        sota_1000_reference="whisper-tiny LoRA on A100: ~0.17 GPU-hr to converge on 1hr data",
        engine_filter=["whisper_lora", "wav2vec2_ctc"],
        data_filter=["librispeech_train_clean_100"],
        runnable_cpu=True,
        min_samples=5,
    ),
    # ── D04: Inference Speed ──
    Domain(
        id="d04_rtf",
        name="Inference Speed — Real-Time Factor",
        metric="rtf",
        description="Real-Time Factor = decode_time / audio_duration on LibriSpeech test-clean. "
        "RTF < 1 means faster than real-time. RTF < 0.1 == 10× real-time.",
        higher_is_better=False,
        bands=[
            Band(1000, 0.01, "RTF ≤ 0.01 — 100× real-time, edge-device capable"),
            Band(950, 0.02, "RTF ≤ 0.02 — faster-whisper CTranslate2 int8 territory"),
            Band(900, 0.05, "RTF ≤ 0.05 — excellent throughput"),
            Band(800, 0.10, "RTF ≤ 0.10 — strong real-time performance"),
            Band(700, 0.30, "RTF ≤ 0.30 — usable for batch processing"),
            Band(600, 1.00, "RTF ≤ 1.00 — real-time capable"),
        ],
        sota_1000_reference="faster-whisper CT2 int8 tiny @ RTF ~0.02 on modern CPU",
        engine_filter=["whisper_lora"],
        data_filter=["librispeech_test_clean"],
        runnable_cpu=True,
        min_samples=100,
    ),
    # ── D05: Data Efficiency ──
    Domain(
        id="d05_data_efficiency",
        name="Data Efficiency — WER vs. Training Minutes",
        metric="wer_at_5min",
        description="WER achieved with 5 minutes of training data on LibriSpeech. "
        "Measures few-shot adaptation capability — critical for users with limited recordings.",
        higher_is_better=False,
        bands=[
            Band(1000, 0.05, "5min→WER≤5%, 1hr→WER≤2% — exceptional few-shot learning"),
            Band(950, 0.07, "5min→WER≤7%, 1hr→WER≤3% — strong few-shot"),
            Band(900, 0.10, "5min→WER≤10%, 1hr→WER≤4% — good data efficiency"),
            Band(800, 0.15, "5min→WER≤15%, 1hr→WER≤6% — usable adaptation"),
            Band(700, 0.20, "5min→WER≤20%, 1hr→WER≤10% — moderate data needs"),
            Band(600, 0.30, "5min→WER≤30%, 1hr→WER≤15% — high data requirement"),
        ],
        sota_1000_reference="Whisper-LoRA: ~3% WER with 30 min of fine-tuning data (literature)",
        engine_filter=["whisper_lora"],
        data_filter=["librispeech_train_clean_100"],
        runnable_cpu=True,
        min_samples=50,
    ),
    # ── D06: Noise Robustness ──
    Domain(
        id="d06_noise_robustness",
        name="Noise Robustness — WER Degradation at 0dB SNR",
        metric="wer_delta_at_0db",
        description="Absolute WER increase from clean to 0dB SNR babble noise. "
        "Measures how badly noise degrades recognition — the smaller the delta, the more robust.",
        higher_is_better=False,
        bands=[
            Band(1000, 0.02, "Δ WER ≤ 2% at 0dB — exceptional noise robustness"),
            Band(950, 0.05, "Δ WER ≤ 5% at 0dB — very robust to noise"),
            Band(900, 0.08, "Δ WER ≤ 8% at 0dB — good noise handling"),
            Band(800, 0.12, "Δ WER ≤ 12% at 0dB — moderate robustness"),
            Band(700, 0.20, "Δ WER ≤ 20% at 0dB — noise-sensitive"),
            Band(600, 0.30, "Δ WER ≤ 30% at 0dB — severely degraded by noise"),
        ],
        sota_1000_reference="Denoised Whisper + DeepFilterNet: Δ<3% at 0dB SNR (research)",
        engine_filter=["whisper_lora"],
        data_filter=["librispeech_test_clean", "wham_noise"],
        runnable_cpu=True,
        min_samples=50,
    ),
    # ── D07: Multilingual Coverage ──
    Domain(
        id="d07_multilingual",
        name="Multilingual Coverage — Languages with WER < 15%",
        metric="languages_under_15pct_wer",
        description="Number of languages on FLEURS test where WER < 15%. "
        "Higher is better. SOTA=1000 means 80+ languages covered with usable accuracy.",
        higher_is_better=True,
        bands=[
            Band(1000, 80, "≥ 80 languages < 15% WER — near-universal ASR"),
            Band(950, 60, "≥ 60 languages — whisper-large-v3 territory"),
            Band(900, 40, "≥ 40 languages — strong multilingual"),
            Band(800, 20, "≥ 20 languages — solid coverage"),
            Band(700, 10, "≥ 10 languages — basic multilingual"),
            Band(600, 5, "≥ 5 languages — minimal multilingual support"),
        ],
        sota_1000_reference="whisper-large-v3: ~60 langs <15% WER on FLEURS (OpenAI 2023)",
        engine_filter=["whisper_lora"],
        data_filter=["fleurs"],
        runnable_cpu=True,
        min_samples=100,
    ),
    # ── D08: Export Portability ──
    Domain(
        id="d08_export_fidelity",
        name="Export Portability — Quantization WER Fidelity",
        metric="wer_delta_export",
        description="Absolute WER increase from fp32 base model to each export format "
        "(CTranslate2 int8, ONNX fp16, safetensors). Smaller is better.",
        higher_is_better=False,
        bands=[
            Band(1000, 0.001, "Δ WER ≤ 0.1% for all export targets — lossless quantization"),
            Band(950, 0.003, "Δ WER ≤ 0.3% — negligible export loss"),
            Band(900, 0.005, "Δ WER ≤ 0.5% — minimal quality degradation"),
            Band(800, 0.010, "Δ WER ≤ 1.0% — acceptable trade-off"),
            Band(700, 0.020, "Δ WER ≤ 2.0% — noticeable but usable"),
            Band(600, 0.050, "Δ WER ≤ 5.0% — significant quality loss"),
        ],
        sota_1000_reference="CTranslate2 int8: Δ WER < 0.1% vs fp32 (CTranslate2 docs)",
        engine_filter=["whisper_lora"],
        data_filter=["librispeech_test_clean"],
        runnable_cpu=True,
        min_samples=50,
    ),
    # ── D09: Augmentation Efficacy ──
    Domain(
        id="d09_augmentation",
        name="Augmentation Efficacy — Relative WER Reduction at 5 min Data",
        metric="rel_wer_reduction_5min",
        description="Relative WER reduction from SpecAugment + speed/pitch/noise augmentation "
        "at 5 min of training data. Higher is better — helps most when data is scarce.",
        higher_is_better=True,
        bands=[
            Band(1000, 0.30, "≥ 30% relative WER reduction — exceptional augmentation benefit"),
            Band(950, 0.25, "≥ 25% — strong augmentation impact"),
            Band(900, 0.20, "≥ 20% — good augmentation efficacy"),
            Band(800, 0.15, "≥ 15% — useful augmentation"),
            Band(700, 0.10, "≥ 10% — modest benefit"),
            Band(600, 0.05, "≥ 5% — marginal improvement"),
        ],
        sota_1000_reference="SpecAugment: ~20% rel WER reduction on small data (Park et al. 2019)",
        engine_filter=["whisper_lora", "wav2vec2_ctc"],
        data_filter=["librispeech_train_clean_100"],
        runnable_cpu=True,
        min_samples=50,
    ),
    # ── D10: Decoding Quality ──
    Domain(
        id="d10_decoding",
        name="Decoding Quality — Optimal Beam + Hotword Bias",
        metric="domain_wer_optimal",
        description="WER with optimal beam + hotword biasing on a domain vocab set. "
        "Also measures OOV error reduction from hotword biasing.",
        higher_is_better=False,
        bands=[
            Band(1000, 0.01, "Domain WER ≤ 1.0% with bias, OOV errors reduced ≥ 50%"),
            Band(950, 0.02, "Domain WER ≤ 2.0%, OOV ≥ 40%"),
            Band(900, 0.03, "Domain WER ≤ 3.0%, OOV ≥ 30%"),
            Band(800, 0.05, "Domain WER ≤ 5.0%, OOV ≥ 20%"),
            Band(700, 0.08, "Domain WER ≤ 8.0%, OOV ≥ 10%"),
            Band(600, 0.12, "Domain WER ≤ 12.0%, OOV > 0%"),
        ],
        sota_1000_reference="Beam=5 + hotword on whisper-tiny: marginal gain on general speech",
        engine_filter=["whisper_lora"],
        data_filter=["librispeech_test_clean"],
        runnable_cpu=True,
        min_samples=30,
    ),
    # ── D11: Long-Form Reliability ──
    Domain(
        id="d11_longform",
        name="Long-Form Reliability — WER at 60 min Continuous Speech",
        metric="wer_delta_60min",
        description="Absolute WER increase from 1-minute clip to a 60-minute continuous recording. "
        "Measures chunked/overlapping-window decoding quality without boundary artifacts.",
        higher_is_better=False,
        bands=[
            Band(1000, 0.005, "Δ WER ≤ 0.5% at 60 min — near-perfect long-form handling"),
            Band(950, 0.010, "Δ WER ≤ 1.0% — excellent chunking"),
            Band(900, 0.020, "Δ WER ≤ 2.0% — good long-form reliability"),
            Band(800, 0.030, "Δ WER ≤ 3.0% — moderate boundary artifacts"),
            Band(700, 0.050, "Δ WER ≤ 5.0% — noticeable degradation"),
            Band(600, 0.080, "Δ WER ≤ 8.0% — significant long-form issues"),
        ],
        sota_1000_reference="Chunked Whisper with overlapping windows: Δ < 1% at 60 min",
        engine_filter=["whisper_lora"],
        data_filter=["librispeech_test_clean"],
        runnable_cpu=True,
        min_samples=10,
    ),
    # ── D12: Speaker/Accent Generalization ──
    Domain(
        id="d12_speaker_equity",
        name="Speaker/Accent Generalization — Per-Speaker WER Variance",
        metric="per_speaker_wer_std",
        description="Standard deviation of per-speaker WER on LibriSpeech test-clean. "
        "Lower σ means the model performs consistently across all speakers. "
        "Also measures max-min WER spread.",
        higher_is_better=False,
        bands=[
            Band(1000, 0.005, "σ ≤ 0.5%, max-min spread ≤ 2.0% — perfect speaker equity"),
            Band(950, 0.010, "σ ≤ 1.0% — excellent consistency across speakers"),
            Band(900, 0.015, "σ ≤ 1.5% — good generalization"),
            Band(800, 0.025, "σ ≤ 2.5% — moderate speaker variation"),
            Band(700, 0.040, "σ ≤ 4.0% — significant variation"),
            Band(600, 0.060, "σ ≤ 6.0% — large speaker-dependent differences"),
        ],
        sota_1000_reference="Best commercial ASR: per-speaker WER σ < 1.5% on LibriSpeech",
        engine_filter=["whisper_lora", "wav2vec2_ctc"],
        data_filter=["librispeech_test_clean"],
        runnable_cpu=True,
        min_samples=100,
    ),
    # ── D13: Director Selection Accuracy ──
    Domain(
        id="d13_director_accuracy",
        name="Director Auto-Selection — Optimal Config Choice Rate",
        metric="oracle_match_rate",
        description="Percentage of (hardware, data, language) scenarios where the director "
        "selects the WER-minimizing config from all available options. "
        "This is the central validation of TalkTeach's 'zero-config' promise.",
        higher_is_better=True,
        bands=[
            Band(1000, 0.98, "≥ 98% oracle match rate — near-perfect auto-selection"),
            Band(950, 0.95, "≥ 95% — excellent director accuracy"),
            Band(900, 0.90, "≥ 90% — strong auto-selection, few mistakes"),
            Band(800, 0.80, "≥ 80% — good, but leaves some gains on the table"),
            Band(700, 0.65, "≥ 65% — better than random, needs calibration"),
            Band(600, 0.50, "≥ 50% — marginally better than coin flip"),
        ],
        sota_1000_reference="Calibrated director: picks WER-minimizing config ≥90% of time",
        engine_filter=["whisper_lora", "wav2vec2_ctc"],
        data_filter=["librispeech_train_clean_100"],
        runnable_cpu=True,
        min_samples=20,
    ),
    # ── D14: Quality Gate Precision ──
    Domain(
        id="d14_quality_gate",
        name="Data Quality Gate — ROC-AUC vs. Human Labels",
        metric="quality_gate_auc",
        description="ROC-AUC of the audio quality gate (SNR + clipping + silence checks) "
        "against human GOOD/BAD labels. Also: Pearson r between quality score and downstream WER. "
        "The gate should accept good clips and reject bad ones accurately.",
        higher_is_better=True,
        bands=[
            Band(1000, 0.95, "AUC ≥ 0.95, r ≥ 0.90 — near-perfect quality discrimination"),
            Band(950, 0.92, "AUC ≥ 0.92, r ≥ 0.85 — excellent gate precision"),
            Band(900, 0.88, "AUC ≥ 0.88, r ≥ 0.80 — strong quality prediction"),
            Band(800, 0.82, "AUC ≥ 0.82, r ≥ 0.70 — good discrimination"),
            Band(700, 0.75, "AUC ≥ 0.75, r ≥ 0.60 — moderate, catches obvious bad clips"),
            Band(600, 0.65, "AUC ≥ 0.65, r ≥ 0.50 — better than random, misses many"),
        ],
        sota_1000_reference="SNR-based gate: AUC ~0.88 on Common Voice labelled subset (estimated)",
        engine_filter=[],
        data_filter=["labelled_quality_set"],
        runnable_cpu=True,
        min_samples=200,
    ),
    # ── D15: Resource Efficiency ──
    Domain(
        id="d15_resource_efficiency",
        name="Resource Efficiency — Disk + RAM per Audio Minute",
        metric="mb_per_audio_minute",
        description="Disk (MB) plus RAM-hours per minute of transcribed audio, "
        "covering the full pipeline: import → decode → quality → train → export → inference.",
        higher_is_better=False,
        bands=[
            Band(1000, 10, "≤ 10 MB + 0.5 GB-hr per audio-minute — edge-device capable"),
            Band(950, 20, "≤ 20 MB + 1.0 GB-hr — very lightweight"),
            Band(900, 50, "≤ 50 MB + 2.0 GB-hr — efficient"),
            Band(800, 100, "≤ 100 MB + 5.0 GB-hr — reasonable desktop footprint"),
            Band(700, 200, "≤ 200 MB + 10 GB-hr — moderate resource usage"),
            Band(600, 500, "≤ 500 MB + 20 GB-hr — heavy but functional"),
        ],
        sota_1000_reference="CTranslate2 whisper-tiny: ~50 MB disk, negligible RAM for inference",
        engine_filter=["whisper_lora"],
        data_filter=["librispeech_test_clean"],
        runnable_cpu=True,
        min_samples=20,
    ),
]


def get_domain(domain_id: str) -> Domain | None:
    """Look up a domain by its ID."""
    for d in ALL_DOMAINS:
        if d.id == domain_id:
            return d
    return None
