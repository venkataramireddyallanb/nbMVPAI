"""Shared Swagger I/O models.

Anything reused across ≥2 namespaces lives here so Swagger UI shows a
single definition in its schemas panel (rather than duplicate copies
named differently).
"""
from __future__ import annotations

from flask_restx import Model, fields


# ---------------------------------------------------------------------------
# Error envelope — every non-2xx response conforms to this shape.
# The app factory's error handlers emit it; handlers that call
# ``ns.abort(...)`` also produce it via Flask-RESTX's default formatter.
# ---------------------------------------------------------------------------

error_envelope = Model("ErrorEnvelope", {
    "error": fields.String(
        required=True,
        example="bad_request",
        description="Stable machine code for the error class",
    ),
    "message": fields.String(
        required=True,
        example="Email already registered",
        description="Human-readable explanation",
    ),
    "details": fields.Raw(
        required=False,
        description="Optional structured details (field errors, etc.)",
    ),
})


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

health_output = Model("Health", {
    "status": fields.String(example="ok"),
    "app": fields.String(example="nicheBrains"),
    "version": fields.String(example="5.0.0"),
    "env": fields.String(example="development"),
})


def register_shared_models(api) -> None:
    """Attach the shared models to an ``Api`` instance.

    Called once from the v1 package __init__. Namespaces reference these
    models by name (``api.models['ErrorEnvelope']``) or import the
    ``error_envelope`` object directly.
    """
    api.models[error_envelope.name] = error_envelope
    api.models[health_output.name] = health_output
