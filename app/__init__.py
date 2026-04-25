"""nicheBrains backend — application factory.

The factory pattern keeps the app construction free of side-effects so that
unit tests, CLI scripts, and gunicorn workers can each spin up their own
Flask app from the same code path with different configs.

Architecture (clean layering, top to bottom):

    api/         HTTP layer       — Flask-RESTX namespaces, request parsing,
                                   response shaping. NO business rules here.
    services/    Application      — orchestration of repositories + agents
                                   + deterministic engines.
    agents/      AI layer         — CrewAI crew with the 2 production LLM
                                   agents (Narrator + Drafter).
    repositories Data access      — every query is tenant-scoped.
    models/      Domain           — SQLAlchemy ORM mappings.
    schemas/     Contracts        — Marshmallow / RESTX models for I/O.
"""
from __future__ import annotations

import logging
import os
from typing import Type

from flask import Flask, jsonify

from app.config import BaseConfig, get_config
from app.extensions import cors, db, jwt, migrate


def create_app(config_class: Type[BaseConfig] | None = None) -> Flask:
    """Build and return a fully wired Flask application."""
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_class or get_config())

    _configure_logging(app)
    _init_extensions(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_health_check(app)

    return app


# ---------------------------------------------------------------------------
# Wiring helpers — each does ONE thing (Single Responsibility).
# ---------------------------------------------------------------------------

def _configure_logging(app: Flask) -> None:
    """Production-grade logging with consistent format."""
    level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    app.logger.setLevel(level)


def _init_extensions(app: Flask) -> None:
    """Bind shared extension singletons to this app."""
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=True,
    )

    # Importing models here ensures SQLAlchemy sees every mapper before the
    # first request — required for ``db.create_all()`` and Alembic autogen.
    with app.app_context():
        from app import models  # noqa: F401  (side-effect import is intentional)


def _register_blueprints(app: Flask) -> None:
    """Mount the versioned API. Currently v1 only — v2 would slot in here."""
    from app.api.v1 import api_v1_bp

    app.register_blueprint(api_v1_bp, url_prefix="/api/v1")


def _register_error_handlers(app: Flask) -> None:
    """Uniform JSON error envelope across the whole API.

    Frontend code can rely on `{ "error": str, "details": any }` for every
    non-2xx response — no surprise HTML error pages.
    """

    @app.errorhandler(400)
    def _bad_request(e):
        return jsonify(error="bad_request", message=str(e.description)), 400

    @app.errorhandler(401)
    def _unauthorized(e):
        return jsonify(error="unauthorized", message="Authentication required"), 401

    @app.errorhandler(403)
    def _forbidden(e):
        return jsonify(error="forbidden", message=str(e.description)), 403

    @app.errorhandler(404)
    def _not_found(e):
        return jsonify(error="not_found", message="Resource not found"), 404

    @app.errorhandler(500)
    def _server_error(e):
        app.logger.exception("Unhandled server error")
        return jsonify(error="server_error", message="Internal server error"), 500


def _register_health_check(app: Flask) -> None:
    """Cheap liveness probe — no DB hit, no auth."""

    @app.get("/healthz")
    def health():
        return jsonify(
            status="ok",
            app=app.config["APP_NAME"],
            version=app.config["APP_VERSION"],
            env=os.getenv("FLASK_ENV", "development"),
        )
