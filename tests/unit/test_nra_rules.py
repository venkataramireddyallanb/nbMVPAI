"""Unit tests for NRA business rules (young-firm floor, skips, contradictions)."""
from __future__ import annotations

import pytest

from app.services.scoring.rules import (
    TooManySkippedError,
    YOUNG_FIRM_FLOOR_SCORE,
    apply_young_firm_floor,
    compute_raw_sum_with_skips,
    is_young_firm,
    resolve_contradiction,
    resolve_skips,
)


class TestYoungFirmFloor:
    def test_2yr_old_firm_with_legacy_S_is_floored(self):
        result = apply_young_firm_floor(
            {"S": 12, "O": 60, "SM": 50, "T": 40, "SK": 48},
            founded_year=2024, now_year=2026,
        )
        assert result["S"] == YOUNG_FIRM_FLOOR_SCORE
        # Other dimensions untouched.
        assert result["O"] == 60 and result["SK"] == 48

    def test_old_firm_not_affected(self):
        result = apply_young_firm_floor(
            {"S": 12, "O": 60, "SM": 50, "T": 40, "SK": 48},
            founded_year=2008, now_year=2026,
        )
        assert result["S"] == 12   # unchanged

    def test_young_firm_already_above_floor_unchanged(self):
        result = apply_young_firm_floor(
            {"S": 70, "O": 60, "SM": 50, "T": 40, "SK": 48},
            founded_year=2024, now_year=2026,
        )
        assert result["S"] == 70

    def test_no_founded_year_no_floor(self):
        result = apply_young_firm_floor(
            {"S": 12, "O": 60, "SM": 50, "T": 40, "SK": 48},
            founded_year=None,
        )
        assert result["S"] == 12

    @pytest.mark.parametrize("founded,now,expect", [
        (2024, 2026, True),    # 2 years old
        (2023, 2026, False),   # 3 years — boundary: NOT young
        (2022, 2026, False),
        (None, 2026, False),
    ])
    def test_is_young_firm_boundary(self, founded, now, expect):
        assert is_young_firm(founded, now) is expect


class TestSkips:
    def test_zero_skips_passthrough(self):
        assert resolve_skips([4, 3, 2, 1, 0, 4, 3, 2]) == [4, 3, 2, 1, 0, 4, 3, 2]

    def test_one_skip_uses_median(self):
        # Median of [4,3,2,1,0,4,3] = 3 (7 values, sorted [0,1,2,3,3,4,4], mid=3)
        answers = [4, 3, 2, 1, 0, 4, 3, None]
        assert resolve_skips(answers) == [4, 3, 2, 1, 0, 4, 3, 3]

    def test_two_skips_raises(self):
        with pytest.raises(TooManySkippedError, match="2 questions skipped"):
            resolve_skips([4, 3, 2, 1, None, 4, None, 2])

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError, match="Expected 8 answers"):
            resolve_skips([1, 2, 3])

    def test_compute_raw_sum_with_skips(self):
        # [4,3,2,1,0,4,3,None] → median 3 → sum 20
        assert compute_raw_sum_with_skips(
            [4, 3, 2, 1, 0, 4, 3, None]) == 20


class TestContradictionResolution:
    def test_higher_tier_wins(self):
        # L0a=3 vs L2=1 → L2 wins even though lower numeric value
        v, t = resolve_contradiction([(3, "L0a"), (1, "L2")])
        assert (v, t) == (1, "L2")

    def test_l4_beats_all(self):
        v, t = resolve_contradiction([(0, "L4"), (4, "L0a"), (3, "L0b"),
                                      (2, "L1"), (1, "L2"), (4, "L3")])
        assert t == "L4"

    def test_single_candidate_returned(self):
        assert resolve_contradiction([(2, "L1")]) == (2, "L1")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            resolve_contradiction([])
