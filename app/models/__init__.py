"""Domain model package — single import surface for SQLAlchemy mappers.

Importing this package (or any submodule) from the app factory ensures that
SQLAlchemy registers every model on the declarative base BEFORE the first
``db.create_all()`` or Alembic autogen scan.
"""
from app.models.assessment import (  # noqa: F401
    AssessmentRun,
    EvidenceRecord,
    Score,
)
from app.models.charter import Charter, Milestone, Outcome  # noqa: F401
from app.models.engagement import Initiative, Match  # noqa: F401
from app.models.evidence import Evidence  # noqa: F401
from app.models.expert import Expert  # noqa: F401
from app.models.financials import FirmFinancials  # noqa: F401
from app.models.firm import Firm  # noqa: F401
from app.models.partner import Partner  # noqa: F401
from app.models.permission import UserModulePermission  # noqa: F401
from app.models.person import Person  # noqa: F401
from app.models.reference import Dimension, Sector  # noqa: F401
from app.models.tenant import Tenant  # noqa: F401
from app.models.user import User, UserRole  # noqa: F401

__all__ = [
    "AssessmentRun",
    "Charter",
    "Dimension",
    "Evidence",
    "EvidenceRecord",
    "Expert",
    "Firm",
    "FirmFinancials",
    "Initiative",
    "Match",
    "Milestone",
    "Outcome",
    "Partner",
    "Person",
    "Score",
    "Sector",
    "Tenant",
    "UserModulePermission",
    "User",
    "UserRole",
]
