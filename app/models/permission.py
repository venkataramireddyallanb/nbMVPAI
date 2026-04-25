"""UserModulePermission — one row per (user, module_code) grant.

Tenant-scoped via the user's own tenant_id. Granting/revoking is an
admin action; the row carries provenance (who granted, when) for the
audit log.
"""
from __future__ import annotations

from sqlalchemy import Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import TenantModel


class UserModulePermission(TenantModel):
    __tablename__ = "user_module_permissions"
    __table_args__ = (
        UniqueConstraint("user_id", "module_code",
                         name="uq_user_module_permission"),
    )

    user_id = Column(String(32),
                     ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    user = relationship("User", backref="module_permissions",
                        foreign_keys=[user_id])

    module_code = Column(String(80), nullable=False, index=True)

    # Provenance for the audit log.
    granted_by_user_id = Column(String(32),
                                ForeignKey("users.id", ondelete="SET NULL"),
                                nullable=True)

    def __repr__(self) -> str:
        return f"<UserModulePermission user={self.user_id} mod={self.module_code}>"
