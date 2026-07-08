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
