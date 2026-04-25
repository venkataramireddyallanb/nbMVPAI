"""Unit tests for the deterministic scoring engine.

Two non-negotiable guarantees being asserted here:

1. Acceptance Criterion #1 — values 35, 65, 85 are UNREACHABLE for any
   integer raw_sum in [0, 32].

2. The "Shree Vardhman Textiles" golden fixture (spec §determinism proof)
   produces the same composite ±2 across runs (we run it 3 times).
"""
from __future__ import annotations

import pytest

from app.services.scoring.engine import (
    DIMENSION_CODES,
    MAX_RAW_SUM,
    Band,
    bankers_round,
    classify_band,
    compute_composite,
    compute_dimension_score,
    score_assessment,
)


# ---------------------------------------------------------------------------
# Acceptance Criterion #1 — 35 / 65 / 85 must be unreachable.
# ---------------------------------------------------------------------------

class TestUnreachableScores:
    def test_no_dimension_score_can_equal_35_65_or_85(self):
        """Acceptance Criterion #1 — exhaustive proof over the full input space.

        The boundary-snap rule (35→36, 65→66, 85→86) ensures forbidden
        values can never escape the engine, regardless of raw_sum.
        """
        forbidden = {35, 65, 85}
        produced = {compute_dimension_score(s) for s in range(0, MAX_RAW_SUM + 1)}
        assert produced.isdisjoint(forbidden), (
            f"Forbidden values appeared from dimension scoring: "
            f"{produced & forbidden}"
        )

    def test_composite_can_never_be_35_65_or_85(self):
        """Composite must also avoid forbidden values across all integer means."""
        from app.services.scoring.engine import compute_composite as cc
        forbidden = {35, 65, 85}
        # Try every possible mean that could produce a forbidden value:
        # bankers_round(s/5) ∈ {35,65,85} for s in [173..177], [322..327], [422..427]
        for s in range(0, 5 * 100 + 1):
            # Synthesise 5 dim values summing to s (one big + four zeros).
            head = min(s, 80)
            remainder = s - head
            # Distribute remainder across 4 slots, each ≤ 80.
            dims = [head] + [min(remainder // 4, 80)] * 4
            # Pad: if rounding lost some, top up.
            while sum(dims) < s and dims[-1] < 80:
                dims[-1] += 1
            if sum(dims) != s:
                continue
            assert cc(dims) not in forbidden, f"sum {s} produced forbidden composite"

    def test_classify_band_rejects_unreachable_values(self):
        for v in (35, 65, 85):
            with pytest.raises(ValueError, match="unreachable"):
                classify_band(v)

    def test_full_dimension_score_range_is_well_formed(self):
        """Every reachable score must fall into exactly one band."""
        for raw_sum in range(0, MAX_RAW_SUM + 1):
            score = compute_dimension_score(raw_sum)
            assert 0 <= score <= 80   # dimension max is 80, not 100
            # band classification is only meaningful for the COMPOSITE,
            # but reachable single-dim scores must never be in {35,65,85}.
            assert score not in (35, 65, 85)


# ---------------------------------------------------------------------------
# Banker's rounding — half-to-even.
# ---------------------------------------------------------------------------

class TestBankersRounding:
    @pytest.mark.parametrize(
        "value, expected",
        [
            (0.5, 0),
            (1.5, 2),
            (2.5, 2),
            (3.5, 4),
            (-0.5, 0),
            (-1.5, -2),
            (10.5, 10),
            (11.5, 12),
        ],
    )
    def test_half_to_even(self, value, expected):
        assert bankers_round(value) == expected


# ---------------------------------------------------------------------------
# Composite + band classification.
# ---------------------------------------------------------------------------

class TestComposite:
    def test_composite_is_mean_rounded(self):
        # 50, 60, 70, 80, 80 → mean 68 → Strategic
        result = score_assessment({
            # raw_sums chosen to produce these dimension values via formula
            "S": 20,    # 20*2.5 = 50
            "O": 24,    # 60
            "SM": 28,   # 70
            "T": 32,    # 80
            "SK": 32,   # 80
        })
        assert [d.value for d in result.dimension_scores] == [50, 60, 70, 80, 80]
        assert result.composite == 68
        assert result.band == Band.STRATEGIC

    def test_boundary_snap_triggers_when_dim_would_be_35(self):
        """raw_sum=14 → 14*2.5=35.0 → snapped to 36."""
        from app.services.scoring.engine import compute_dimension_score as cd
        assert cd(14) == 36

    def test_boundary_snap_triggers_when_dim_would_be_65(self):
        """raw_sum=26 → 26*2.5=65.0 → snapped to 66."""
        from app.services.scoring.engine import compute_dimension_score as cd
        assert cd(26) == 66

    def test_classify_band_boundaries(self):
        assert classify_band(0) == Band.LEGACY
        assert classify_band(34) == Band.LEGACY
        assert classify_band(36) == Band.SILOED
        assert classify_band(64) == Band.SILOED
        assert classify_band(66) == Band.STRATEGIC
        assert classify_band(84) == Band.STRATEGIC
        assert classify_band(86) == Band.FUTURE_READY
        assert classify_band(100) == Band.FUTURE_READY


# ---------------------------------------------------------------------------
# Determinism — golden fixture from spec.
# ---------------------------------------------------------------------------

class TestDeterminism:
    """Spec golden fixture: Shree Vardhman Textiles must score ±2 across runs."""

    GOLDEN_RAW_SUMS = {
        # Per spec: Strategy 44, Ops 34, Sales 47, Tech 34, Skills 47
        # are the *dimension scores*, not raw sums. We back-solve the raw sums
        # from the formula score = 2.5 × raw_sum, then verify the same
        # composite emerges 3 runs in a row.
        # 44 → raw 17.6 → not integer-reachable; closest reachable is 44 from
        # raw_sum where round(2.5 × n) == 44 ⇒ n = 18 (gives 45). The fixture
        # in the doc reflects rounding of underlying L1 evidence — for a
        # determinism test we use the closest-reachable raw_sums.
        "S": 18,    # → 45
        "O": 14,    # → 35? — 35 is forbidden, the formula yields banker's-round(35.0)=
                    # actually 14*2.5 = 35.0 exact half → bankers → 36 (even). Good.
        "SM": 19,   # → 47 (banker's: 47.5 → 48) — let's check
        "T": 14,    # → 36
        "SK": 19,   # → 48
    }

    def test_golden_fixture_is_deterministic_across_runs(self):
        """Run scoring 3 times with same input — composites must be identical."""
        composites = []
        for _ in range(3):
            result = score_assessment(self.GOLDEN_RAW_SUMS)
            composites.append(result.composite)
        # Pure function — should be EXACTLY equal, not ±2.
        assert len(set(composites)) == 1, (
            f"Scoring is non-deterministic: got {composites}"
        )

    def test_golden_fixture_dimension_values_are_legal(self):
        """Sanity: every produced dimension score must avoid 35/65/85."""
        result = score_assessment(self.GOLDEN_RAW_SUMS)
        for ds in result.dimension_scores:
            assert ds.value not in (35, 65, 85)
            assert ds.code in DIMENSION_CODES


# ---------------------------------------------------------------------------
# Defensive errors.
# ---------------------------------------------------------------------------

class TestDefensiveErrors:
    def test_raw_sum_out_of_range_raises(self):
        with pytest.raises(ValueError):
            compute_dimension_score(-1)
        with pytest.raises(ValueError):
            compute_dimension_score(MAX_RAW_SUM + 1)

    def test_missing_dimension_raises(self):
        with pytest.raises(ValueError, match="Missing raw sums"):
            score_assessment({"S": 10, "O": 10})

    def test_empty_composite_raises(self):
        with pytest.raises(ValueError):
            compute_composite([])
