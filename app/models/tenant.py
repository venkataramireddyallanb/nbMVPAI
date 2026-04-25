"""Tenant — root of the multi-user isolation boundary.

A Tenant typically maps to one Firm (SME), one Expert practice, or one
Partner organisation. Every domain row belongs to exactly one tenant; the
repository layer is contractually required to scope every query by
``current_user.tenant_id``.
"""
from __future__ import annotations

from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Tenant(BaseModel):
    __tablename__ = "tenants"

    name = Column(String(200), nullable=False)
    slug = Column(String(120), unique=True, nullable=False, index=True)

    # tenant_kind ∈ {sme, expert, partner} — drives default UI and feature
    # gating. Kept loose (string) rather than enum to avoid heavy migrations
    # when new tenant kinds appear.
    tenant_kind = Column(String(32), nullable=False, default="sme")

    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Tenant {self.slug} ({self.tenant_kind})>"
