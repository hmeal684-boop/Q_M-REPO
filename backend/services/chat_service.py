"""Conversation orchestration with application-controlled agent routing."""

import re
from datetime import timezone

from backend.extensions import db
from backend.services.enrollment_service import EnrollmentService
from backend.services.privacy import mask_nrics_in_text, redact_for_classification


UNCLEAR_REPLY = (
    "Hi! 👋 Would you like to learn more about the course, or would you like to enroll?"
)


class ChatService:
    def __init__(self, repository, catalogue, ai_service, context_limit=20):
        self.repository = repository
        self.catalogue = catalogue
        self.ai_service = ai_service
        self.context_limit = context_limit
        self.enrollment = EnrollmentService(ai_service, catalogue, repository)

    def respond(self, conversation, user_text):
        user_message = self.repository.add_message(
            conversation, "user", user_text, agent_name="intent_classifier"
        )
        db.session.commit()
        recent_messages = self.repository.recent_messages(
            conversation, self.context_limit + 1
        )
        prior_messages = [
            message for message in recent_messages if message.id != user_message.id
        ][-self.context_limit :]

        draft = conversation.enrollment_draft
        classification = self.ai_service.classify(
            message=redact_for_classification(user_text),
            context=self._format_context(prior_messages, redact=True),
            active_intent=conversation.active_intent,
            draft_status=draft.status if draft else None,
        )
        user_message.detected_intent = classification.intent
        user_message.classification_confidence = classification.confidence

        if classification.intent == "faq":
            if not self.catalogue.has_intake_dates and _is_intake_question(user_text):
                reply = self.catalogue.no_intakes_message
            else:
                reply = self.ai_service.answer_faq(
                    message=redact_for_classification(user_text),
                    context=self._format_context(prior_messages, redact=True),
                    catalogue_context=self.catalogue.agent_context(),
                ).answer.strip()
            reply = clean_customer_copy(reply)
            agent_name = "faq_agent"
            if draft and draft.status != "confirmed":
                name = _first_name(draft.full_name)
                continuation = "We can continue your enrollment whenever you’re ready."
                if name:
                    continuation = f"{name}, we can continue your enrollment whenever you’re ready."
                reply += f"\n\n{continuation}"
            elif conversation.active_intent != "enrollment":
                conversation.active_intent = "faq"
                if "enroll" not in reply.casefold() and "enrol" not in reply.casefold():
                    reply += "\n\nWould you like to begin an enrollment?"
        elif classification.intent == "enrollment":
            conversation.active_intent = "enrollment"
            reply, draft = self.enrollment.handle(
                conversation,
                user_text,
                self._format_context(prior_messages),
            )
            agent_name = "enrollment_agent"
        else:
            reply = UNCLEAR_REPLY
            agent_name = "intent_classifier"

        assistant_message = self.repository.add_message(
            conversation,
            "assistant",
            reply,
            agent_name=agent_name,
            detected_intent=classification.intent,
            classification_confidence=classification.confidence,
        )
        db.session.commit()

        return {
            "conversation_id": conversation.id,
            "message": serialize_message(assistant_message),
            "routing": {
                "intent": classification.intent,
                "confidence": classification.confidence,
                "agent": agent_name,
            },
            "enrollment": serialize_enrollment(draft, self.catalogue),
        }

    @staticmethod
    def _format_context(messages, redact=False):
        lines = []
        for message in messages:
            content = (
                redact_for_classification(message.content)
                if redact
                else mask_nrics_in_text(message.content)
            )
            lines.append(f"{message.role}: {content}")
        return "\n".join(lines)


def serialize_message(message):
    timestamp = message.created_at
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return {
        "id": message.id,
        "role": message.role,
        "content": clean_customer_copy(mask_nrics_in_text(message.content))
        if message.role == "assistant"
        else mask_nrics_in_text(message.content),
        "agent_name": message.agent_name,
        "detected_intent": message.detected_intent,
        "classification_confidence": message.classification_confidence,
        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
    }


def serialize_enrollment(draft, catalogue=None):
    if draft is None:
        return {"status": None, "missing_fields": []}
    return {
        "status": draft.status,
        "missing_fields": EnrollmentService.missing_fields(draft, catalogue),
    }


def clean_customer_copy(content):
    """Remove wording retained in older local conversation records."""
    cleaned = re.sub(
        r"(?i)prototype enrollment summary \(not an official Q&M enrollment\):",
        "Please confirm your enrollment details:",
        content or "",
    )
    cleaned = re.sub(
        r"(?i)your enrollment draft is still saved\. We can continue it whenever you are ready\.",
        "We can continue your enrollment whenever you’re ready.",
        cleaned,
    )
    cleaned = re.sub(
        r"(?im)^prototype notice:.*(?:\r?\n)*",
        "",
        cleaned,
    )
    cleaned = re.sub(
        r"(?i)this is not (?:an? )?official Q&M (?:information|enrollment)\.?",
        "",
        cleaned,
    )
    cleaned = re.sub(r"(?i)\b(?:fictional|synthetic|mock|prototype)\b\s*", "", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if re.search(
        r"(?i)\b(?:crewai|openai|intent classification|routing|mock response|next stage)\b",
        cleaned,
    ):
        return "I can help with course information or guide you through enrollment."
    return cleaned or "I’m sorry, I don’t have that information at the moment."


def _first_name(full_name):
    return full_name.split()[0] if full_name else None


def _is_intake_question(message):
    lowered = message.casefold()
    return any(term in lowered for term in ("course date", "intake", "available date"))
