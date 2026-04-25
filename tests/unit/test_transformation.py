"""Unit tests for transformation-type inference (DDExpert v3.1 Table 4)."""
from __future__ import annotations

import pytest

from app.services.scoring.transformation import (
    DIMENSION_TO_TYPE,
    HYBRID_THRESHOLD_PTS,
    infer_transformation_type,
)


class TestSingleType:
    @pytest.mark.parametrize("worst_dim, expected_type", [
        ("O",  "process"),
        ("SM", "cx"),
        ("S",  "business_model"),
        ("SK", "organisational"),
        ("T",  "digital"),
    ])
    def test_dominant_gap_maps_to_type(self, worst_dim, expected_type):
        # Make worst_dim 30, others 80 (huge gap → not hybrid).
        scores = {d: 80 for d in ("S", "O", "SM", "T", "SK")}
        scores[worst_dim] = 30
        result = infer_transformation_type(scores)
        assert result.primary_type == expected_type
        assert result.primary_dimension == worst_dim
        assert result.secondary_dimension is None
        assert result.gap_points == 50


class TestHybrid:
    def test_two_dims_within_5_pts_triggers_hybrid(self):
        # Worst=O at 30, SM at 33 (3 pts gap → hybrid).
        scores = {"S": 80, "O": 30, "SM": 33, "T": 80, "SK": 80}
        result = infer_transformation_type(scores)
        assert result.primary_type == "hybrid"
        assert result.primary_dimension == "O"
        assert result.secondary_dimension == "SM"
        assert result.secondary_type == "cx"
        assert result.gap_points == 3

    def test_exactly_5_pts_still_hybrid(self):
        scores = {"S": 80, "O": 30, "SM": 35, "T": 80, "SK": 80}
        result = infer_transformation_type(scores)
        assert result.primary_type == "hybrid"
        assert result.gap_points == HYBRID_THRESHOLD_PTS

    def test_6_pts_apart_not_hybrid(self):
        scores = {"S": 80, "O": 30, "SM": 36, "T": 80, "SK": 80}
        result = infer_transformation_type(scores)
        assert result.primary_type == "process"
        assert result.secondary_dimension is None


class TestErrors:
    def test_missing_dimensions_raises(self):
        with pytest.raises(ValueError, match="Missing dimension scores"):
            infer_transformation_type({"S": 50})

    def test_complete_mapping_covers_all_dims(self):
        from app.services.scoring.engine import DIMENSION_CODES
        assert set(DIMENSION_TO_TYPE.keys()) == set(DIMENSION_CODES)
