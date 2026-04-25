"""Orchestration layer — pulls persisted data, calls the pure engine.

Caller flow:
    /firms/{id}/driver-tree
        -> value_creation_service.get_driver_tree_for_firm(firm_id, tenant_id)
            -> loads FirmFinancials + approved Initiative uplifts
            -> engine.compute_reading + engine.project_with_initiatives
            -> returns a serialisable dict for the UI
"""
from __future__ import annotations

from app.extensions import db
from app.models.charter import CharterStatus
from app.models.engagement import Initiative
from app.models.financials import FirmFinancials
from app.models.firm import Firm
from app.services.value_creation.engine import (
    ASSET_INTENSIVE_SECTORS,
    Driver,
    Financials,
    compute_reading,
    project_with_initiatives,
)


def get_driver_tree_for_firm(firm_id: str, tenant_id: str) -> dict | None:
    firm = Firm.query.filter_by(id=firm_id, tenant_id=tenant_id).first()
    if not firm:
        return None

    # Latest period.
    latest = (FirmFinancials.query
              .filter_by(firm_id=firm.id, tenant_id=tenant_id)
              .order_by(FirmFinancials.period_end_year.desc())
              .first())

    if not latest:
        return _empty_response(firm)

    fin = Financials(
        revenue=latest.revenue,
        operating_profit=latest.operating_profit,
        profit_before_tax=latest.profit_before_tax,
        tax=latest.tax,
        invested_capital=max(latest.invested_capital, 1.0),
        total_assets=latest.total_assets,
    )

    sector_code = firm.sector.code if firm.sector else None
    current = compute_reading(fin, sector_code=sector_code)

    # Initiative uplifts — only from charters that have been approved
    # (Gate 1 signed). Uplifts are sourced from initiative.economic_drivers.
    uplifts = _initiative_uplifts(firm)

    projected = (project_with_initiatives(current, uplifts)
                 if uplifts else current)

    is_asset_intensive = sector_code in ASSET_INTENSIVE_SECTORS

    return {
        "firm_id": firm.id,
        "sector_code": sector_code,
        "is_asset_intensive": is_asset_intensive,
        "period_code": latest.period_code,
        "period_end_year": latest.period_end_year,
        "evidence_tier": latest.evidence_tier,
        "current": _serialize_reading(current, is_asset_intensive),
        "projected": _serialize_reading(projected, is_asset_intensive) if uplifts else None,
        "initiative_uplifts_bps": uplifts,
    }


def _initiative_uplifts(firm: Firm) -> list[int]:
    """Sum bps uplifts from approved charter initiatives for this firm."""
    approved_initiatives = (
        db.session.query(Initiative)
        .filter(Initiative.firm_id == firm.id)
        .all()
    )
    uplifts: list[int] = []
    for i in approved_initiatives:
        ed = i.economic_drivers or {}
        if isinstance(ed, dict):
            bps = ed.get("roic_uplift_bps")
            if isinstance(bps, (int, float)) and bps > 0:
                uplifts.append(int(bps))
    return uplifts


def _serialize_reading(r, is_asset_intensive: bool) -> dict:
    return {
        "operating_margin_pct": r.operating_margin_pct,
        "capital_turnover": r.capital_turnover,
        "effective_tax_rate_pct": r.effective_tax_rate_pct,
        "roic_pct": r.roic_pct,
        "roa_pct": r.roa_pct if is_asset_intensive else None,
        "drivers": [
            {"label": d.label, "value": d.value, "unit": d.unit,
             "delta_bps": d.delta_bps, "note": d.note}
            for d in r.drivers
        ],
    }


def _empty_response(firm: Firm) -> dict:
    sector_code = firm.sector.code if firm.sector else None
    return {
        "firm_id": firm.id,
        "sector_code": sector_code,
        "is_asset_intensive": sector_code in ASSET_INTENSIVE_SECTORS,
        "period_code": None,
        "period_end_year": None,
        "evidence_tier": "L0a",
        "current": None,
        "projected": None,
        "initiative_uplifts_bps": [],
    }
