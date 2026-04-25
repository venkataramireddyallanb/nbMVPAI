"""Singleton Flask extensions.

Each extension is instantiated **without** an app object so the same
instance can be shared across the app factory, blueprints, scripts, and
tests. The app factory then calls ``ext.init_app(app)``.
"""
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

# Single source of truth for the SQLAlchemy session/engine.
db = SQLAlchemy()

# Database migrations via Alembic.
migrate = Migrate()

# JWT-based stateless auth.
jwt = JWTManager()

# CORS — origins configured per-env from ``CORS_ORIGINS``.
cors = CORS()


__all__ = ["db", "migrate", "jwt", "cors"]
