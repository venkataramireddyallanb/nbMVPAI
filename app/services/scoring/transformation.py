"""Transformation-type inference per DDExpert v3.1 Table 4.

The spec is explicit: transformation type is **never asked** — it is
derived from the dimension-gap pattern. Five types:

    PROCESS         — dominant gap is O (Operations & Supply Chain)
    CX              — dominant gap is SM (Sales & Marketing)
    BUSINESS_MODEL  — dominant gap is S (Strategy & Leadership)
    ORGANISATIONAL  — dominant gap is SK (Skills & Capabilities)
    DIGITAL         — dominant gap is T (Technology)
    HYBRID          — two or more dimensions within 5 pts of the worst;
                      report the top two explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.scoring.engine import DIMENSION_CODES

# Spec-mandated mapping from dominant gap dimension to transformation type.
DIMENSION_TO_TYPE: dict[str, str] = {
    "O":  "process",
    "SM": "cx",
    "S":  "business_model",
    "SK": "organisational",
    "T":  "digital",
}

# Hybrid trigger: any dim within this many points of the worst dim.
HYBRID_THRESHOLD_PTS = 5


@dataclass(frozen=True)
class TransformationInference:
    """Output of ``infer_transformation_type``."""
    primary_type: str               # process / cx / business_model / organisational / digital / hybrid
    primary_dimension: str          # the worst dim (lowest score)
    secondary_dimension: str | None # populated only when primary_type == 'hybrid'
    secondary_type: str | None
    gap_points: int                 # gap from worst → second-worst
    rationale: str


def infer_transformation_type(dim_scores: dict[str, int]) -> TransformationInference:
    """Infer the transformation type from the per-dimension scores.

    Args:
        dim_scores: ``{dimension_code: int score}`` for all 5 dimensions.

    The "worst" dimension is the one with the LOWEST score (biggest gap
    to close). If two or more dims sit within 5 pts of that worst, we
    return HYBRID and surface the top two explicitly per spec.
    """
    missing = set(DIMENSION_CODES) - dim_scores.keys()
    if missing:
        raise ValueError(f"Missing dimension scores: {sorted(missing)}")

    # Sort dims ascending by score — index 0 is worst (biggest gap).
    ordered = sorted(dim_scores.items(), key=lambda kv: kv[1])
    worst_dim, worst_score = ordered[0]
    second_dim, second_score = ordered[1]
    gap = second_score - worst_score

    primary_type = DIMENSION_TO_TYPE[worst_dim]

    # Hybrid rule: top two dims within HYBRID_THRESHOLD_PTS.
    if gap <= HYBRID_THRESHOLD_PTS:
        secondary_type = DIMENSION_TO_TYPE[second_dim]
        return TransformationInference(
            primary_type="hybrid",
            primary_dimension=worst_dim,
            secondary_dimension=second_dim,
            secondary_type=secondary_type,
            gap_points=gap,
            rationale=(
                f"Worst dimension '{worst_dim}' (score {worst_score}) and "
                f"second-worst '{second_dim}' (score {second_score}) are "
                f"only {gap} pts apart — within the {HYBRID_THRESHOLD_PTS}-pt "
                f"hybrid threshold. Reporting both: "
                f"{primary_type} + {secondary_type}."
            ),
        )

    return TransformationInference(
        primary_type=primary_type,
        primary_dimension=worst_dim,
        secondary_dimension=None,
        secondary_type=None,
        gap_points=gap,
        rationale=(
            f"Dominant gap is '{worst_dim}' at {worst_score}; next-worst "
            f"is {second_score} ({gap} pts higher). Single-type "
            f"transformation: {primary_type}."
        ),
    )
