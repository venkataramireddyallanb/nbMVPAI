"""Module catalogue — the granular permission surface.

Every user-facing feature maps to a module. Admins grant modules
per-user; the ``module_required`` decorator checks the grant at request
time. OWNER + ADMIN roles implicitly have all modules.

The catalogue is STATIC in v5.0. In v6 we'd move it to a DB table so
modules can be added without a code deploy; the static version here is
good enough for a fresh tenant and keeps the inventory obvious in one
place (reviewable by non-engineers).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.user import UserRole


@dataclass(frozen=True)
class Module:
    code: str          # machine code, e.g. 'nra.assess'
    label: str         # human label for admin UI
    group: str         # UI grouping (SME journey / Expert / Partner / Admin)
    description: str


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

CATALOGUE: tuple[Module, ...] = (
    # SME journey
    Module("sme.snapshot", "Instant Snapshot", "SME journey",
           "W0.0 — 60-second sector read (no questions)"),
    Module("sme.prescreener", "Pre-screener", "SME journey",
           "W0.1 — six-question band classifier"),
    Module("sme.nra", "NRA Assessment", "SME journey",
           "W1 — 40-question scoring"),
    Module("sme.charter_view", "Charter view", "SME journey",
           "View drafted Charters"),
    Module("sme.charter_draft", "Charter draft", "SME journey",
           "Draft a new Charter from an assessment"),
    Module("sme.charter_approve", "Charter approve", "SME journey",
           "Gate-1 OWNER sign-off — owner role only"),
    Module("sme.driver_tree", "Driver tree (ROIC)", "SME journey",
           "ROIC decomposition + 12-mo projection"),
    Module("sme.experts_directory", "Expert directory", "SME journey",
           "Browse the expert marketplace"),

    # Expert self-service
    Module("expert.pipeline", "Expert pipeline", "Expert",
           "See charters where you're top-3 matched"),
    Module("expert.profile", "Expert profile", "Expert",
           "Edit your headline, expertise, languages, geography"),
    Module("expert.outcomes", "Expert outcomes", "Expert",
           "Closed charters you delivered"),

    # Partner cohort
    Module("partner.cohort", "Partner cohort", "Partner",
           "Sector benchmark + band distribution (n≥20)"),
    Module("partner.schemes", "Scheme registry", "Partner",
           "Applicable schemes + windows"),

    # Platform — visible to every role by default
    Module("platform.overview", "Platform overview", "Platform",
           "Three-sided platform explainer + 'you are here'"),
    Module("platform.architecture", "Architecture", "Platform",
           "Living product & data architecture page"),

    # Admin (tenant-local)
    Module("admin.users", "User admin", "Admin",
           "List tenant users and assign modules"),
    Module("admin.modules", "Module catalogue", "Admin",
           "Read the module catalogue (for the admin UI itself)"),
)

# Map for O(1) lookup.
BY_CODE: dict[str, Module] = {m.code: m for m in CATALOGUE}


def module_codes() -> list[str]:
    return [m.code for m in CATALOGUE]


# ---------------------------------------------------------------------------
# Role defaults
# ---------------------------------------------------------------------------
# When a user is created, these are the modules they start with.
# An admin can later add or remove modules individually.
# OWNER + ADMIN roles get EVERYTHING (computed, not listed).

ROLE_DEFAULTS: dict[UserRole, tuple[str, ...]] = {
    UserRole.OPERATOR: (
        "sme.snapshot", "sme.prescreener", "sme.nra",
        "sme.charter_view", "sme.charter_draft",
        "sme.driver_tree", "sme.experts_directory",
        "platform.overview", "platform.architecture",
    ),
    UserRole.EXPERT: (
        "expert.pipeline", "expert.profile", "expert.outcomes",
        "platform.overview", "platform.architecture",
    ),
    UserRole.PARTNER: (
        "partner.cohort", "partner.schemes",
        "platform.overview", "platform.architecture",
    ),
    # OWNER and ADMIN: all modules (no list needed — see has_module()).
}


def default_modules_for_role(role: UserRole) -> list[str]:
    """Return the module codes a freshly-created user should start with."""
    if role in (UserRole.OWNER, UserRole.ADMIN):
        return module_codes()
    return list(ROLE_DEFAULTS.get(role, ()))
