"""Small additive migrations for databases created before migration tooling existed."""

from sqlalchemy import inspect, text

from backend.extensions import db


ENROLLMENT_DRAFT_COLUMNS = {
    "mobile_number": "VARCHAR(32)",
    "payment_method": "VARCHAR(32)",
    "skillsfuture_amount": "NUMERIC(10, 2)",
    "paynow_amount": "NUMERIC(10, 2)",
}


def apply_additive_migrations():
    """Add new nullable enrollment fields without replacing existing data."""
    inspector = inspect(db.engine)
    if "enrollment_drafts" not in inspector.get_table_names():
        return

    existing = {
        column["name"] for column in inspector.get_columns("enrollment_drafts")
    }
    missing = [name for name in ENROLLMENT_DRAFT_COLUMNS if name not in existing]
    if not missing:
        return

    with db.engine.begin() as connection:
        for name in missing:
            column_type = ENROLLMENT_DRAFT_COLUMNS[name]
            connection.execute(
                text(f"ALTER TABLE enrollment_drafts ADD COLUMN {name} {column_type}")
            )


__all__ = ["apply_additive_migrations"]
