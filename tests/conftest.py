"""Shared pytest fixtures.

Spins up an in-memory SQLite app per test session and yields a client
with authenticated + unauthenticated helpers.
"""
from __future__ import annotations

import pytest

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.seed.seed_data import seed_reference_data


@pytest.fixture(scope="session")
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        seed_reference_data()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
