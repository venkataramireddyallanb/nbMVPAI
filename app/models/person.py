"""Person — the human identity behind one-or-more roles.

Per the spec's dual-role rule: a single Person can be both an SME owner and
an Expert. The Person row is the "single identity"; the Firm and Expert rows
are the "two entities". A Person may also be linked to multiple ``User``
login records (one per tenant context), so evidence does not auto-cross
between roles.
"""
from __future__ import annotations

from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Person(BaseModel):
    __tablename__ = "persons"

    full_name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(40), nullable=True)

    # role_in_firm captures the spec's owner/next-gen/CFO/COO/function-head
    # taxonomy when this person is acting in an SME context.
    role_in_firm = Column(String(60), nullable=True)

    # SME sub-persona per DDExpert v3.1 §14 (Table 9). Drives the
    # Land-and-Expand UX motion: Founder/MD enters via dTAS at org
    # scope; CFO via Finance Agent; Dept Head via dept-scope dTAS.
    # ∈ {founder_md, cfo, dept_head}.
    sub_persona = Column(String(20), nullable=True, index=True)

    user_logins = relationship("User", back_populates="person")

    def __repr__(self) -> str:
        return f"<Person {self.full_name}>"
