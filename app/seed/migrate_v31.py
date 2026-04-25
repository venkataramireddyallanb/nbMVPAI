"""Idempotent SQLite migration for v3.1 column additions.

The live DB was created before v3.1 added new columns to a handful of
existing tables. SQLite doesn't support `IF NOT EXISTS` on ADD COLUMN,
so we use ``inspect()`` to detect missing columns and only ALTER when
needed. Safe to run multiple times.
"""
from __future__ import annotations

from sqlalchemy import inspect, text

from app.extensions import db


# Each row: (table_name, column_name, full SQLite column DDL)
EXPECTED_COLUMNS: list[tuple[str, str, str]] = [
    # Person — DDExpert v3.1 §14 sub-personas.
    ("persons", "sub_persona", "VARCHAR(20)"),

    # AssessmentRun — Horizon + Priority + Transformation (v3.1 §4.1, §7.1, Table 4).
    ("assessment_runs", "horizon",                 "VARCHAR(20)"),
    ("assessment_runs", "priority_mode",           "VARCHAR(30)"),
    ("assessment_runs", "priority_dimension",      "VARCHAR(4)"),
    ("assessment_runs", "priority_driver",         "VARCHAR(30)"),
    ("assessment_runs", "transformation_type",     "VARCHAR(20)"),
    ("assessment_runs", "transformation_secondary","VARCHAR(20)"),

    # FirmFinancials may be entirely missing on very old DBs — but that's
    # handled by db.create_all() at the call site, not by ALTER.
]


def detect_missing() -> list[tuple[str, str, str]]:
    """Return rows that need an ALTER on the current DB."""
    insp = inspect(db.engine)
    missing: list[tuple[str, str, str]] = []
    for table, column, ddl in EXPECTED_COLUMNS:
        if not insp.has_table(table):
            # Whole table missing — caller should run db.create_all() first.
            continue
        existing = {c["name"] for c in insp.get_columns(table)}
        if column not in existing:
            missing.append((table, column, ddl))
    return missing


def migrate() -> dict:
    """Apply every missing v3.1 column. Idempotent."""
    # First, make sure any *new* tables (FirmFinancials, UserModulePermission,
    # etc.) actually exist. create_all() is idempotent — it only creates what's
    # missing and never drops anything.
    db.create_all()

    missing = detect_missing()
    applied = []
    for table, column, ddl in missing:
        sql = f'ALTER TABLE {table} ADD COLUMN {column} {ddl}'
        db.session.execute(text(sql))
        applied.append(f"{table}.{column}")

    db.session.commit()
    return {"applied_count": len(applied), "applied": applied}
