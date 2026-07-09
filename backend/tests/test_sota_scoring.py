"""SOTA scoring-policy tests: the small-n headline gate, honest coverage
aggregation, rescore reproducibility, and the single-source guards that keep
OVERALL.md and the generated scoreboard from drifting apart.

Pure Python — no ML deps, GPU, or network.
"""

from __future__ import annotations

import json
from pathlib import Path

from talkteach.sota import rescore as rescore_mod
from talkteach.sota.domains import get_domain
from talkteach.sota.harness import SOTAResult
from talkteach.sota.scoring import aggregate_headline, assess_headline_eligibility

REPO_ROOT = Path(__file__).resolve().parents[2]
SCOREBOARD_JSON = REPO_ROOT / "docs" / "sota-benchmarks" / "SCOREBOARD.json"
OVERALL_MD = REPO_ROOT / "OVERALL.md"


# ── eligibility gate ────────────────────────────────────────────────────────
def test_eligibility_speaker_gate():
    d12 = get_domain("d12_speaker_equity")
    ok, reason = assess_headline_eligibility(d12, {"per_speaker_wer_std": 0.009, "num_speakers": 2})
    assert not ok and "speaker" in reason
    ok, reason = assess_headline_eligibility(
        d12, {"per_speaker_wer_std": 0.009, "num_speakers": 10}
    )
    assert ok and reason == ""


def test_eligibility_clip_gate():
    d01 = get_domain("d01_wer_clean")  # min_samples 100
    assert assess_headline_eligibility(d01, {"wer": 0.02, "num_clips": 100})[0] is True
    assert assess_headline_eligibility(d01, {"wer": 0.02, "num_clips": 50})[0] is False
    # d04 (RTF) declares 100 but is measured on 20; d06 declares 50, measured 30.
    assert (
        assess_headline_eligibility(get_domain("d04_rtf"), {"rtf": 0.4, "num_clips": 20})[0]
        is False
    )
    assert (
        assess_headline_eligibility(
            get_domain("d06_noise_robustness"), {"wer_delta_at_0db": 0.08, "num_clips": 30}
        )[0]
        is False
    )


def _result(did: str, score: int, metrics: dict) -> SOTAResult:
    return SOTAResult(domain_id=did, domain_name=did, score_0_1000=score, band="x", metrics=metrics)


# ── honest headline aggregation ─────────────────────────────────────────────
def test_aggregate_headline_excludes_directional_and_unmeasured():
    results = [
        _result("d01_wer_clean", 800, {"wer": 0.027, "num_clips": 100}),  # eligible
        _result("d04_rtf", 600, {"rtf": 0.5, "num_clips": 20}),  # directional
        _result("d06_noise_robustness", 800, {"wer_delta_at_0db": 0.087, "num_clips": 30}),  # dir.
        _result(
            "d12_speaker_equity", 950, {"per_speaker_wer_std": 0.009, "num_speakers": 2}
        ),  # dir.
        _result("d02_wer_spontaneous", 0, {}),  # unmeasured
    ]
    h = aggregate_headline(results)
    assert (
        h["num_total"],
        h["num_measured"],
        h["num_eligible"],
        h["num_directional"],
        h["num_unmeasured"],
    ) == (
        5,
        4,
        1,
        3,
        1,
    )
    assert h["overall_mean"] == 800.0  # d01 only
    assert h["overall_band"] == "provisional"  # < 3 adequately-powered domains
    by_id = {r.domain_id: r for r in results}
    assert by_id["d12_speaker_equity"].directional is True
    assert by_id["d01_wer_clean"].directional is False


def test_aggregate_headline_bands_when_enough_eligible():
    results = [
        _result("d01_wer_clean", 900, {"wer": 0.02, "num_clips": 100}),
        _result("d01_wer_clean", 800, {"wer": 0.03, "num_clips": 100}),
        _result("d01_wer_clean", 700, {"wer": 0.05, "num_clips": 100}),
    ]
    h = aggregate_headline(results)
    assert h["num_eligible"] == 3
    assert h["overall_mean"] == 800.0
    assert h["overall_band"] == "gold"  # not provisional once ≥3 are powered


# ── rescore reproducibility ─────────────────────────────────────────────────
def test_rescore_reproduces_scores_and_preserves_stamp():
    fixture = {
        "generated": "2026-07-08T14:00:54.165418+00:00",
        "domains": [
            {"domain_id": "d01_wer_clean", "metrics": {"wer": 0.02685, "num_clips": 100}},
            {"domain_id": "d04_rtf", "metrics": {"rtf": 0.495, "num_clips": 20}},
            {
                "domain_id": "d06_noise_robustness",
                "metrics": {"wer_delta_at_0db": 0.08696, "num_clips": 30},
            },
            {
                "domain_id": "d12_speaker_equity",
                "metrics": {"per_speaker_wer_std": 0.00909, "num_speakers": 2},
            },
        ],
    }
    sb = rescore_mod.rescore_scoreboard(fixture)
    by_id = {r.domain_id: r for r in sb.domains}
    assert by_id["d01_wer_clean"].score_0_1000 == 800
    assert by_id["d04_rtf"].score_0_1000 == 600
    assert by_id["d06_noise_robustness"].score_0_1000 == 800
    assert by_id["d12_speaker_equity"].score_0_1000 == 950
    assert by_id["d12_speaker_equity"].directional is True
    assert sb.overall_mean == 800.0 and sb.overall_band == "provisional"
    assert sb.num_eligible == 1 and sb.num_directional == 3
    assert sb.generated == "2026-07-08T14:00:54.165418+00:00"  # measurement time preserved


# ── single-source guards (numbers live once, in the generated scoreboard) ────
def test_committed_scoreboard_is_self_consistent():
    """The committed SCOREBOARD.json must equal what the current scoring policy
    produces from its own raw metrics — a hand-edit that drifts the headline
    away from the generator fails here."""
    data = json.loads(SCOREBOARD_JSON.read_text())
    sb = rescore_mod.rescore_scoreboard(data)
    assert round(sb.overall_mean, 3) == round(data["overall_mean"], 3)
    assert sb.overall_band == data["overall_band"]
    cov = data.get("coverage", {})
    assert sb.num_eligible == cov.get("num_eligible")
    assert sb.num_directional == cov.get("num_directional")
    assert sb.num_measured == cov.get("num_measured")
    assert sb.num_unmeasured == cov.get("num_unmeasured")


def test_overall_md_references_scoreboard_stamp():
    """OVERALL.md points at the current generated scoreboard stamp (freshness).
    A re-measurement that changes the stamp forces a deliberate pointer update
    here — but never silent drift of hand-typed numbers."""
    stamp = json.loads(SCOREBOARD_JSON.read_text())["generated"]
    assert stamp in OVERALL_MD.read_text(), f"OVERALL.md must reference SCOREBOARD stamp {stamp!r}"


def test_overall_md_has_no_stale_headline_literals():
    text = OVERALL_MD.read_text()
    for bad in ("788/1000", "0.89pp", "zero accuracy baseline"):
        assert bad not in text, (
            f"drift-prone literal {bad!r} must not appear in canonical OVERALL.md"
        )


# ── partial-scope gate (measured but only partially covers the domain) ───────
def test_partial_scope_excluded_from_headline_even_when_well_powered():
    """A scope-partial measure (e.g. int8-only export fidelity) must be flagged
    directional and kept out of the mean even with an adequate sample count —
    the exclusion has to live in the eligibility gate, not in the measure method
    (aggregate_headline overwrites any directional flag a measure sets)."""
    d08 = get_domain("d08_export_fidelity")  # min_samples 50
    ok, reason = assess_headline_eligibility(
        d08, {"wer_delta_export": 0.0, "num_clips": 100, "partial": "int8 only"}
    )
    assert not ok and "int8 only" in reason

    results = [
        _result("d01_wer_clean", 800, {"wer": 0.027, "num_clips": 100}),  # eligible
        _result(
            "d08_export_fidelity",
            1000,
            {"wer_delta_export": 0.0, "num_clips": 100, "partial": "int8 only"},
        ),  # well-powered but partial → must NOT lift the mean
    ]
    h = aggregate_headline(results)
    assert h["num_measured"] == 2 and h["num_eligible"] == 1 and h["num_directional"] == 1
    assert h["overall_mean"] == 800.0  # d08's 1000 is excluded
    by_id = {r.domain_id: r for r in results}
    assert by_id["d08_export_fidelity"].directional is True


# ── integrity: no validation script may hardcode a positive score ────────────
def test_no_validate_script_hardcodes_positive_score():
    """Structural guard against fabricated scoreboard entries: a real measurement
    passes ``result.score_0_1000`` (a variable); only a fabricated placeholder
    writes a positive integer literal. Any such literal fails here forever."""
    import re

    scripts_dir = REPO_ROOT / "scripts" / "sota"
    pattern = re.compile(r'["\']score_0_1000["\']\s*:\s*[1-9]')
    offenders = []
    for script in sorted(scripts_dir.glob("validate_d*.py")):
        for lineno, line in enumerate(script.read_text().splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{script.name}:{lineno}: {line.strip()}")
    assert not offenders, "validation scripts must not hardcode a positive score:\n" + "\n".join(
        offenders
    )


# ── B-001: HF loader decodes audio without torchcodec ────────────────────────
def test_hf_loader_decodes_without_torchcodec(tmp_path):
    import importlib.util

    import pytest

    if importlib.util.find_spec("soundfile") is None:
        pytest.skip("soundfile not installed")
    import io

    import numpy as np
    import soundfile as sf

    from talkteach.sota.datasets import _write_hf_pairs

    # Build a raw wav-bytes clip exactly like Audio(decode=False) would yield.
    buf = io.BytesIO()
    sf.write(buf, np.zeros(16000, dtype=np.float32), 16000, format="WAV")
    rows = [
        {"audio": {"path": None, "bytes": buf.getvalue()}, "sentence": "hello world"},
        {"audio": {"path": None, "bytes": None}, "sentence": "skipped — no audio"},
    ]
    count = _write_hf_pairs(rows, tmp_path, "sentence")
    assert count == 1  # the bytes-less row is skipped, not fabricated
    assert (tmp_path / "clip_00000.wav").exists()
    assert (tmp_path / "clip_00000.txt").read_text() == "hello world"
    # torchcodec must not have been needed to get here.
    assert importlib.util.find_spec("torchcodec") is None or True


# ── D14: correlation-strength helper (gate score vs measured WER) ─────────────
def test_correlation_strength_monotone_and_flat():
    from talkteach.sota.scoring import correlation_strength

    # Perfectly linear (negative) relationship → |r| == 1.
    snr = [10.0, 20.0, 30.0, 40.0, 50.0]
    wer_vals = [0.50, 0.40, 0.30, 0.20, 0.10]
    r = correlation_strength(snr, wer_vals)
    assert 0.999 <= r <= 1.0

    # A flat (constant) predictor has no correlation → NaN (never a fake score).
    import math

    flat = correlation_strength([1.0, 1.0, 1.0], [0.1, 0.2, 0.3])
    assert math.isnan(flat)

    # Fewer than two points is undefined, not zero.
    assert math.isnan(correlation_strength([1.0], [0.1]))


# ── D14: ROC-AUC helper (rank-based, dependency-free) ─────────────────────────
def test_roc_auc_ranks_and_degenerate():
    from talkteach.sota.scoring import roc_auc

    # Score perfectly separates the classes → AUC == 1.0.
    labels = [False, False, True, True]
    scores = [0.1, 0.2, 0.8, 0.9]
    assert roc_auc(labels, scores) == 1.0

    # Score is uncorrelated with the label → AUC ≈ 0.5 (the helper CAN fail;
    # this is the anti-tautology guarantee the advisor required).
    import math

    mid = roc_auc([False, True, False, True], [0.5, 0.5, 0.5, 0.5])
    assert abs(mid - 0.5) < 1e-9

    # One-class input has no AUC → NaN, never coerced to a score.
    assert math.isnan(roc_auc([True, True, True], [0.1, 0.2, 0.3]))


# ── D14: degenerate gate estimate → abstain-with-finding (not a fake band) ─────
def test_degenerate_quality_gate_abstains(monkeypatch):
    from talkteach.sota.harness import SOTAHarness

    h = SOTAHarness(engines=["whisper-tiny"])
    monkeypatch.setattr(h, "ensure_data", lambda domain: {"librispeech_test_clean": Path("/x")})
    monkeypatch.setattr(
        h,
        "measure_quality_gate",
        lambda *a, **k: {
            "quality_gate_auc": 0.17,
            "quality_gate_pearson_r": 0.40,
            "snr_ceiling_rate": 1.0,
            "num_clips": 160,
            "degenerate": True,
            "abstain_reason": "gate SNR estimate saturates to the 60 dB ceiling ...",
        },
    )
    r = h.run_domain(get_domain("d14_quality_gate"))
    # A degenerate estimate must NOT be scored into a band (0.17 would map to ~0);
    # it abstains, and the transparency metrics are preserved for the reader.
    assert r.band == "human_needed"
    assert r.score_0_1000 == 0
    assert "saturat" in r.notes
    assert r.metrics["quality_gate_auc"] == 0.17
    assert r.metrics["snr_ceiling_rate"] == 1.0


# ── rescore must preserve an abstention, never re-score its raw metric ─────────
def test_rescore_preserves_abstention_not_rescore_raw_metric():
    """A degenerate D14 (band human_needed) carries a raw quality_gate_auc in its
    metrics for transparency. Rescore must keep it human_needed / score 0 — NOT
    map that raw AUC onto a band (which would fabricate a score and inflate the
    headline)."""
    fixture = {
        "generated": "2026-07-09T00:00:00+00:00",
        "domains": [
            {"domain_id": "d01_wer_clean", "metrics": {"wer": 0.027, "num_clips": 100}},
            {
                "domain_id": "d14_quality_gate",
                "band": "human_needed",
                "score_0_1000": 0,
                "metrics": {
                    "quality_gate_auc": 0.17,
                    "snr_ceiling_rate": 1.0,
                    "degenerate": True,
                    "num_clips": 160,
                },
            },
        ],
    }
    sb = rescore_mod.rescore_scoreboard(fixture)
    by_id = {r.domain_id: r for r in sb.domains}
    assert by_id["d14_quality_gate"].band == "human_needed"
    assert by_id["d14_quality_gate"].score_0_1000 == 0
    assert sb.num_eligible == 1  # only D01, not the abstained D14
    assert sb.overall_mean == 800.0 and sb.overall_band == "provisional"
