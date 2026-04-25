"""Seed reference data + demo tenants/users for first-run convenience.

Usage::
    flask seed          # idempotent — safe to re-run

Creates one demo user per role so the login page's persona picker works
out of the box:

    owner     @ owner@demo.nichebrains.ai       (SME tenant — Demo SME)
    operator  @ operator@demo.nichebrains.ai    (SME tenant — Demo SME)
    expert    @ expert@demo.nichebrains.ai      (Expert tenant — Demo Expert)
    partner   @ partner@demo.nichebrains.ai     (Partner tenant — Demo Partner)
    admin     @ admin@demo.nichebrains.ai       (Platform tenant — Demo Platform)

All passwords: demo1234
"""
from __future__ import annotations

from app.extensions import db
from app.models.expert import Expert
from app.models.partner import Partner
from app.models.person import Person
from app.models.reference import Dimension, Sector
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.services.modules import default_modules_for_role
from app.models.permission import UserModulePermission


DIMENSION_SEED = [
    ("S", "Strategy & Leadership", "1"),
    ("O", "Operations & Supply Chain", "2"),
    ("SM", "Sales & Marketing", "3"),
    ("T", "Technology", "4"),
    ("SK", "Skills & Capabilities", "5"),
]

SECTOR_SEED = [
    ("manufacturing", "Manufacturing", True, True),
    ("pharma", "Pharmaceuticals", True, True),
    ("textile", "Textile & Apparel", True, True),
    ("automotive", "Automotive Components", True, False),
    ("agro", "Agro-processing", True, False),
    ("services", "Services", False, False),
    ("it", "IT & Software", False, False),
    ("distribution", "Distribution & Logistics", False, False),
]


# ---------------------------------------------------------------------------
# Reference data — idempotent.
# ---------------------------------------------------------------------------

def seed_reference_data() -> None:
    """Create sectors and dimensions if missing."""
    for code, name, order in DIMENSION_SEED:
        if not Dimension.query.filter_by(code=code).first():
            db.session.add(Dimension(code=code, name=name, display_order=order))
    for code, name, is_asset, has_agent in SECTOR_SEED:
        if not Sector.query.filter_by(code=code).first():
            db.session.add(Sector(code=code, name=name,
                                  is_asset_intensive=is_asset,
                                  has_vertical_agent=has_agent))
    db.session.commit()


# ---------------------------------------------------------------------------
# Demo tenants + users — one per role.
# ---------------------------------------------------------------------------

def _get_or_create_tenant(name: str, slug: str, kind: str) -> Tenant:
    t = Tenant.query.filter_by(slug=slug).first()
    if t: return t
    t = Tenant(name=name, slug=slug, tenant_kind=kind)
    db.session.add(t)
    db.session.flush()
    return t


def _get_or_create_user(email: str, full_name: str, role: UserRole,
                       tenant: Tenant, password: str = "demo1234") -> User:
    u = User.query.filter_by(email=email).first()
    if u: return u
    u = User(email=email, full_name=full_name, role=role, tenant_id=tenant.id)
    u.set_password(password)
    db.session.add(u)
    db.session.flush()
    # Grant the role-default module set (OWNER/ADMIN bypass; others get rows).
    if role not in (UserRole.OWNER, UserRole.ADMIN):
        for code in default_modules_for_role(role):
            db.session.add(UserModulePermission(
                tenant_id=tenant.id, user_id=u.id,
                module_code=code, granted_by_user_id=u.id,
            ))
    return u


def seed_demo_tenant() -> dict:
    """Create demo tenants + one user per role. Idempotent."""
    already = Tenant.query.filter_by(slug="demo-sme").first() is not None

    # --- SME tenant with OWNER + OPERATOR ---
    sme_tenant = _get_or_create_tenant("Demo SME", "demo-sme", "sme")
    _get_or_create_user("owner@demo.nichebrains.ai",
                        "Demo Owner", UserRole.OWNER, sme_tenant)
    _get_or_create_user("operator@demo.nichebrains.ai",
                        "Demo Operator", UserRole.OPERATOR, sme_tenant)

    # --- Expert tenant + EXPERT user + Expert profile ---
    expert_tenant = _get_or_create_tenant(
        "Demo Expert Practice", "demo-expert", "expert")
    _get_or_create_user("expert@demo.nichebrains.ai",
                        "Priya Rao", UserRole.EXPERT, expert_tenant)
    # Also ensure an Expert row exists (with matching Person).
    if not Expert.query.filter_by(tenant_id=expert_tenant.id).first():
        person = Person.query.filter_by(email="expert@demo.nichebrains.ai").first()
        if not person:
            person = Person(full_name="Priya Rao",
                           email="expert@demo.nichebrains.ai")
            db.session.add(person)
            db.session.flush()
        db.session.add(Expert(
            tenant_id=expert_tenant.id, person_id=person.id,
            headline="Operations & Lean specialist",
            expertise_codes=["ops.lean", "ops.oee"],
            sector_codes=["manufacturing", "textile"],
            languages=["en", "hi"],
            states_served=["Maharashtra", "Gujarat"],
            availability_score=0.9,
            has_anchor_evidence="true",
        ))

    # --- Partner tenant + PARTNER user ---
    partner_tenant = _get_or_create_tenant(
        "Demo Partner Alliance", "demo-partner", "partner")
    _get_or_create_user("partner@demo.nichebrains.ai",
                        "Demo Partner", UserRole.PARTNER, partner_tenant)
    if not Partner.query.filter_by(tenant_id=partner_tenant.id).first():
        db.session.add(Partner(
            tenant_id=partner_tenant.id,
            name="Demo Partner Alliance",
            partner_kind="association",
            sector_codes=["manufacturing", "textile"],
            states=["Gujarat", "Maharashtra", "Karnataka"],
            contact_email="partner@demo.nichebrains.ai",
        ))

    # --- Platform tenant + ADMIN user ---
    platform_tenant = _get_or_create_tenant(
        "Demo Platform", "demo-platform", "sme")
    _get_or_create_user("admin@demo.nichebrains.ai",
                        "Demo Admin", UserRole.ADMIN, platform_tenant)

    db.session.commit()
    return {
        "already_present": already,
        "users": [
            "owner@demo.nichebrains.ai",
            "operator@demo.nichebrains.ai",
            "expert@demo.nichebrains.ai",
            "partner@demo.nichebrains.ai",
            "admin@demo.nichebrains.ai",
        ],
        "password": "demo1234",
    }
