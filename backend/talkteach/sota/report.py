"""Generate SOTA scoreboard reports — Markdown and JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from talkteach.sota.harness import Scoreboard, SOTAResult

BAND_EMOJI: dict[str, str] = {
    "platinum": "💠",
    "diamond": "💎",
    "gold": "🥇",
    "silver": "🥈",
    "bronze": "🥉",
    "pending": "⏳",
    "unmeasured": "❓",
    "error": "⚠️",
}


def generate_scoreboard_md(
    scoreboard: Scoreboard,
    output_path: Path | None = None,
) -> str:
    """Generate SCOREBOARD.md content."""
    lines: list[str] = []
    lines.append("# TalkTeach SOTA Scoreboard")
    lines.append("")
    lines.append(f"**Generated:** {scoreboard.generated}")
    lines.append("")
    lines.append(f"**Headline:** {scoreboard.overall_mean:.0f}/1000 — {scoreboard.overall_band}")
    lines.append("")
    lines.append(
        f"**Coverage:** {scoreboard.num_eligible}/{scoreboard.num_total} domains "
        f"adequately powered · {scoreboard.num_directional} directional (measured but "
        f"under-powered, excluded from the mean) · {scoreboard.num_unmeasured} "
        f"unmeasured/blocked. The headline is the mean over adequately-powered domains only."
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| # | Domain | Score | Band | Primary Metric | Value |")
    lines.append("|---|---|---|---|---|---|")

    for i, r in enumerate(scoreboard.sorted_by_score, 1):
        emoji = BAND_EMOJI.get(r.band, "")
        primary_key = _primary_metric_key(r)
        primary_val = r.metrics.get(primary_key, "—")
        if isinstance(primary_val, float):
            primary_val = f"{primary_val:.4f}"
        band_cell = f"{r.band} ⚠︎ directional" if getattr(r, "directional", False) else r.band
        lines.append(
            f"| {i} | {emoji} {r.domain_name} | **{r.score_0_1000}** | {band_cell} | "
            f"{primary_key} | {primary_val} |"
        )

    lines.append("")
    lines.append("## Per-Domain Details")
    lines.append("")

    for r in scoreboard.domains:
        lines.append(f"### {r.domain_id}: {r.domain_name}")
        lines.append("")
        lines.append(f"- **Score:** {r.score_0_1000}/1000 ({r.band})")
        lines.append(f"- **Engine:** {r.engine_used}")
        lines.append(f"- **Samples:** {r.num_samples}")
        if getattr(r, "directional", False):
            lines.append(f"- **Headline:** excluded — {r.directional_reason or 'under-powered'}")
        lines.append(f"- **SOTA Reference:** {r.sota_ref}")
        if r.notes:
            lines.append(f"- **Notes:** {r.notes}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(r.metrics, indent=2, default=str))
        lines.append("```")
        lines.append("")

    content = "\n".join(lines)
    if output_path:
        output_path.write_text(content)
    return content


def generate_scoreboard_json(
    scoreboard: Scoreboard,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Generate scoreboard as a JSON-serializable dict."""
    data: dict[str, Any] = {
        "generated": scoreboard.generated,
        "overall_mean": scoreboard.overall_mean,
        "overall_band": scoreboard.overall_band,
        "coverage": {
            "num_total": scoreboard.num_total,
            "num_measured": scoreboard.num_measured,
            "num_eligible": scoreboard.num_eligible,
            "num_directional": scoreboard.num_directional,
            "num_unmeasured": scoreboard.num_unmeasured,
        },
        "domains": [],
    }
    for r in scoreboard.domains:
        entry: dict[str, Any] = {
            "domain_id": r.domain_id,
            "domain_name": r.domain_name,
            "score_0_1000": r.score_0_1000,
            "band": r.band,
            "directional": getattr(r, "directional", False),
            "directional_reason": getattr(r, "directional_reason", ""),
            "metrics": r.metrics,
            "confidence_95": {k: list(v) for k, v in r.confidence_95.items()},
            "baseline_ref": r.baseline_ref,
            "sota_ref": r.sota_ref,
            "num_samples": r.num_samples,
            "engine_used": r.engine_used,
            "notes": r.notes,
        }
        data["domains"].append(entry)

    if output_path:
        output_path.write_text(json.dumps(data, indent=2, default=str))
    return data


def _primary_metric_key(result: SOTAResult) -> str:
    """Infer the primary metric key from domain ID."""
    mapping = {
        "d01": "wer",
        "d02": "wer",
        "d03": "gpu_hours",
        "d04": "rtf",
        "d05": "wer_at_5min",
        "d06": "wer_delta_at_0db",
        "d07": "languages_under_15pct_wer",
        "d08": "wer_delta_export",
        "d09": "rel_wer_reduction_5min",
        "d10": "domain_wer_optimal",
        "d11": "wer_delta_60min",
        "d12": "per_speaker_wer_std",
        "d13": "oracle_match_rate",
        "d14": "quality_gate_auc",
        "d15": "mb_per_audio_minute",
    }
    for prefix, key in mapping.items():
        if result.domain_id.startswith(prefix):
            return key
    return list(result.metrics.keys())[0] if result.metrics else "unknown"


def generate(
    scoreboard: Scoreboard,
    output_dir: Path | None = None,
) -> tuple[str, dict[str, Any]]:
    """Generate both Markdown and JSON scoreboard."""
    output_dir = output_dir or Path("docs/sota-benchmarks")
    output_dir.mkdir(parents=True, exist_ok=True)

    md = generate_scoreboard_md(scoreboard, output_dir / "SCOREBOARD.md")
    json_data = generate_scoreboard_json(scoreboard, output_dir / "SCOREBOARD.json")
    return md, json_data
