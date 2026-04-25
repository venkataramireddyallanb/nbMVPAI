"""Engagement-side models: Initiative + Match.

An ``Initiative`` is the ranker's output — a candidate transformation
project. A ``Match`` is one expert proposed against a charter (top-3 only,
per spec). Both are tenant-scoped.
"""
from __future__ import annotations

import enum

from sqlalchemy import (
    JSON,
    Column,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.models.base import TenantModel


class TransformationType(str, enum.Enum):
    """Spec §29D — deterministic inference taxonomy."""

    PROCESS = "process"
    ORGANISATIONAL = "organisational"
    DIGITAL = "digital"
    HYBRID = "hybrid"
    NONE_YET = "none_yet"


class Initiative(TenantModel):
    """Candidate transformation project produced by the ranker."""

    __tablename__ = "initiatives"

    firm_id = Column(
        String(32), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    firm = relationship("Firm", back_populates="initiatives")

    assessment_id = Column(
        String(32),
        ForeignKey("assessment_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    assessment = relationship("AssessmentRun", back_populates="initiatives")

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    transformation_type = Column(
        Enum(TransformationType), nullable=False, default=TransformationType.PROCESS
    )

    # Primary dimension this initiative addresses (for gap-closing math).
    target_dimension = Column(String(4), nullable=False, index=True)

    # Inputs to the ranker formula:
    #   rank = 0.30·closesGapWeight + 0.20·transformationTypeFit
    #        + 0.15·horizonFit + 0.15·priorityFit
    #        + 0.10·sectorDefaultUplift − 0.10·effortBand
    closes_gap_weight = Column(Float, nullable=False, default=0.0)
    transformation_type_fit = Column(Float, nullable=False, default=0.0)
    horizon_fit = Column(Float, nullable=False, default=0.0)
    priority_fit = Column(Float, nullable=False, default=0.0)
    sector_default_uplift = Column(Float, nullable=False, default=0.0)
    effort_band = Column(Float, nullable=False, default=0.0)

    # Computed by the ranker — sorted-by-this for shortlist.
    rank_score = Column(Float, nullable=False, default=0.0, index=True)

    # Feasibility 0..1 — <0.4 BLOCKS ranking (spec §30D.5).
    feasibility = Column(Float, nullable=False, default=1.0)

    # Estimated economic effects on driver tree (revenue, margin, etc.).
    economic_drivers = Column(JSON, nullable=True)

    # Position in the final shortlist (1..5 if shortlisted, else NULL).
    shortlist_position = Column(Integer, nullable=True, index=True)


class Match(TenantModel):
    """One Expert proposal against a Charter (top-3 only)."""

    __tablename__ = "matches"

    charter_id = Column(
        String(32), ForeignKey("charters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    charter = relationship("Charter", back_populates="matches")

    expert_id = Column(
        String(32), ForeignKey("experts.id", ondelete="CASCADE"), nullable=False
    )
    expert = relationship("Expert", back_populates="matches")

    # Inputs to the Expert Match Ranker:
    #   match = 0.35·expertise + 0.25·sector + 0.15·geography
    #         + 0.15·language + 0.10·availability
    expertise_score = Column(Float, nullable=False, default=0.0)
    sector_score = Column(Float, nullable=False, default=0.0)
    geography_score = Column(Float, nullable=False, default=0.0)
    language_score = Column(Float, nullable=False, default=0.0)
    availability_score = Column(Float, nullable=False, default=0.0)
    fit_score = Column(Float, nullable=False, default=0.0, index=True)

    # The reason-code chips shown in the UI ("Sector match", "Lean expertise").
    reason_codes = Column(JSON, nullable=True)

    # 1..3 — top three only, per spec.
    rank_position = Column(Integer, nullable=False, default=1)
