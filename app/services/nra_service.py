"""NRA service — orchestrates scoring + persistence + optional narrative."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from flask import current_app

from app.extensions import db
from app.models.assessment import (
    AssessmentRun,
    AssessmentScope,
    AssessmentStage,
    Score,
)
from app.models.firm import Firm
from app.services.ranking.initiative_ranker import (
    InitiativeCandidate,
    rank_initiatives,
)
from app.services.scoring.engine import DIMENSION_CODES, score_assessment
from app.services.scoring.engine import DIMENSION_CODES as _DIMS

logger = logging.getLogger(__name__)


def create_nra_run(
    firm: Firm,
    raw_sums: dict[str, int],
    priority_preferences: dict | None = None,
    evidence_tiers: dict[str, str] | None = None,
    include_narrative: bool = False,
) -> dict[str, Any]:
    """Score, persist, optionally narrate. Returns the API-shaped dict."""
    # --- 1. Validate inputs ----------------------------------------------
    missing = set(_DIMS) - raw_sums.keys()
    if missing:
        raise ValueError(f"Missing raw sums for dimensions: {sorted(missing)}")

    # --- 2. Score deterministically --------------------------------------
    result = score_assessment(raw_sums, evidence_tiers=evidence_tiers)

    # --- 2b. Apply NRA business rule: young-firm (<3 yrs) Strategy floor ---
    # See app/services/scoring/rules.py — a 2-year-old firm shouldn't be
    # labelled Legacy on Strategy just because they haven't had time to
    # build governance artefacts.
    try:
        founded_year = int(firm.founded_year) if firm.founded_year else None
    except (TypeError, ValueError):
        founded_year = None
    if founded_year:
        patched = apply_young_firm_floor(
            {ds.code: ds.value for ds in result.dimension_scores},
            founded_year=founded_year,
        )
        # If the floor changed anything, rebuild the ScoringResult.
        if any(patched[ds.code] != ds.value for ds in result.dimension_scores):
            from app.services.scoring.engine import (
                DimensionScore, ScoringResult, classify_band, compute_composite,
            )
            new_dim = tuple(
                DimensionScore(
                    code=ds.code,
                    raw_sum=ds.raw_sum,
                    value=patched[ds.code],
                    evidence_tier=ds.evidence_tier,
                ) for ds in result.dimension_scores
            )
            composite = compute_composite(d.value for d in new_dim)
            result = ScoringResult(
                dimension_scores=new_dim,
                composite=composite,
                band=classify_band(composite),
            )

    # --- 2c. Infer transformation type (DDExpert v3.1 Table 4) -----------
    # Never asked — always derived from the dimension-gap pattern.
    inference = infer_transformation_type(
        {ds.code: ds.value for ds in result.dimension_scores}
    )

    # --- 3. Persist run + per-dim scores ---------------------------------
    run = AssessmentRun(
        tenant_id=firm.tenant_id,
        firm_id=firm.id,
        scope=AssessmentScope.ORGANISATION,
        stage=AssessmentStage.NRA,
        composite_score=result.composite,
        band=result.band.value,
        priority_preferences=priority_preferences,
        transformation_type=inference.primary_type,
        transformation_secondary=inference.secondary_type,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db.session.add(run)
    db.session.flush()

    for ds in result.dimension_scores:
        db.session.add(Score(
            tenant_id=firm.tenant_id,
            assessment_id=run.id,
            dimension_code=ds.code,
            value=ds.value,
            raw_sum=ds.raw_sum,
            evidence_tier=ds.evidence_tier,
        ))

    db.session.commit()

    # --- 4. Narrative (optional, guarded) --------------------------------
    narrative = None
    if include_narrative and current_app.config.get("OPENAI_API_KEY"):
        try:
            from app.agents import build_crew
            crew = build_crew()
            narrative = crew.run_nra_report_and_charter(
                firm_profile={
                    "legal_name": firm.legal_name,
                    "sector": firm.sector.code if firm.sector else None,
                    "size_band": firm.size_band,
                },
                scoring_result={
                    "composite": result.composite,
                    "band": result.band.value,
                    "dimensions": [
                        {"code": d.code, "value": d.value, "tier": d.evidence_tier}
                        for d in result.dimension_scores
                    ],
                },
                ranked_initiatives=[],
                ranked_experts=[],
            ).nra_narrative
        except Exception as exc:  # noqa: BLE001
            logger.warning("Narrator failed during NRA — returning without narrative: %s", exc)

    return {
        "assessment_id": run.id,
        "firm_id": firm.id,
        "stage": run.stage.value,
        "composite_score": run.composite_score,
        "band": run.band,
        "scores": [
            dict(
                dimension_code=ds.code,
                value=ds.value,
                raw_sum=ds.raw_sum,
                evidence_tier=ds.evidence_tier,
            )
            for ds in result.dimension_scores
        ],
        "narrative": narrative,
        "transformation_type": inference.primary_type,
        "transformation_secondary": inference.secondary_type,
    }
