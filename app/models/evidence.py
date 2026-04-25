"""Evidence — uploaded artefact attached to scores / initiatives / charters / outcomes.

Distinct from ``EvidenceRecord`` (the normalised atomic input). Evidence
rows are the user-facing files: a scanned invoice, an audit report, an
ERP screenshot. Every L-pill citation in the UI traces back here.
"""
from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, Text

from app.models.base import TenantModel


class Evidence(TenantModel):
    __tablename__ = "evidence"

    layer = Column(String(4), nullable=False, index=True)   # L0a/L0b/L1/L2/L3/L4
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Storage pointer — could be S3 key, GCS object, local path. Kept as
    # string so the storage backend can be swapped without a migration.
    storage_url = Column(String(500), nullable=True)
    mime_type = Column(String(80), nullable=True)
    size_bytes = Column(Integer, nullable=True)

    # Polymorphic attachment — Evidence can hang off any of the four
    # primary entities. Exactly one of these FKs should be non-null.
    score_id = Column(String(32), ForeignKey("scores.id", ondelete="CASCADE"), nullable=True)
    initiative_id = Column(
        String(32), ForeignKey("initiatives.id", ondelete="CASCADE"), nullable=True
    )
    charter_id = Column(
        String(32), ForeignKey("charters.id", ondelete="CASCADE"), nullable=True
    )
    outcome_id = Column(
        String(32), ForeignKey("outcomes.id", ondelete="CASCADE"), nullable=True
    )

    uploaded_by_user_id = Column(String(32), ForeignKey("users.id"), nullable=True)
