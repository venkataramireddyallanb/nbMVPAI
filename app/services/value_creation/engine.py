"""Value-creation engine — ROIC / ROA / driver tree math.

Spec identities (§Finance Agent contract, §30D.5):

    ROIC = Operating Margin × Capital Turnover × (1 − Effective Tax Rate)

         = (Operating Profit / Revenue)
         × (Revenue / Invested Capital)
         × (1 − Tax / PBT)

    ROA  = Net Income / Total Assets           (asset-intensive sectors only)

This module is framework-free (no Flask, no SQLAlchemy) so it can be
unit-tested in isolation and reused from CLI / batch jobs.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Iterable

# Asset-intensive sectors — dual ROIC + ROA view per spec.
ASSET_INTENSIVE_SECTORS = frozenset({
    "manufacturing", "pharma", "textile", "agro",
})


@dataclass(frozen=True)
class Financials:
    """One period of P&L + balance-sheet primitives (INR)."""
    revenue: float
    operating_profit: float       # EBIT
    profit_before_tax: float
    tax: float
    invested_capital: float       # debt + equity - cash
    total_assets: float | None = None   # only needed for ROA

    def __post_init__(self):
        if self.revenue < 0 or self.invested_capital <= 0:
            raise ValueError("Revenue must be >=0 and invested_capital > 0")


@dataclass(frozen=True)
class ValueCreationReading:
    """Output of the driver tree for one period."""
    operating_margin_pct: float      # OP / Revenue × 100
    capital_turnover: float          # Revenue / Invested Capital
    effective_tax_rate_pct: float    # Tax / PBT × 100
    roic_pct: float                  # %
    roa_pct: float | None            # only when total_assets provided
    # Driver decomposition (for UI waterfall / tree).
    drivers: tuple["Driver", ...] = ()


@dataclass(frozen=True)
class Driver:
    """One node in the driver tree."""
    label: str
    value: float
    unit: str
    delta_bps: float | None = None   # change vs. baseline if provided
    note: str = ""


def _pct(n: float, d: float) -> float:
    if d == 0: return 0.0
    return round((n / d) * 100, 2)


def _round(x: float, ndigits: int = 2) -> float:
    with localcontext() as c:
        c.rounding = ROUND_HALF_EVEN
        return float(Decimal(str(x)).quantize(Decimal(10) ** -ndigits))


def compute_reading(
    financials: Financials,
    sector_code: str | None = None,
) -> ValueCreationReading:
    """Compute one period's ROIC / ROA / driver tree.

    Args:
        financials: P&L + BS primitives.
        sector_code: used to gate the ROA calculation (asset-intensive only).
    """
    om = _pct(financials.operating_profit, financials.revenue)
    ct = _round(financials.revenue / financials.invested_capital, 3) \
        if financials.invested_capital else 0.0
    etr = _pct(financials.tax, financials.profit_before_tax) \
        if financials.profit_before_tax else 0.0

    # ROIC = OM% × CT × (1 − ETR%)
    roic_pct = _round((om / 100) * ct * (1 - etr / 100) * 100, 2)

    roa_pct: float | None = None
    if (sector_code and sector_code in ASSET_INTENSIVE_SECTORS
            and financials.total_assets and financials.total_assets > 0):
        # ROA uses Net Income (PBT - Tax).
        net_income = financials.profit_before_tax - financials.tax
        roa_pct = _pct(net_income, financials.total_assets)

    return ValueCreationReading(
        operating_margin_pct=om,
        capital_turnover=ct,
        effective_tax_rate_pct=etr,
        roic_pct=roic_pct,
        roa_pct=roa_pct,
        drivers=(
            Driver("Revenue", financials.revenue, "INR",
                   note=f"top of tree"),
            Driver("Operating Profit", financials.operating_profit, "INR",
                   note="EBIT"),
            Driver("Operating Margin", om, "percent",
                   note="OP / Revenue"),
            Driver("Invested Capital", financials.invested_capital, "INR",
                   note="debt + equity − cash"),
            Driver("Capital Turnover", ct, "ratio",
                   note="Revenue / Invested Capital"),
            Driver("Effective Tax Rate", etr, "percent",
                   note="Tax / PBT"),
            Driver("ROIC", roic_pct, "percent",
                   note="OM × CT × (1 − ETR)"),
            *(((Driver("ROA", roa_pct, "percent", note="Net Income / Total Assets"),))
              if roa_pct is not None else ()),
        ),
    )


def project_with_initiatives(
    reading: ValueCreationReading,
    initiative_uplifts_bps: Iterable[int],
) -> ValueCreationReading:
    """Apply cumulative ROIC uplifts (in basis points) from approved initiatives.

    This is the spec's "outputs as inputs" flywheel preview — what does the
    driver tree look like if the owner signs the shortlisted charters?

    Uplifts compose additively in bps (conservative vs. multiplicative)
    unless and until we have L4-proven deltas.
    """
    total_bps = sum(initiative_uplifts_bps)
    projected_roic = _round(reading.roic_pct + total_bps / 100, 2)
    return ValueCreationReading(
        operating_margin_pct=reading.operating_margin_pct,
        capital_turnover=reading.capital_turnover,
        effective_tax_rate_pct=reading.effective_tax_rate_pct,
        roic_pct=projected_roic,
        roa_pct=reading.roa_pct,
        drivers=(
            *reading.drivers,
            Driver(
                "Projected ROIC (12-mo)",
                projected_roic,
                "percent",
                delta_bps=total_bps,
                note=f"+{total_bps} bps from {len(list(initiative_uplifts_bps)) if False else 'approved'} initiatives",
            ),
        ),
    )
