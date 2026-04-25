"""Charter service — W1.5 draft composition.

Flow:
    1. Load the AssessmentRun + selected Initiative.
    2. Ask the Drafter agent to author the seven-field Charter.
    3. Persist as ``status=DRAFT`` — Gate 1 is the OWNER's to sign.
"""
from __future__ import annotations

import logging

from app.extensions import db
from app.models.assessment import AssessmentRun
from app.models.charter import Charter, CharterStatus
from app.models.engagement import Initiative

logger = logging.getLogger(__name__)


def draft_charter_from_assessment(
    assessment_id: str,
    initiative_id: str,
    tenant_id: str,
) -> Charter:
    """Create a new DRAFT Charter. Caller is responsible for approval."""
    run = AssessmentRun.query.filter_by(
        id=assessment_id, tenant_id=tenant_id
    ).first()
    if not run:
        raise LookupError(f"AssessmentRun {assessment_id} not found for tenant")

    initiative = Initiative.query.filter_by(
        id=initiative_id, tenant_id=tenant_id
    ).first()
    if not initiative:
        raise LookupError(f"Initiative {initiative_id} not found for tenant")

    # Try the LLM Drafter; fall back to deterministic scaffolding.
    draft = _llm_draft(run, initiative) or _fallback_draft(run, initiative)

    charter = Charter(
        tenant_id=tenant_id,
        firm_id=run.firm_id,
        initiative_id=initiative.id,
        nra_run_id=run.id,
        title=draft["title"],
        purpose=draft["purpose"],
        scope=draft["scope"],
        success_metrics=draft["success_metrics"],
        milestones_summary=draft["milestones_summary"],
        risks=draft["risks"],
        required_skills=draft["required_skills"],
        budget_inr=draft["budget_inr"],
        status=CharterStatus.DRAFT,
    )
    db.session.add(charter)
    db.session.commit()
    return charter


def _llm_draft(run: AssessmentRun, initiative: Initiative) -> dict | None:
    """Ask the Drafter agent to compose the Charter. Returns None on any failure."""
    from flask import current_app
    if not current_app.config.get("OPENAI_API_KEY"):
        return None
    try:
        from app.agents import build_crew
        crew = build_crew()
        out = crew.run_nra_report_and_charter(
            firm_profile={"firm_id": run.firm_id},
            scoring_result={
                "composite": run.composite_score,
                "band": run.band,
            },
            ranked_initiatives=[{
                "id": initiative.id,
                "title": initiative.title,
                "type": initiative.transformation_type.value,
                "target": initiative.target_dimension,
            }],
            ranked_experts=[],
        )
        # The raw output is a text blob — parsing a structured charter from
        # it is deferred to a post-processor. For now, wrap it into the
        # seven fields with the LLM prose in purpose.
        return {
            "title": f"Charter — {initiative.title}",
            "purpose": out.charter_draft.get("raw", "") if out.charter_draft else "",
            "scope": f"Organisation-wide; primary dimension = {initiative.target_dimension}",
            "success_metrics": [],
            "milestones_summary": [],
            "risks": [],
            "required_skills": [],
            "budget_inr": 0.0,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Drafter failed: %s", exc)
        return None


def _fallback_draft(run: AssessmentRun, initiative: Initiative) -> dict:
    """Deterministic Charter scaffold — used when the LLM is off."""
    return {
        "title": f"Charter — {initiative.title}",
        "purpose": (
            f"Close the gap in dimension '{initiative.target_dimension}' "
            f"via '{initiative.title}'. Baseline composite: {run.composite_score} "
            f"({run.band})."
        ),
        "scope": "Organisation scope. 90-day horizon. Reviewed at gate 1.",
        "success_metrics": [
            {"name": "Primary KPI", "baseline": None, "target": None, "unit": "tbd"},
        ],
        "milestones_summary": [
            {"name": "Kick-off & baseline", "due_in_days": 14},
            {"name": "Design & approvals", "due_in_days": 45},
            {"name": "Pilot & measurement", "due_in_days": 90},
        ],
        "risks": ["Adoption friction", "Data-quality gap"],
        "required_skills": ["Process design", "Change management"],
        "budget_inr": 0.0,
    }
