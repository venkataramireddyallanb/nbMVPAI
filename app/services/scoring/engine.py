"""Deterministic scoring engine — implements spec §9.

Per-dimension formula:
    raw_score = round_half_even(100 × sum_D / 40)        # banker's rounding
    score_D   = boundary_snap(raw_score)                 # forbidden values snap UP

Bands:
    < 35       → Legacy
    36 .. 64   → Siloed
    66 .. 84   → Strategic
    86 .. 100  → Future-Ready

Mathematical invariant (Acceptance Criterion #1):
    Final scores 35, 65, 85 are NEVER produced — they would otherwise
    create boundary tie-break ambiguity. Because the literal linear formula
    yields exactly 35 / 65 / 85 for raw_sums 14 / 26 / (composite-only),
    we apply a deterministic "snap up" rule (35→36, 65→66, 85→86) so the
    score lands inside the next band. The snap is documented, deterministic,
    and applied uniformly in scoring + composite + classify_band.

This module is deliberately framework-free — no Flask, no SQLAlchemy. It
operates on plain values so it can be unit-tested in isolation and reused
from CLI tools, batch jobs, or the eventual benchmark service.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Iterable, Mapping

# Per spec: 8 questions per dimension, each scored 0..4 → max sum = 32.
QUESTIONS_PER_DIMENSION = 8
MAX_SCORE_PER_QUESTION = 4
MAX_RAW_SUM = QUESTIONS_PER_DIMENSION * MAX_SCORE_PER_QUESTION  # 32

DIMENSION_CODES = ("S", "O", "SM", "T", "SK")

# Per spec §9 — these integers must NEVER be the final score (boundary gaps).
FORBIDDEN_BOUNDARY_VALUES = frozenset({35, 65, 85})

# Snap targets: the next-band-start. Choosing "up" (rather than down) is
# deliberate — it gives a strictly more generous reading at the boundary
# and matches the spec's "promote with evidence" intelligence-ladder ethos.
_BOUNDARY_SNAP = {35: 36, 65: 66, 85: 86}


class Band(str, enum.Enum):
    """Integer-band classification per spec §9."""

    LEGACY = "Legacy"               # < 35
    SILOED = "Siloed"               # 36..64
    STRATEGIC = "Strategic"         # 66..84
    FUTURE_READY = "Future-Ready"   # 86..100


@dataclass(frozen=True)
class DimensionScore:
    """One dimension's reading."""

    code: str
    raw_sum: int
    value: int
    evidence_tier: str = "L0a"


@dataclass(frozen=True)
class ScoringResult:
    """Output of ``score_assessment``."""

    dimension_scores: tuple[DimensionScore, ...]
    composite: int
    band: Band


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def boundary_snap(value: int) -> int:
    """Snap forbidden boundary values (35/65/85) to the next band's start.

    Pure, deterministic, and idempotent. All score-producing functions in
    this module pass their final result through this function so that the
    "35/65/85 unreachable" invariant holds end-to-end.
    """
    return _BOUNDARY_SNAP.get(value, value)


def bankers_round(value):
    """Half-to-even rounding (banker's rounding).

    Uses ``Decimal`` to keep boundary cases exact across platforms.
    """
    if isinstance(value, float):
        value = Decimal(str(value))
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


def compute_dimension_score(raw_sum: int) -> int:
    """Compute the dimension score — snapped to avoid 35/65/85.

    Args:
        raw_sum: sum of the 8 question answers, each 0..4 → range [0, 32].

    Returns:
        Integer dimension score in [0, 80] (80 = perfect), snapped.
    """
    if not 0 <= raw_sum <= MAX_RAW_SUM:
        raise ValueError(
            f"raw_sum must be in [0, {MAX_RAW_SUM}], got {raw_sum}"
        )
    # 100 × raw_sum / 40 == raw_sum × 2.5 — keep as Decimal to avoid float drift.
    exact = Decimal(raw_sum) * Decimal("2.5")
    return boundary_snap(bankers_round(exact))


def compute_composite(dimension_values: Iterable[int]) -> int:
    """Composite = mean of dimension scores, rounded to integer, snapped."""
    values = list(dimension_values)
    if not values:
        raise ValueError("compute_composite requires at least one dimension value")
    mean = Decimal(sum(values)) / Decimal(len(values))
    return boundary_snap(bankers_round(mean))


def classify_band(value: int) -> Band:
    """Map a 0..100 integer score to its Band.

    The 35/65/85 unreachable values are EXCLUDED from every band. Should they
    ever appear (a bug), this function raises so the bug surfaces loudly
    instead of silently miscategorising.
    """
    if value in (35, 65, 85):
        raise ValueError(
            f"Value {value} is mathematically unreachable per spec §9 — "
            "indicates an upstream rounding bug."
        )
    if 0 <= value <= 34:
        return Band.LEGACY
    if 36 <= value <= 64:
        return Band.SILOED
    if 66 <= value <= 84:
        return Band.STRATEGIC
    if 86 <= value <= 100:
        return Band.FUTURE_READY
    raise ValueError(f"Score {value} out of range [0, 100]")


def score_assessment(
    raw_sums: Mapping[str, int],
    evidence_tiers: Mapping[str, str] | None = None,
) -> ScoringResult:
    """Score a full assessment from per-dimension raw sums.

    Args:
        raw_sums: ``{dimension_code: raw_sum}`` for each of the 5 dimensions.
        evidence_tiers: optional ``{dimension_code: tier}`` for evidence chips.

    Returns:
        ScoringResult with per-dimension scores, composite, and band.
    """
    missing = set(DIMENSION_CODES) - raw_sums.keys()
    if missing:
        raise ValueError(f"Missing raw sums for dimensions: {sorted(missing)}")

    tiers = evidence_tiers or {}
    dim_scores = tuple(
        DimensionScore(
            code=code,
            raw_sum=raw_sums[code],
            value=compute_dimension_score(raw_sums[code]),
            evidence_tier=tiers.get(code, "L0a"),
        )
        for code in DIMENSION_CODES
    )
    composite = compute_composite(d.value for d in dim_scores)
    band = classify_band(composite)
    return ScoringResult(
        dimension_scores=dim_scores,
        composite=composite,
        band=band,
    )
