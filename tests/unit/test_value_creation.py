"""Unit tests for the ROIC / ROA engine."""
from __future__ import annotations

import pytest

from app.services.value_creation import (
    ASSET_INTENSIVE_SECTORS,
    Financials,
    compute_reading,
    project_with_initiatives,
)


class TestROICIdentity:
    """The spec identity: ROIC = OM × CT × (1 − ETR)."""

    def test_known_values(self):
        # Revenue 100, OP 15, PBT 12, Tax 3, Invested 80, Assets 150
        # OM = 15/100 = 15%
        # CT = 100/80 = 1.25
        # ETR = 3/12 = 25%
        # ROIC = 0.15 × 1.25 × (1 − 0.25) = 0.140625 → 14.06%
        r = compute_reading(
            Financials(revenue=100, operating_profit=15,
                       profit_before_tax=12, tax=3,
                       invested_capital=80, total_assets=150),
            sector_code="manufacturing",
        )
        assert r.operating_margin_pct == 15.0
        assert r.capital_turnover == 1.25
        assert r.effective_tax_rate_pct == 25.0
        assert r.roic_pct == pytest.approx(14.06, rel=1e-3)

    def test_roa_only_for_asset_intensive(self):
        base = dict(revenue=100, operating_profit=15,
                    profit_before_tax=12, tax=3,
                    invested_capital=80, total_assets=150)
        # Asset-intensive → ROA present
        r1 = compute_reading(Financials(**base), sector_code="manufacturing")
        assert r1.roa_pct is not None
        # Non-asset-intensive → ROA absent
        r2 = compute_reading(Financials(**base), sector_code="services")
        assert r2.roa_pct is None
        r3 = compute_reading(Financials(**base), sector_code="it")
        assert r3.roa_pct is None

    def test_asset_intensive_whitelist_is_exactly_the_four_named(self):
        assert ASSET_INTENSIVE_SECTORS == {
            "manufacturing", "pharma", "textile", "agro",
        }

    def test_zero_revenue_safe(self):
        r = compute_reading(
            Financials(revenue=0, operating_profit=0,
                       profit_before_tax=0, tax=0, invested_capital=10),
        )
        assert r.operating_margin_pct == 0.0
        assert r.capital_turnover == 0.0
        assert r.roic_pct == 0.0

    def test_missing_invested_capital_raises(self):
        with pytest.raises(ValueError):
            Financials(revenue=100, operating_profit=10,
                       profit_before_tax=8, tax=2, invested_capital=0)

    def test_projection_adds_bps(self):
        base = compute_reading(
            Financials(revenue=100, operating_profit=15,
                       profit_before_tax=12, tax=3,
                       invested_capital=80, total_assets=150),
            sector_code="manufacturing",
        )
        # Apply +180 and +120 bps uplifts from approved initiatives.
        projected = project_with_initiatives(base, [180, 120])
        # 14.06 + 3.00 = 17.06%
        assert projected.roic_pct == pytest.approx(17.06, rel=1e-3)
        # Projection surfaces as an extra driver node for UI.
        labels = [d.label for d in projected.drivers]
        assert "Projected ROIC (12-mo)" in labels
