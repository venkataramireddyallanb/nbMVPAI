"""Charter, Milestone, Outcome — the delivery side of the platform.

A Charter is the spec's seven-field artefact (Purpose, Scope, Success
metrics, 90-day Milestones, Risks, Required Skills, Budget). Approval at
Gate 1 is human-mediated — agents never sign, pay, or commit.
"""
from __future__ import annotations

import enum
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


class CharterStatus(str, enum.Enum):
    """Lifecycle around the four human-approval gates."""

    DRAFT = "draft"             # composed by the Drafter agent
    PENDING_APPROVAL = "pending_approval"   # Gate 1 awaits owner
    APPROVED = "approved"       # signed off
    IN_DELIVERY = "in_delivery"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Charter(TenantModel):
    """The seven-field Charter artefact."""

    __tablename__ = "charters"

    firm_id = Column(
        String(32), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    firm = relationship("Firm", back_populates="charters")

    initiative_id = Column(
        String(32), ForeignKey("initiatives.id", ondelete="SET NULL"), nullable=True
    )
    initiative = relationship("Initiative")

    title = Column(String(200), nullable=False)
    purpose = Column(Text, nullable=False)
    scope = Column(Text, nullable=False)

    # Success metrics — list of {name, baseline, target, unit}.
    success_metrics = Column(JSON, nullable=False, default=list)

    # 90-day milestones — list of {name, due_at, owner, criteria}.
    milestones_summary = Column(JSON, nullable=False, default=list)

    risks = Column(JSON, nullable=False, default=list)
    required_skills = Column(JSON, nullable=False, default=list)
    budget_inr = Column(Float, nullable=False, default=0.0)

    status = Column(
        Enum(CharterStatus), nullable=False, default=CharterStatus.DRAFT, index=True
    )

    # Provenance — points back to the NRA run that birthed this Charter.
    # The "Charter always points to its NRA run" invariant.
    nra_run_id = Column(
        String(32), ForeignKey("assessment_runs.id", ondelete="SET NULL"), nullable=True
    )

    approved_at = Column(DateTime, nullable=True)
    approved_by_user_id = Column(String(32), ForeignKey("users.id"), nullable=True)

    matches = relationship("Match", back_populates="charter", cascade="all, delete-orphan")
    milestones = relationship(
        "Milestone", back_populates="charter", cascade="all, delete-orphan"
    )
    outcomes = relationship(
        "Outcome", back_populates="charter", cascade="all, delete-orphan"
    )


class Milestone(TenantModel):
    """Time-stamped step inside a Charter."""

    __tablename__ = "milestones"

    charter_id = Column(
        String(32), ForeignKey("charters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    charter = relationship("Charter", back_populates="milestones")

    name = Column(String(200), nullable=False)
    due_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    sequence = Column(Integer, nullable=False, default=0)

    acceptance_criteria = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    # ∈ {pending, in_progress, completed, blocked}


class Outcome(TenantModel):
    """Closed-charter reading against baseline.

    The Outcome flows back into the system as a sector-default uplift for
    future ranker runs (the spec's "outputs as inputs" flywheel).
    """

    __tablename__ = "outcomes"

    charter_id = Column(
        String(32), ForeignKey("charters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    charter = relationship("Charter", back_populates="outcomes")

    closed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    baseline_metrics = Column(JSON, nullable=False, default=list)
    actual_metrics = Column(JSON, nullable=False, default=list)
    delta_pct = Column(Float, nullable=True)

    # Promotion ladder: low_evidence | evidenced | proven.
    evidence_grade = Column(String(20), nullable=False, default="evidenced")

    summary = Column(Text, nullable=True)
