"""Centralised configuration.

Each environment subclasses ``BaseConfig``. ``get_config()`` resolves the
appropriate class from the ``FLASK_ENV`` environment variable so the app
factory stays free of conditional logic.
"""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Load .env once at import time so subclasses can read the values directly.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class BaseConfig:
    """Shared defaults — never instantiated directly."""

    # --- Flask core ---
    APP_NAME: str = os.getenv("APP_NAME", "nicheBrains")
    APP_VERSION: str = os.getenv("APP_VERSION", "5.0.0")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-me")

    # --- SQLAlchemy ---
    SQLALCHEMY_DATABASE_URI: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'nichebrains.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_pre_ping": True,  # avoid stale connections in long-lived workers
    }

    # --- JWT ---
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(os.getenv("ACCESS_TOKEN_EXPIRES_MIN", "30"))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(os.getenv("REFRESH_TOKEN_EXPIRES_DAYS", "14"))
    )

    # --- CORS ---
    CORS_ORIGINS: list[str] = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:4200").split(",")
    ]

    # --- Swagger / RESTX ---
    RESTX_MASK_SWAGGER: bool = False
    RESTX_VALIDATE: bool = True
    RESTX_ERROR_404_HELP: bool = False
    SWAGGER_UI_DOC_EXPANSION: str = "list"

    # --- LLM / Agents ---
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))

    # --- nicheBrains business invariants ---
    # Per DDExpert Foundation Framework v3.1 §13.4 / §14.5: minimum cohort
    # of 10 firms before any benchmark exposure. (v5.0 said 20; v3.1 lowered.)
    # Stored in config so tests can override and so the same value is
    # referenced everywhere (no magic numbers).
    PEER_BENCHMARK_MIN_COHORT: int = int(os.getenv("PEER_BENCHMARK_MIN_COHORT", "10"))
    AUDIT_LOG_RETENTION_YEARS: int = int(os.getenv("AUDIT_LOG_RETENTION_YEARS", "7"))

    # The five dTAS dimensions, canonical short codes used everywhere.
    DIMENSIONS: tuple[str, ...] = ("S", "O", "SM", "T", "SK")

    # Question count per dimension at Org scope (5 dims × 8 = 40).
    QUESTIONS_PER_DIMENSION: int = 8


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = False


class TestingConfig(BaseConfig):
    DEBUG = False
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
    BCRYPT_LOG_ROUNDS = 4  # keep test password hashing fast


class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False
    # Prod must set SECRET_KEY / JWT_SECRET_KEY / DATABASE_URL via env.


_CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None) -> type[BaseConfig]:
    """Resolve a config class by name (defaults to FLASK_ENV)."""
    name = (name or os.getenv("FLASK_ENV", "development")).lower()
    return _CONFIG_MAP.get(name, DevelopmentConfig)
