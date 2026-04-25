"""API v1 — single Flask-RESTX Api aggregating all namespaces.

The api object is mounted at /api/v1 by the app factory. Swagger UI
is exposed at /api/v1/docs/.
"""
from __future__ import annotations

from flask import Blueprint
from flask_restx import Api

from app.api.v1.schemas import register_shared_models
from app.api.v1.namespaces.admin import ns as admin_ns
from app.api.v1.namespaces.auth import ns as auth_ns
from app.api.v1.namespaces.charters import ns as charters_ns
from app.api.v1.namespaces.experts import ns as experts_ns
from app.api.v1.namespaces.firms import ns as firms_ns
from app.api.v1.namespaces.nra import ns as nra_ns
from app.api.v1.namespaces.partner import ns as partner_ns
from app.api.v1.namespaces.prescreener import ns as prescreener_ns
from app.api.v1.namespaces.snapshot import ns as snapshot_ns
from app.api.v1.namespaces.platform import ns as platform_ns
from app.api.v1.namespaces.users import ns as users_ns

api_v1_bp = Blueprint("api_v1", __name__)

# JWT bearer security scheme — surfaces the Authorize button in Swagger UI.
authorizations = {
    "Bearer": {
        "type": "apiKey",
        "in": "header",
        "name": "Authorization",
        "description": (
            "JWT Bearer token. Format: Bearer <access_token>. "
            "Obtain a token from POST /auth/login or POST /auth/register."
        ),
    }
}

api = Api(
    api_v1_bp,
    version="5.0",
    title="nicheBrains API",
    description=(
        "REST API for nicheBrains v5.0 — the AI-native digital transformation "
        "platform for Indian MSMEs (INR 10-500 Cr revenue band).\n\n"
        "Authentication. Call POST /auth/login with email + password to "
        "receive an access_token. Pass it on every subsequent call via the "
        "Authorization: Bearer <token> header (click the Authorize button).\n\n"
        "Multi-tenant. Every domain row (Firm, Charter, Score, etc.) is scoped "
        "to the caller tenant. Cross-tenant reads return 403.\n\n"
        "Spec invariants enforced server-side:\n"
        "- Scores 35 / 65 / 85 are unreachable (Acceptance Criterion #1)\n"
        "- Instant Snapshot is strictly read-only (AC #9)\n"
        "- Exactly 2 LLM agents in production (AC #10)\n"
        "- Initiative shortlist: 3-5 (AC #6)\n"
        "- Expert match top-3 only; anchor evidence (L0/L3) required\n"
        "- Benchmarks require cohort >= 20 (PII guard)\n"
        "- Agents never sign, pay, or commit"
    ),
    doc="/docs/",
    authorizations=authorizations,
    security="Bearer",
    validate=True,
    contact="nicheBrains engineering",
    contact_email="engineering@nichebrains.ai",
    license="Proprietary",
)

register_shared_models(api)

api.add_namespace(platform_ns, path="/platform")
api.add_namespace(auth_ns, path="/auth")
api.add_namespace(users_ns, path="/users")
api.add_namespace(firms_ns, path="/firms")
api.add_namespace(snapshot_ns, path="/snapshot")
api.add_namespace(prescreener_ns, path="/prescreener")
api.add_namespace(nra_ns, path="/nra")
api.add_namespace(charters_ns, path="/charters")
api.add_namespace(experts_ns, path="/experts")
api.add_namespace(partner_ns, path="/partner")
api.add_namespace(admin_ns, path="/admin")
