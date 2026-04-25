"""Reference data — Sectors and Dimensions.

These are platform-wide (not tenant-scoped). They seed the system and rarely
change. Sector codes drive vertical-agent dispatch (Manufacturing / Pharma /
Textile in v5.0); Dimension codes are the canonical S, O, SM, T, SK from the
dTAS v2 framework.
"""
from __future__ import annotations

from sqlalchemy import Boolean, Column, String, Text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Sector(BaseModel):
    __tablename__ = "sectors"

    code = Column(String(40), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)

    # Asset-intensive sectors get the dual ROIC + ROA view per spec §UI rules.
    # (Manufacturing, Pharma, Textile, Agro-processing.)
    is_asset_intensive = Column(Boolean, nullable=False, default=False)

    # Whether a vertical agent / sector skin is live for this sector yet.
    has_vertical_agent = Column(Boolean, nullable=False, default=False)

    firms = relationship("Firm", back_populates="sector")

    def __repr__(self) -> str:
        return f"<Sector {self.code}>"


class Dimension(BaseModel):
    """The five dTAS v2 dimensions — S, O, SM, T, SK."""

    __tablename__ = "dimensions"

    code = Column(String(4), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)

    # display_order keeps the radar/dashboard rendering deterministic.
    display_order = Column(String(2), nullable=False, default="0")

    def __repr__(self) -> str:
        return f"<Dimension {self.code}>"
