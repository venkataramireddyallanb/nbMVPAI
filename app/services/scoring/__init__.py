"""Deterministic scoring service — NOT an LLM agent.

The spec mandates exactly TWO LLM agents in production. Scoring is a pure
function of inputs and lives here as a plain service.
"""
from app.services.scoring.engine import (  # noqa: F401
    FORBIDDEN_BOUNDARY_VALUES,
    Band,
    DimensionScore,
    ScoringResult,
    bankers_round,
    boundary_snap,
    classify_band,
    compute_composite,
    compute_dimension_score,
    score_assessment,
)

__all__ = [
    "FORBIDDEN_BOUNDARY_VALUES",
    "Band",
    "DimensionScore",
    "ScoringResult",
    "bankers_round",
    "boundary_snap",
    "classify_band",
    "compute_composite",
    "compute_dimension_score",
    "score_assessment",
]
