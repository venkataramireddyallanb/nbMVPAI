"""FirmFinancials — one period of P&L + BS inputs per firm.

One row = one fiscal year (or quarter). The latest row drives the current
driver tree; prior rows feed YoY comparisons on the dashboard.
"""
from __future__ import annotations

from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import TenantModel


class FirmFinancials(TenantModel):
    __tablename__ = "firm_financials"

    firm_id = Column(
        String(32), ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    firm = relationship("Firm")

    # Period — 'FY24', 'Q3-FY25', etc.
    period_code = Column(String(20), nullable=False, index=True)
    period_end_year = Column(Integer, nullable=False)

    # P&L primitives (INR, nominal).
    revenue = Column(Float, nullable=False, default=0.0)
    operating_profit = Column(Float, nullable=False, default=0.0)   # EBIT
    profit_before_tax = Column(Float, nullable=False, default=0.0)
    tax = Column(Float, nullable=False, default=0.0)

    # Balance sheet primitives.
    invested_capital = Column(Float, nullable=False, default=0.0)
    total_assets = Column(Float, nullable=True)

    # Evidence tier — drives the L-pill on the driver tree chips.
    evidence_tier = Column(String(4), nullable=False, default="L0a")

    # Source provenance — 'owner_input' | 'mca' | 'gst' | 'upload'.
    source = Column(String(40), nullable=False, default="owner_input")

    def __repr__(self) -> str:
        return f"<FirmFinancials firm={self.firm_id} period={self.period_code}>"
