"""ML safety guardrails — bias detection, hallucination scoring, OOD detection.

Extends NaN-detection (already in _whisper_train.py) with production-grade guardrails
that should run automatically during training and flag issues before the model ships.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GuardrailResult:
    """Result of a single guardrail check."""

    name: str  # e.g. "bias_detection", "hallucination_rate"
    passed: bool
    severity: str  # "critical" | "warning" | "info"
    value: float | None = None
    threshold: float | None = None
    detail: str = ""
    recommendation: str = ""


@dataclass
class GuardrailReport:
    """Aggregate report from all guardrail checks."""

    all_passed: bool = True
    results: list[GuardrailResult] = field(default_factory=list)
    critical_count: int = 0
    warning_count: int = 0

    @property
    def summary(self) -> str:
        if self.all_passed:
            return "All guardrails passed"
        parts: list[str] = []
        if self.critical_count:
            parts.append(f"{self.critical_count} CRITICAL")
        if self.warning_count:
            parts.append(f"{self.warning_count} WARNING")
        return f"Guardrail failures: {', '.join(parts)}"


def check_nan_gradient(loss_value: float, grad_norm: float | None = None) -> GuardrailResult:
    """Check for NaN/Inf in loss or gradients (already in training loop, codified here)."""
    import math

    loss_ok = not (math.isnan(loss_value) or math.isinf(loss_value))
    grad_ok = grad_norm is None or not (math.isnan(grad_norm) or math.isinf(grad_norm))

    if not loss_ok:
        return GuardrailResult(
            name="nan_loss",
            passed=False,
            severity="critical",
            value=loss_value,
            detail=f"Loss is {loss_value}",
            recommendation="Roll back to last good checkpoint and reduce learning rate",
        )
    if not grad_ok:
        return GuardrailResult(
            name="nan_gradient",
            passed=False,
            severity="critical",
            value=grad_norm,
            detail=f"Gradient norm is {grad_norm}",
            recommendation="Enable gradient clipping, reduce learning rate",
        )
    return GuardrailResult(name="nan_check", passed=True, severity="info")


def check_bias_demographic(
    per_group_wer: dict[str, float],
    max_gap: float = 0.15,
) -> GuardrailResult:
    """Check for demographic bias: max WER gap between groups should not exceed max_gap.

    per_group_wer: dict mapping demographic group name → WER
    max_gap: maximum acceptable absolute WER difference between best and worst group
    """
    if len(per_group_wer) < 2:
        return GuardrailResult(
            name="bias_demographic",
            passed=True,
            severity="info",
            detail="Fewer than 2 demographic groups; bias check skipped",
        )

    values = list(per_group_wer.values())
    min_wer = min(values)
    max_wer = max(values)
    gap = max_wer - min_wer

    passed = gap <= max_gap
    return GuardrailResult(
        name="bias_demographic",
        passed=passed,
        severity="warning" if not passed else "info",
        value=gap,
        threshold=max_gap,
        detail=f"WER gap between best ({min_wer:.3f}) and worst ({max_wer:.3f}) group: {gap:.3f}",
        recommendation=(
            "Consider collecting more data for underrepresented groups" if not passed else ""
        ),
    )


def check_hallucination_rate(
    transcript: str,
    audio_duration_s: float,
    max_repetition_ratio: float = 0.3,
    min_words_per_second: float = 0.5,
    max_words_per_second: float = 5.0,
) -> GuardrailResult:
    """Check for hallucination: repetitive text, abnormally fast/slow output.

    transcript: the decoded text
    audio_duration_s: duration of the audio in seconds
    """
    words = transcript.lower().split()
    n_words = len(words)

    if n_words == 0:
        return GuardrailResult(
            name="hallucination_empty",
            passed=True,
            severity="info",
            detail="Empty transcript",
        )

    wps = n_words / audio_duration_s if audio_duration_s > 0 else 0

    # Check repetition
    if n_words >= 5:
        bigrams: dict[str, int] = {}
        for i in range(len(words) - 1):
            bg = f"{words[i]} {words[i + 1]}"
            bigrams[bg] = bigrams.get(bg, 0) + 1
        max_repeat = max(bigrams.values()) if bigrams else 1
        repeat_ratio = max_repeat / n_words
    else:
        repeat_ratio = 0.0

    issues: list[str] = []
    passed = True

    if repeat_ratio > max_repetition_ratio:
        issues.append(f"High repetition ratio: {repeat_ratio:.2f}")
        passed = False

    if wps < min_words_per_second:
        issues.append(f"Output too slow: {wps:.1f} wps (min {min_words_per_second})")
        passed = False

    if wps > max_words_per_second:
        issues.append(f"Output too fast (possible hallucination): {wps:.1f} wps")
        passed = False

    return GuardrailResult(
        name="hallucination_check",
        passed=passed,
        severity="warning" if not passed else "info",
        value=repeat_ratio,
        detail="; ".join(issues) if issues else f"OK (wps={wps:.1f}, repeat={repeat_ratio:.2f})",
        recommendation="Model may be hallucinating — check training data and hyperparameters"
        if not passed
        else "",
    )


def check_data_leakage(
    train_speakers: set[str],
    eval_speakers: set[str],
    train_sentences: set[str] | None = None,
    eval_sentences: set[str] | None = None,
) -> GuardrailResult:
    """Check for data leakage between train and eval sets.

    This is the Mo3 fix — ensuring speaker and sentence disjointness.
    Hard block: training should not proceed if there's overlap.
    """
    speaker_overlap = train_speakers & eval_speakers

    if speaker_overlap:
        return GuardrailResult(
            name="data_leakage_speaker",
            passed=False,
            severity="critical",
            detail=f"Speaker overlap: {len(speaker_overlap)} speakers in both sets",
            recommendation=(
                "Split by SPEAKER, not randomly. "
                "These speakers must be exclusively in train or eval."
            ),
        )

    if train_sentences and eval_sentences:
        sentence_overlap = train_sentences & eval_sentences
        if sentence_overlap:
            return GuardrailResult(
                name="data_leakage_sentence",
                passed=False,
                severity="critical",
                detail=f"Sentence overlap: {len(sentence_overlap)} in both sets",
                recommendation=("Split by sentence hash. Remove overlapping from eval."),
            )

    return GuardrailResult(
        name="data_leakage",
        passed=True,
        severity="info",
        detail=f"Disjoint: {len(train_speakers)} train, {len(eval_speakers)} eval, zero overlap",
    )


def check_ood_confidence(
    confidence_scores: list[float],
    threshold: float = 0.3,
    max_low_confidence_ratio: float = 0.1,
) -> GuardrailResult:
    """Check for out-of-distribution audio via confidence scores.

    If >10% of clips have mean confidence below threshold, the model is likely
    encountering OOD audio and results should be flagged.
    """
    if not confidence_scores:
        return GuardrailResult(
            name="ood_confidence",
            passed=True,
            severity="info",
            detail="No confidence scores available",
        )

    n_low = sum(1 for c in confidence_scores if c < threshold)
    ratio = n_low / len(confidence_scores)

    passed = ratio <= max_low_confidence_ratio
    return GuardrailResult(
        name="ood_confidence",
        passed=passed,
        severity="warning" if not passed else "info",
        value=ratio,
        threshold=max_low_confidence_ratio,
        detail=f"{n_low}/{len(confidence_scores)} clips below confidence {threshold} ({ratio:.1%})",
        recommendation=(
            "High proportion of low-confidence predictions — model may be OOD. "
            "Consider adding more in-domain training data."
            if not passed
            else ""
        ),
    )


def run_all_guardrails(
    per_group_wer: dict[str, float] | None = None,
    transcripts: list[str] | None = None,
    audio_durations: list[float] | None = None,
    train_speakers: set[str] | None = None,
    eval_speakers: set[str] | None = None,
    confidence_scores: list[float] | None = None,
    loss_value: float | None = None,
) -> GuardrailReport:
    """Run all applicable guardrails and return an aggregate report."""
    results: list[GuardrailResult] = []

    if loss_value is not None:
        results.append(check_nan_gradient(loss_value))

    if per_group_wer:
        results.append(check_bias_demographic(per_group_wer))

    if transcripts and audio_durations:
        for t, d in zip(transcripts, audio_durations, strict=False):
            results.append(check_hallucination_rate(t, d))

    if train_speakers is not None and eval_speakers is not None:
        results.append(check_data_leakage(train_speakers, eval_speakers))

    if confidence_scores:
        results.append(check_ood_confidence(confidence_scores))

    all_passed = all(r.passed for r in results)
    critical_count = sum(1 for r in results if not r.passed and r.severity == "critical")
    warning_count = sum(1 for r in results if not r.passed and r.severity == "warning")

    return GuardrailReport(
        all_passed=all_passed,
        results=results,
        critical_count=critical_count,
        warning_count=warning_count,
    )


def format_report(report: GuardrailReport) -> str:
    """Format a guardrail report as a human-readable string."""
    lines = [
        "=" * 60,
        "GUARDRAIL REPORT",
        "=" * 60,
        f"Status: {'ALL PASSED' if report.all_passed else 'FAILURES DETECTED'}",
        f"Critical: {report.critical_count}  Warnings: {report.warning_count}",
        "",
    ]
    for r in report.results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"[{status}] {r.name} (severity: {r.severity})")
        if r.value is not None and r.threshold is not None:
            lines.append(f"       Value: {r.value:.4f}  Threshold: {r.threshold}")
        if r.detail:
            lines.append(f"       Detail: {r.detail}")
        if r.recommendation:
            lines.append(f"       Fix: {r.recommendation}")
        lines.append("")
    return "\n".join(lines)
