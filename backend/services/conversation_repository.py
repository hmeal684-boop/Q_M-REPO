"""Persistence helpers for conversation state."""

from backend.extensions import db
from backend.models import Conversation, EnrollmentDraft, Message, utc_now


class ConversationRepository:
    def create(self):
        conversation = Conversation()
        db.session.add(conversation)
        db.session.commit()
        return conversation

    def get(self, conversation_id):
        return db.session.get(Conversation, conversation_id)

    def add_message(
        self,
        conversation,
        role,
        content,
        *,
        agent_name=None,
        detected_intent=None,
        classification_confidence=None,
    ):
        conversation.updated_at = utc_now()
        message = Message(
            conversation=conversation,
            role=role,
            content=content,
            agent_name=agent_name,
            detected_intent=detected_intent,
            classification_confidence=classification_confidence,
        )
        db.session.add(message)
        db.session.flush()
        return message

    def recent_messages(self, conversation, limit):
        recent = (
            Message.query.filter_by(conversation_id=conversation.id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )
        return list(reversed(recent))

    def all_messages(self, conversation):
        return (
            Message.query.filter_by(conversation_id=conversation.id)
            .order_by(Message.created_at.asc())
            .all()
        )

    def get_or_create_draft(self, conversation):
        draft = conversation.enrollment_draft
        if draft is None:
            draft = EnrollmentDraft(conversation=conversation)
            db.session.add(draft)
            db.session.flush()
        return draft

    @staticmethod
    def update_draft(draft, values):
        for field, value in values.items():
            setattr(draft, field, value)
        draft.updated_at = utc_now()


__all__ = ["ConversationRepository"]
