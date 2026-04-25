"""NRA business rules — invariants the spec names verbatim.

Three rules live here:

1. **Young-firm Strategy floor** — Firms founded < 3 years ago cannot be
   Legacy on the Strategy dimension. We floor their S score to the
   Siloed lower bound (36) so a new founder isn't mislabelled as legacy
   when they simply haven't had time to build strategy artefacts.

2. **Skipped-question handling** — A respondent may skip ONE question per
   dimension; the missing answer is substituted with the dimension's
   median of the answered questions. More than one skip in the same
   dimension is a hard error — the dim is not scoreable.

3. **Contradiction resolution** — When L0a (owner opinion) disagrees with
   L0b (public) or L2 (evidenced), the higher-evidence answer wins.
"""
from __future__ import annotations

from datetime import datetime
from statistics import median

from app.services.scoring.engine import (
    DIMENSION_CODES,
    QUESTIONS_PER_DIMENSION,
    Band,
    classify_band,
)

YOUNG_FIRM_YEARS = 3
YOUNG_FIRM_FLOOR_SCORE = 36   # lower edge of Siloed (Legacy = <35 → floor to 36)


# ---------------------------------------------------------------------------
# Rule 1 — young-firm floor
# ---------------------------------------------------------------------------

def apply_young_firm_floor(
    dim_values: dict[str, int],
    founded_year: int | None,
    now_year: int | None = None,
) -> dict[str, int]:
    """Return a patched copy of ``dim_values`` applying the young-firm rule."""
    if founded_year is None:
        return dict(dim_values)
    now = now_year or datetime.utcnow().year
    if now - founded_year < YOUNG_FIRM_YEARS:
        patched = dict(dim_values)
        if patched.get("S", 100) < YOUNG_FIRM_FLOOR_SCORE:
            patched["S"] = YOUNG_FIRM_FLOOR_SCORE
        return patched
    return dict(dim_values)


def is_young_firm(founded_year: int | None, now_year: int | None = None) -> bool:
    if founded_year is None:
        return False
    now = now_year or datetime.utcnow().year
    return (now - founded_year) < YOUNG_FIRM_YEARS


# ---------------------------------------------------------------------------
# Rule 2 — skipped-question median substitution
# ---------------------------------------------------------------------------

class TooManySkippedError(ValueError):
    """More than one skip in the same dimension → not scoreable."""


def resolve_skips(answers: list[int | None]) -> list[int]:
    """Replace the single ``None`` entry with the median of the rest.

    Args:
        answers: 8 entries per dimension; at most ONE may be None.

    Raises:
        TooManySkippedError: if ≥2 entries are None.
    """
    if len(answers) != QUESTIONS_PER_DIMENSION:
        raise ValueError(
            f"Expected {QUESTIONS_PER_DIMENSION} answers, got {len(answers)}"
        )
    skips = [i for i, a in enumerate(answers) if a is None]
    if len(skips) >= 2:
        raise TooManySkippedError(
            f"{len(skips)} questions skipped in one dimension — only 1 allowed"
        )
    if not skips:
        return [int(a) for a in answers]  # type: ignore[arg-type]

    present = [int(a) for a in answers if a is not None]
    # Banker's-round-free median: stats.median gives the float mid-value;
    # round half to even to stay consistent with the scoring engine.
    med = round(median(present))
    patched = [int(a) if a is not None else med for a in answers]
    return patched


def compute_raw_sum_with_skips(answers: list[int | None]) -> int:
    """Helper: compute the per-dim raw_sum after skip substitution."""
    return sum(resolve_skips(answers))


# ---------------------------------------------------------------------------
# Rule 3 — contradiction resolution
# ---------------------------------------------------------------------------

EVIDENCE_RANK = {"L0a": 0, "L0b": 1, "L1": 2, "L2": 3, "L3": 4, "L4": 5}


def resolve_contradiction(
    candidates: list[tuple[int, str]],
) -> tuple[int, str]:
    """Given competing (value, tier) readings for the SAME question,
    return the winning one — highest evidence tier wins.

    Args:
        candidates: list of (answer_value, evidence_tier) tuples.

    Returns:
        (winning_value, winning_tier).
    """
    if not candidates:
        raise ValueError("resolve_contradiction needs ≥1 candidate")
    return max(candidates, key=lambda c: EVIDENCE_RANK.get(c[1], -1))
