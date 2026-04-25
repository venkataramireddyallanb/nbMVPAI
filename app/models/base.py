"""Shared SQLAlchemy primitives.

Every domain entity inherits ``TimestampMixin`` for audit columns and
``TenantScopedMixin`` for strict multi-tenant data isolation. The mixins
keep table definitions DRY and guarantee that no domain row exists outside
a tenant context — which the repository layer also enforces at query time.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import declared_attr

from app.extensions import db


def _uuid() -> str:
    """ULID-style sortable id would be nicer, but UUID4 keeps deps minimal."""
    return uuid.uuid4().hex


class TimestampMixin:
    """Common ``created_at`` / ``updated_at`` columns."""

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class TenantScopedMixin:
    """Forces every domain row to live under a tenant.

    The ``tenant_id`` foreign-key is declared via ``@declared_attr`` so each
    inheriting model gets its own column rather than sharing the mixin's
    column object (which would break SQLAlchemy's mapper).
    """

    @declared_attr
    def tenant_id(cls):  # noqa: N805 — SQLAlchemy convention
        return Column(
            String(32),
            ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )


class IdMixin:
    """ULID/UUID primary key. String for portability across SQLite + Postgres."""

    id = Column(String(32), primary_key=True, default=_uuid)


class BaseModel(db.Model, IdMixin, TimestampMixin):
    """Abstract root for non-tenant-scoped tables (Tenant, User, reference data)."""

    __abstract__ = True

    def to_dict(self) -> dict:
        """Generic serialiser — repositories/schemas may override per model."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class TenantModel(BaseModel, TenantScopedMixin):
    """Abstract root for every tenant-scoped domain entity."""

    __abstract__ = True
