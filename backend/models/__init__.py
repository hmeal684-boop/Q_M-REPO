"""Database models for conversations and enrollment drafts."""

from datetime import date, datetime, timezone
from uuid import uuid4

from backend.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


def new_id():
    return str(uuid4())


class Conversation(db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.String(36), primary_key=True, default=new_id)
    user_id = db.Column(
        db.String(36), db.ForeignKey("users.id"), nullable=True, index=True
    )
    active_intent = db.Column(db.String(32), nullable=True)
    pending_followup = db.Column(db.String(32), nullable=True)
    status = db.Column(db.String(32), nullable=False, default="active")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    messages = db.relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
    enrollment_draft = db.relationship(
        "EnrollmentDraft",
        back_populates="conversation",
        cascade="all, delete-orphan",
        uselist=False,
    )
    user = db.relationship("User", back_populates="conversations")


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.String(36), primary_key=True, default=new_id)
    conversation_id = db.Column(
        db.String(36), db.ForeignKey("conversations.id"), nullable=False, index=True
    )
    role = db.Column(db.String(16), nullable=False)
    content = db.Column(db.Text, nullable=False)
    agent_name = db.Column(db.String(64), nullable=True)
    detected_intent = db.Column(db.String(32), nullable=True)
    classification_confidence = db.Column(db.Float, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    image_alt = db.Column(db.String(500), nullable=True)
    image_status = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    conversation = db.relationship("Conversation", back_populates="messages")


class EnrollmentDraft(db.Model):
    __tablename__ = "enrollment_drafts"

    id = db.Column(db.String(36), primary_key=True, default=new_id)
    conversation_id = db.Column(
        db.String(36),
        db.ForeignKey("conversations.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    course = db.Column(db.String(255), nullable=True)
    full_name = db.Column(db.String(255), nullable=True)
    nric = db.Column(db.String(16), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    email = db.Column(db.String(320), nullable=True)
    preferred_intake_date = db.Column(db.Date, nullable=True)
    mobile_number = db.Column(db.String(32), nullable=True)
    payment_method = db.Column(db.String(32), nullable=True)
    skillsfuture_amount = db.Column(db.Numeric(10, 2), nullable=True)
    paynow_amount = db.Column(db.Numeric(10, 2), nullable=True)
    status = db.Column(db.String(32), nullable=False, default="collecting")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    confirmed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    conversation = db.relationship("Conversation", back_populates="enrollment_draft")


from backend.models.accounts import User


__all__ = [
    "Conversation",
    "EnrollmentDraft",
    "Message",
    "User",
    "date",
    "db",
    "utc_now",
]
