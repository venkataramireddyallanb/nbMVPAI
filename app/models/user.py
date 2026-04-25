"""User — authenticated identity.

A ``User`` is the login principal. It belongs to ONE tenant but its
underlying ``Person`` may be referenced by multiple entities (the spec's
"dual-role" rule: the same Person can be both an SME owner and an Expert,
but evidence does NOT auto-cross — each role gets its own tenant context).
"""
from __future__ import annotations

import enum
from datetime import datetime

import bcrypt
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class UserRole(str, enum.Enum):
    """Role-based access — checked by the ``role_required`` decorator."""

    OWNER = "owner"          # SME founder / director
    OPERATOR = "operator"    # SME employee with delegated access
    EXPERT = "expert"        # external practitioner
    PARTNER = "partner"      # ecosystem org analyst
    ADMIN = "admin"          # platform staff


class User(BaseModel):
    __tablename__ = "users"

    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.OWNER, index=True)

    is_active = Column(Boolean, nullable=False, default=True)
    last_login_at = Column(DateTime, nullable=True)

    tenant_id = Column(
        String(32),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant = relationship("Tenant", back_populates="users")

    person_id = Column(
        String(32),
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
    )
    person = relationship("Person", back_populates="user_logins")

    # ---- Password handling ----
    def set_password(self, plain: str) -> None:
        self.password_hash = bcrypt.hashpw(plain.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, plain: str) -> bool:
        if not self.password_hash:
            return False
        return bcrypt.checkpw(plain.encode('utf-8'), self.password_hash.encode('utf-8'))

    def touch_login(self) -> None:
        self.last_login_at = datetime.utcnow()

    def __repr__(self) -> str:
        return f"<User {self.email} role={self.role.value}>"
