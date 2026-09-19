"""Small additive migrations for databases created before migration tooling existed."""

from sqlalchemy import inspect, text

from backend.extensions import db


ENROLLMENT_DRAFT_COLUMNS = {
    "course_fee": "NUMERIC(10, 2)",
    "intake_id": "VARCHAR(64)",
    "intake_start_date": "DATE",
    "intake_end_date": "DATE",
    "intake_is_demo": "BOOLEAN",
    "mobile_number": "VARCHAR(32)",
    "payment_method": "VARCHAR(32)",
    "skillsfuture_amount": "NUMERIC(10, 2)",
    "paynow_amount": "NUMERIC(10, 2)",
}

CONVERSATION_COLUMNS = {
    "user_id": "VARCHAR(36) REFERENCES users(id)",
    "pending_followup": "VARCHAR(32)",
}

MESSAGE_COLUMNS = {
    "image_url": "VARCHAR(500)",
    "image_alt": "VARCHAR(500)",
    "image_status": "VARCHAR(64)",
}


def apply_additive_migrations():
    """Add new nullable enrollment fields without replacing existing data."""
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())

    with db.engine.begin() as connection:
        if "enrollment_drafts" in tables:
            existing = {
                column["name"]
                for column in inspector.get_columns("enrollment_drafts")
            }
            for name, column_type in ENROLLMENT_DRAFT_COLUMNS.items():
                if name not in existing:
                    connection.execute(
                        text(
                            f"ALTER TABLE enrollment_drafts ADD COLUMN "
                            f"{name} {column_type}"
                        )
                    )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_enrollment_drafts_intake_id "
                    "ON enrollment_drafts (intake_id)"
                )
            )

        if "conversations" in tables:
            existing = {
                column["name"] for column in inspector.get_columns("conversations")
            }
            for name, column_type in CONVERSATION_COLUMNS.items():
                if name not in existing:
                    connection.execute(
                        text(
                            f"ALTER TABLE conversations ADD COLUMN "
                            f"{name} {column_type}"
                        )
                    )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_conversations_user_id "
                    "ON conversations (user_id)"
                )
            )

        if "messages" in tables:
            existing = {
                column["name"] for column in inspector.get_columns("messages")
            }
            for name, column_type in MESSAGE_COLUMNS.items():
                if name not in existing:
                    connection.execute(
                        text(
                            f"ALTER TABLE messages ADD COLUMN "
                            f"{name} {column_type}"
                        )
                    )


__all__ = ["apply_additive_migrations"]
