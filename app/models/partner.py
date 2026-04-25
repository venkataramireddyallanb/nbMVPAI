"""Partner — ecosystem organisation (association, bank, incubator, cluster).

Partners get their own dashboards (cohort views, sector readiness
benchmarks, scheme uptake). They never see PII; benchmark exposure requires
a minimum cohort size of 20 (enforced at the service layer).
"""
from __future__ import annotations

from sqlalchemy import JSON, Column, String, Text

from app.models.base import TenantModel


class Partner(TenantModel):
    __tablename__ = "partners"

    name = Column(String(200), nullable=False)
    partner_kind = Column(String(40), nullable=False, default="association")
    # ∈ {association, bank, incubator, cluster, government}

    # Cohort scope — sectors and geographies this partner cares about.
    sector_codes = Column(JSON, nullable=False, default=list)
    states = Column(JSON, nullable=False, default=list)

    contact_email = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Partner {self.name} ({self.partner_kind})>"
