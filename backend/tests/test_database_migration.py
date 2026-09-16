"""Coverage for the additive enrollment-field migration."""

import sqlite3

from sqlalchemy import inspect

from backend.app import create_app
from backend.extensions import db
from backend.models import Conversation, EnrollmentDraft


def test_existing_database_data_survives_enrollment_field_migration(tmp_path, fake_ai):
    database_path = tmp_path / "existing.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE conversations (
                id VARCHAR(36) PRIMARY KEY,
                active_intent VARCHAR(32),
                status VARCHAR(32) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
            CREATE TABLE enrollment_drafts (
                id VARCHAR(36) PRIMARY KEY,
                conversation_id VARCHAR(36) NOT NULL UNIQUE,
                course VARCHAR(255),
                full_name VARCHAR(255),
                nric VARCHAR(16),
                date_of_birth DATE,
                email VARCHAR(320),
                preferred_intake_date DATE,
                status VARCHAR(32) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                confirmed_at DATETIME,
                FOREIGN KEY(conversation_id) REFERENCES conversations (id)
            );
            INSERT INTO conversations VALUES (
                'existing-conversation', 'enrollment', 'active',
                '2026-09-01 00:00:00.000000', '2026-09-01 00:00:00.000000'
            );
            INSERT INTO enrollment_drafts VALUES (
                'existing-draft', 'existing-conversation',
                '2-Day Basic Certificate in Dental Assisting', 'Test Student',
                'S1234567D', '2000-05-15', 'test.student@example.com', NULL,
                'collecting', '2026-09-01 00:00:00.000000',
                '2026-09-01 00:00:00.000000', NULL
            );
            """
        )

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path.as_posix()}",
        },
        ai_service=fake_ai,
    )

    with app.app_context():
        columns = {
            column["name"] for column in inspect(db.engine).get_columns("enrollment_drafts")
        }
        assert {
            "mobile_number",
            "payment_method",
            "skillsfuture_amount",
            "paynow_amount",
        } <= columns
        assert db.session.query(Conversation).count() == 1
        draft = db.session.get(EnrollmentDraft, "existing-draft")
        assert draft.full_name == "Test Student"
        assert draft.email == "test.student@example.com"
        assert draft.mobile_number is None
        assert draft.payment_method is None
        assert draft.skillsfuture_amount is None
        assert draft.paynow_amount is None
