"""Active learning — "fix these clips next" (roadmap #32).

After a round of training, the most valuable thing a child can do is correct the
clips the model is *least sure about*. This module ranks clips by an uncertainty
heuristic so the UI can say "the computer is unsure about these 5 — fix these
first." Pure Python, unit-tested; no model required (the heuristic uses signals
we already store, and can later be replaced by real per-clip confidence).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClipUncertainty:
    clip_id: int
    score: float  # higher = more worth fixing
    reason: str


def rank_clips(clips: list[dict], *, top_k: int | None = None) -> list[ClipUncertainty]:
    """Rank clips by how much fixing them would likely help (pure, tested).

    Signals (no model needed yet):
      * no transcript yet → highest priority (we can't learn from unlabelled audio),
      * flagged quality issues → likely confusing the model,
      * very short clips → little signal, easy to mislabel,
      * a provided ``confidence`` in [0,1] (if present) → lower = more uncertain.
    A real per-clip confidence from the trained model can later replace the
    confidence term without changing the interface.
    """
    ranked: list[ClipUncertainty] = []
    for c in clips:
        score = 0.0
        reasons: list[str] = []
        if not (c.get("transcript") or "").strip():
            score += 1.0
            reasons.append("no words yet")
        if c.get("issues"):
            score += 0.5
            reasons.append("recording could be clearer")
        dur = float(c.get("duration_s", 0.0) or 0.0)
        if 0.0 < dur < 1.0:
            score += 0.3
            reasons.append("very short")
        conf = c.get("confidence")
        if conf is not None:
            score += max(0.0, 1.0 - float(conf))
            reasons.append("the computer wasn't sure")
        ranked.append(
            ClipUncertainty(
                clip_id=int(c["id"]),
                score=round(score, 4),
                reason=", ".join(reasons) or "looks fine",
            )
        )
    # Most-uncertain first; stable by clip_id for ties (deterministic).
    ranked.sort(key=lambda r: (-r.score, r.clip_id))
    return ranked[:top_k] if top_k else ranked
