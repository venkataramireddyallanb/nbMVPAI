"""CLI entry point: ``python manage.py <command>``.

Commands:
    init-db     Create all tables from SQLAlchemy models.
    seed        Populate reference data + a demo tenant.
    shell       Flask shell with models preloaded.
"""
from __future__ import annotations

import sys

from app import create_app
from app.extensions import db
from app.seed.migrate_v31 import migrate as run_migration
from app.seed.seed_data import seed_demo_tenant, seed_reference_data


def init_db(app) -> None:
    with app.app_context():
        db.create_all()
        print("[ok] tables created")


def seed(app) -> None:
    with app.app_context():
        db.create_all()
        seed_reference_data()
        result = seed_demo_tenant()
        print(f"[ok] reference data seeded; demo tenant: {result}")


def migrate(app) -> None:
    """Apply idempotent v3.1 column additions to the live DB."""
    with app.app_context():
        result = run_migration()
        if result["applied_count"] == 0:
            print("[ok] schema already up to date")
        else:
            print(f"[ok] applied {result['applied_count']} migrations:")
            for col in result["applied"]:
                print(f"    + {col}")


COMMANDS = {"init-db": init_db, "seed": seed, "migrate": migrate}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: python manage.py [{' | '.join(COMMANDS)}]")
        return 1
    app = create_app()
    COMMANDS[sys.argv[1]](app)
    return 0


if __name__ == "__main__":
    sys.exit(main())
