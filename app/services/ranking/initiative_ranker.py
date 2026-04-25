"""Initiative Ranker — deterministic.

Spec formula (quoted verbatim from §13.1, step 6):

    rank = 0.30·closesGapWeight
         + 0.20·transformationTypeFit
         + 0.15·horizonFit
         + 0.15·priorityFit
         + 0.10·sectorDefaultUplift
         − 0.10·effortBand

Hard rules:
    * Feasibility < 0.4 BLOCKS the candidate from ranking (spec §30D.5).
    * 0.4 ≤ feasibility ≤ 0.7 → still ranked, but flagged "conditional".
    * Hybrid transformation type pays a 10% penalty unless evidence is
      strong on BOTH composing types (spec §29D + ranker note).
    * Shortlist is capped at 5 and floored at 3 (Acceptance Criterion #6).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

# Weights — exposed as constants so tests can assert against the spec.
W_CLOSES_GAP = 0.30
W_TYPE_FIT = 0.20
W_HORIZON_FIT = 0.15
W_PRIORITY_FIT = 0.15
W_SECTOR_UPLIFT = 0.10
W_EFFORT = -0.10  # negative — effort works against the rank

# Behavioural constants.
MIN_FEASIBILITY = 0.4
HYBRID_PENALTY = 0.9        # 10% multiplier reduction for unsupported hybrids
SHORTLIST_MIN = 3
SHORTLIST_MAX = 5


@dataclass
class InitiativeCandidate:
    """One candidate initiative the ranker will score."""

    id: str
    title: str
    transformation_type: str  # 'process' | 'organisational' | 'digital' | 'hybrid' | 'none_yet'
    target_dimension: str

    # Ranker inputs — each in [0, 1] unless noted.
    closes_gap_weight: float
    transformation_type_fit: float
    horizon_fit: float
    priority_fit: float
    sector_default_uplift: float
    effort_band: float        # higher = harder
    feasibility: float = 1.0

    # If hybrid: do we have strong (L2/L3) evidence for BOTH types?
    hybrid_evidence_strong: bool = False

    # Output (filled in by ranker).
    rank_score: float = field(init=False, default=0.0)
    flags: list[str] = field(init=False, default_factory=list)


def _raw_rank(c: InitiativeCandidate) -> float:
    return (
        W_CLOSES_GAP * c.closes_gap_weight
        + W_TYPE_FIT * c.transformation_type_fit
        + W_HORIZON_FIT * c.horizon_fit
        + W_PRIORITY_FIT * c.priority_fit
        + W_SECTOR_UPLIFT * c.sector_default_uplift
        + W_EFFORT * c.effort_band
    )


def rank_initiatives(
    candidates: Iterable[InitiativeCandidate],
) -> list[InitiativeCandidate]:
    """Rank, filter, and shortlist initiative candidates.

    Returns:
        Sorted list (highest rank first) of candidates that survived
        feasibility filtering, capped at SHORTLIST_MAX. The ``rank_score``
        and ``flags`` fields on each candidate are populated in-place.

    Raises:
        ValueError: if fewer than SHORTLIST_MIN candidates survive — the
        caller is contractually required to widen the candidate pool.
    """
    survivors: list[InitiativeCandidate] = []

    for c in candidates:
        # Hard block: feasibility < 0.4
        if c.feasibility < MIN_FEASIBILITY:
            continue

        score = _raw_rank(c)

        # Hybrid penalty unless evidence supports both legs.
        if c.transformation_type == "hybrid" and not c.hybrid_evidence_strong:
            score *= HYBRID_PENALTY
            c.flags.append("hybrid_penalty_applied")

        # Conditional flag — still ranked, but UI shows pre-work warning.
        if MIN_FEASIBILITY <= c.feasibility <= 0.7:
            c.flags.append("conditional_feasibility")

        c.rank_score = round(score, 6)
        survivors.append(c)

    survivors.sort(key=lambda c: c.rank_score, reverse=True)

    if len(survivors) < SHORTLIST_MIN:
        raise ValueError(
            f"Only {len(survivors)} candidate(s) survived feasibility filter "
            f"(need ≥{SHORTLIST_MIN}). Widen the candidate pool."
        )

    # Cap at 5 — return top N, preserving ranker's order.
    shortlist = survivors[:SHORTLIST_MAX]
    for i, c in enumerate(shortlist, start=1):
        # Convenience: stamp the position so the persistence layer can write
        # ``shortlist_position`` directly.
        c.flags.append(f"shortlist_position:{i}")
    return shortlist
