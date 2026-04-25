"""Snapshot service — W0.0 read-only composition.

Contract (Acceptance Criterion #9): this service MUST NOT create any rows
in ``assessment_runs``, ``scores``, or ``evidence_records``. It returns a
dict to the caller and writes nothing domain-level.
"""
from __future__ import annotations

import logging
from datetime import datetime

from flask import current_app

from app.models.reference import Sector

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sector-default uplifts — these are the spec's "outputs-as-inputs" feed.
# In production they are refreshed nightly from closed Outcomes. Here we
# ship reasonable defaults so the Snapshot is immediately useful.
# ---------------------------------------------------------------------------
_SECTOR_DEFAULT_INITIATIVES: dict[str, list[dict]] = {
    "manufacturing": [
        {
            "title": "Implement OEE programme on the binding line",
            "transformation_type": "process",
            "target_dimension": "O",
            "roic_impact_bps": 180,
            "horizon_months": 9,
            "evidence_tier": "L0b",
        },
        {
            "title": "Consolidate vendor base and renegotiate MSME payment terms",
            "transformation_type": "process",
            "target_dimension": "O",
            "roic_impact_bps": 120,
            "horizon_months": 6,
            "evidence_tier": "L0b",
        },
        {
            "title": "Roll out ERP-to-shopfloor data spine (MES-lite)",
            "transformation_type": "digital",
            "target_dimension": "T",
            "roic_impact_bps": 95,
            "horizon_months": 12,
            "evidence_tier": "L0b",
        },
    ],
    "pharma": [
        {
            "title": "Data-integrity uplift for GMP audit readiness",
            "transformation_type": "process",
            "target_dimension": "O",
            "roic_impact_bps": 140,
            "horizon_months": 9,
            "evidence_tier": "L0b",
        },
        {
            "title": "API backward-integration feasibility for top-3 molecules",
            "transformation_type": "organisational",
            "target_dimension": "S",
            "roic_impact_bps": 210,
            "horizon_months": 18,
            "evidence_tier": "L0b",
        },
        {
            "title": "Serialisation & track-and-trace upgrade",
            "transformation_type": "digital",
            "target_dimension": "T",
            "roic_impact_bps": 80,
            "horizon_months": 6,
            "evidence_tier": "L0b",
        },
    ],
    "textile": [
        {
            "title": "Fibre-to-fabric yield optimisation on top-2 SKUs",
            "transformation_type": "process",
            "target_dimension": "O",
            "roic_impact_bps": 160,
            "horizon_months": 6,
            "evidence_tier": "L0b",
        },
        {
            "title": "Digital print pilot for fast-fashion margins",
            "transformation_type": "digital",
            "target_dimension": "SM",
            "roic_impact_bps": 110,
            "horizon_months": 9,
            "evidence_tier": "L0b",
        },
        {
            "title": "Skill-ladder programme for supervisor role gap",
            "transformation_type": "organisational",
            "target_dimension": "SK",
            "roic_impact_bps": 70,
            "horizon_months": 12,
            "evidence_tier": "L0b",
        },
    ],
}


def _macro_context(sector: Sector) -> dict:
    """Nightly-refreshed sector backdrop. Stub with representative values."""
    return {
        "sector_growth_pct_yoy": {
            "manufacturing": 7.4,
            "pharma": 9.8,
            "textile": 5.6,
        }.get(sector.code, 6.0),
        "roic_median_pct": {
            "manufacturing": 11.2,
            "pharma": 14.6,
            "textile": 9.4,
        }.get(sector.code, 10.0),
        "recent_scheme_changes": [
            {"scheme": "PLI Scheme", "change": "Tier-2 auto-ancillary window extended", "evidence_tier": "L0b"},
            {"scheme": "ECLGS 2.0", "change": "Revised eligibility for MSMEs up to ₹500 Cr", "evidence_tier": "L0b"},
        ],
        "refreshed_at": datetime.utcnow().isoformat(),
    }


def render_snapshot(sector: Sector) -> dict:
    """Produce the Instant Snapshot for a sector. Writes nothing."""
    macro = _macro_context(sector)
    initiatives = _SECTOR_DEFAULT_INITIATIVES.get(sector.code, [])

    narrative = _compose_narrative_with_fallback(sector, macro, initiatives)

    return {
        "sector_code": sector.code,
        "sector_name": sector.name,
        "macro_context": macro,
        "top_initiatives": initiatives[:3],
        "narrative": narrative,
        "is_read_only": True,
    }


def _compose_narrative_with_fallback(
    sector: Sector, macro: dict, initiatives: list[dict]
) -> str:
    """Invoke the Narrator agent; fall back to a deterministic template.

    The spec allows deterministic prose when the LLM is unavailable (eg.
    air-gapped env, missing API key) — the snapshot remains useful and the
    L-pill citation invariant is trivially satisfied because we cite L0b.
    """
    cfg = current_app.config if current_app else {}
    if not cfg.get("OPENAI_API_KEY"):
        return _fallback_narrative(sector, macro, initiatives)

    try:
        from app.agents.crews.nichebrains_crew import build_crew

        crew = build_crew()
        out = crew.run_snapshot(
            sector_name=sector.name,
            sector_context=macro,
            top_initiatives=initiatives[:3],
        )
        return out.snapshot_text or _fallback_narrative(sector, macro, initiatives)
    except Exception as exc:  # noqa: BLE001 — fallback on any agent failure
        logger.warning("Narrator agent failed; using fallback. %s", exc)
        return _fallback_narrative(sector, macro, initiatives)


def _fallback_narrative(
    sector: Sector, macro: dict, initiatives: list[dict]
) -> str:
    """Deterministic template used when LLM is unavailable."""
    bullets = "\n".join(
        f"- {i['title']} (+{i['roic_impact_bps']} bps ROIC, {i['horizon_months']} mo) [L0b]"
        for i in initiatives[:3]
    )
    return (
        f"The {sector.name} sector is growing at "
        f"{macro['sector_growth_pct_yoy']}% YoY with a median ROIC of "
        f"{macro['roic_median_pct']}% [L0b]. Against that backdrop, three "
        f"transformation plays most consistently move the needle for "
        f"₹10–500 Cr firms:\n\n{bullets}\n\n"
        f"This is a 60-second indicative reading — a full 40-question NRA "
        f"returns an evidenced score and a matched expert shortlist [L0b]."
    )
