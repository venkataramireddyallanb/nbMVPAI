"""Firm — the SME / MSME being assessed.

Maps to the spec's "Company Master" object: stable firmographic profile
(identity, sector, size band, location, sub-persona tags) that survives
across multiple Assessment Runs.
"""
from __future__ import annotations

from sqlalchemy import JSON, Column, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.models.base import TenantModel


class Firm(TenantModel):
    __tablename__ = "firms"

    legal_name = Column(String(200), nullable=False)
    display_name = Column(String(200), nullable=True)

    sector_id = Column(String(32), ForeignKey("sectors.id"), nullable=False, index=True)
    sector = relationship("Sector", back_populates="firms")

    # Revenue size band drives the ₹10–500 Cr targeting and benchmark cohort.
    # Stored as enum-ish string: 'micro' | 'small' | 'mid' | 'upper_mid'
    size_band = Column(String(20), nullable=False, default="small")

    # Public registry identifiers — used to pre-fill from L0b sources.
    cin = Column(String(40), nullable=True, index=True)        # MCA
    gstin = Column(String(20), nullable=True, index=True)      # GSTN
    pan = Column(String(20), nullable=True)

    state = Column(String(80), nullable=True)
    city = Column(String(80), nullable=True)

    # Free-form sub-persona / cluster tags (e.g. "auto-ancillary tier-2",
    # "API-pharma exporter"). Kept JSON for flexibility; queried rarely.
    sub_persona_tags = Column(JSON, nullable=True)

    # Founding year — drives the spec's "very young firms (<3 yrs) get S floored" rule.
    founded_year = Column(String(4), nullable=True)

    notes = Column(Text, nullable=True)

    assessments = relationship(
        "AssessmentRun", back_populates="firm", cascade="all, delete-orphan"
    )
    initiatives = relationship(
        "Initiative", back_populates="firm", cascade="all, delete-orphan"
    )
    charters = relationship(
        "Charter", back_populates="firm", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Firm {self.legal_name}>"
