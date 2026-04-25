"""Expert — the practitioner side of the marketplace.

The Expert is a TENANT-SCOPED record (the expert's own tenant). The
matching logic surfaces experts to SMEs across tenants via a deterministic
ranker; the SME side never reads the Expert tenant directly.
"""
from __future__ import annotations

from sqlalchemy import JSON, Column, Float, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.models.base import TenantModel


class Expert(TenantModel):
    __tablename__ = "experts"

    person_id = Column(
        String(32), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False
    )
    person = relationship("Person")

    headline = Column(String(280), nullable=True)
    bio = Column(Text, nullable=True)

    # Expertise codes (e.g. ["finance.working_capital", "ops.lean", "tech.erp"]).
    # Used by the Expert Match Ranker (`expertise` term).
    expertise_codes = Column(JSON, nullable=False, default=list)

    # Sectors the expert serves — feeds the `sector` ranker term.
    sector_codes = Column(JSON, nullable=False, default=list)

    languages = Column(JSON, nullable=False, default=list)
    states_served = Column(JSON, nullable=False, default=list)

    # 0..1 availability score from upstream calendaring. Defaults to fully
    # available; the matching service tops it up from the booking system.
    availability_score = Column(Float, nullable=False, default=1.0)

    # Evidence anchor — at least one L0/L3 anchor required before the
    # expert can appear in any match shortlist (per spec acceptance rule).
    has_anchor_evidence = Column(String(8), nullable=False, default="false")

    matches = relationship("Match", back_populates="expert")

    def __repr__(self) -> str:
        return f"<Expert person={self.person_id}>"
