"""Assessment-side models: AssessmentRun, EvidenceRecord, Score.

The AssessmentRun is the spec's atomic analytical unit — one run is tied
to a scope (Organisation / Department / Initiative), a timeframe, and an
evidence set. A run produces Scores per Dimension; each Score points to its
EvidenceRecord (the "Score always points to its Evidence" invariant).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.models.base import TenantModel
import enum


class AssessmentScope(str, enum.Enum):
    """Spec §13: three scopes with different question counts."""

    ORGANISATION = "organisation"   # 40 Qs
    DEPARTMENT = "department"       # 16 or 24 Qs
    INITIATIVE = "initiative"       # 8–16 Qs


class AssessmentStage(str, enum.Enum):
    """The assessment lifecycle stages, mapped to W0.0 → W1.5."""

    SNAPSHOT = "snapshot"               # W0.0 — read-only
    PRESCREENER = "prescreener"         # W0.1 — 6 questions
    NRA = "nra"                         # W1   — full assessment
    CHARTER_DRAFT = "charter_draft"     # W1.5 — pre-Gate-1
    DELIVERED = "delivered"             # post-Gate-1





class AssessmentHorizon(str, enum.Enum):
    """Spec §7.1 (DDExpert v3.1) — Horizon captured upstream of dTAS."""

    IMMEDIATE = "immediate"   # 0–3 months
    SHORT = "short"           # 3–12 months
    MEDIUM = "medium"         # 1–3 years
    LONG = "long"             # 3+ years


class PriorityMode(str, enum.Enum):
    """Spec §4.1 — Priority is one of two modes.

    MODE_A: a named dimension (S/O/SM/T/SK).
    MODE_B: a business driver (one of seven, see PriorityDriver).
    """

    MODE_A_DIMENSION = "mode_a_dimension"
    MODE_B_DRIVER = "mode_b_driver"


class PriorityDriver(str, enum.Enum):
    """Spec §4.1 — the seven Mode-B business drivers."""

    REVENUE_GROWTH = "revenue_growth"
    MARGIN = "margin"
    WORKING_CAPITAL = "working_capital"
    PRODUCTIVITY = "productivity"
    MARKET_EXPANSION = "market_expansion"
    CUSTOMER_RETENTION = "customer_retention"
    COMPLIANCE_RISK = "compliance_risk"

class AssessmentRun(TenantModel):
    """One analytical run for a Firm at a given scope/timeframe."""

    __tablename__ = "assessment_runs"

    firm_id = Column(
        String(32), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    firm = relationship("Firm", back_populates="assessments")

    scope = Column(
        Enum(AssessmentScope), nullable=False, default=AssessmentScope.ORGANISATION
    )
    stage = Column(
        Enum(AssessmentStage), nullable=False, default=AssessmentStage.NRA, index=True
    )

    # The composite score is integer per spec — 0..100 with bands
    # <35 / 36-64 / 66-84 / 86-100. Stored as Integer so the DB type matches.
    composite_score = Column(Integer, nullable=True)
    band = Column(String(20), nullable=True, index=True)

    # Free-form bag of priority preferences from the owner: business_driver,
    # focus_area, timeframe, appetite, urgency. Used by the Initiative Ranker.
    priority_preferences = Column(JSON, nullable=True)

    # First-class Horizon + Priority (v3.1 §4.1, §7.1) — captured BEFORE the
    # 40 dTAS questions. The freeform priority_preferences above is kept for
    # backward compatibility with v5.0 callers.
    horizon = Column(Enum(AssessmentHorizon), nullable=True)
    priority_mode = Column(Enum(PriorityMode), nullable=True)
    priority_dimension = Column(String(4), nullable=True,
        doc="Mode A: one of S/O/SM/T/SK")
    priority_driver = Column(Enum(PriorityDriver), nullable=True,
        doc="Mode B: one of the seven business drivers")

    # Derived per v3.1 Table 4 — never asked, always inferred from gaps.
    transformation_type = Column(String(20), nullable=True,
        doc="process | cx | business_model | organisational | digital | hybrid")
    transformation_secondary = Column(String(20), nullable=True,
        doc="Secondary type when transformation_type == 'hybrid'")

    # Pre-fill provenance — which L0b sources were tapped at intake.
    prefill_sources = Column(JSON, nullable=True)

    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    notes = Column(Text, nullable=True)

    scores = relationship(
        "Score", back_populates="assessment", cascade="all, delete-orphan"
    )
    evidence_records = relationship(
        "EvidenceRecord", back_populates="assessment", cascade="all, delete-orphan"
    )
    initiatives = relationship(
        "Initiative", back_populates="assessment", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AssessmentRun firm={self.firm_id} stage={self.stage.value}>"


class Score(TenantModel):
    """Per-dimension integer score for a single AssessmentRun.

    Invariant: ``value`` is always 0..100, computed by the deterministic
    scoring service via banker's rounding. Values 35, 65, 85 are
    mathematically unreachable — proven in tests/unit/test_scoring.py.
    """

    __tablename__ = "scores"

    assessment_id = Column(
        String(32),
        ForeignKey("assessment_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessment = relationship("AssessmentRun", back_populates="scores")

    dimension_code = Column(String(4), nullable=False, index=True)  # S/O/SM/T/SK
    value = Column(Integer, nullable=False)
    raw_sum = Column(Integer, nullable=False)  # the 0..32 input sum

    # Evidence tier of the dominant supporting evidence: L0a/L0b/L1/L2/L3/L4.
    # Drives the "evidence chip" in the UI.
    evidence_tier = Column(String(4), nullable=False, default="L0a")

    notes = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Score dim={self.dimension_code} value={self.value}>"


class EvidenceRecord(TenantModel):
    """Spec's "Evidence Record" — normalised atomic input.

    Fields per spec: source, confidence, freshness, mapping. Distinct from
    the user-uploaded ``Evidence`` artefact (which is the file/document).
    """

    __tablename__ = "evidence_records"

    assessment_id = Column(
        String(32),
        ForeignKey("assessment_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessment = relationship("AssessmentRun", back_populates="evidence_records")

    layer = Column(String(4), nullable=False, index=True)   # L0a..L4
    source = Column(String(120), nullable=False)             # 'mca' | 'gst' | 'upload' | 'owner_input'
    confidence = Column(Float, nullable=False, default=0.5)  # 0..1
    freshness_days = Column(Integer, nullable=False, default=0)
    mapping = Column(JSON, nullable=True)  # which dimension/question this maps to
    payload = Column(JSON, nullable=True)  # the normalised value
