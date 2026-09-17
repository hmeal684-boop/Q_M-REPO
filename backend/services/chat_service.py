"""Conversation orchestration with application-controlled agent routing."""

import re
from difflib import get_close_matches
from datetime import timezone

from backend.extensions import db
from backend.services.enrollment_service import EnrollmentService
from backend.services.faq_attachments import FAQAttachmentCatalogue
from backend.services.privacy import mask_nrics_in_text, redact_for_classification


UNCLEAR_REPLY = (
    "Hi! 👋 Would you like to learn more about the course, or would you like to enrol?"
)


class ChatService:
    def __init__(self, repository, catalogue, ai_service, context_limit=20):
        self.repository = repository
        self.catalogue = catalogue
        self.ai_service = ai_service
        self.context_limit = context_limit
        self.enrollment = EnrollmentService(ai_service, catalogue, repository)
        self.faq_attachments = FAQAttachmentCatalogue()

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
        if classification.intent == "unclear" and (
            _is_intake_question(user_text) or _is_utap_question(user_text)
        ):
            classification.intent = "faq"
        user_message.detected_intent = classification.intent
        user_message.classification_confidence = classification.confidence

        if classification.intent == "faq":
            name = _first_name(draft.full_name) if draft else None
            faq_result = self.ai_service.answer_faq(
                message=redact_for_classification(user_text),
                context=self._format_context(prior_messages, redact=True),
                catalogue_context=self.catalogue.agent_context(),
                customer_first_name=name,
            )
            if not self.catalogue.has_intake_dates and _is_intake_question(user_text):
                reply = self.catalogue.no_intakes_message
            elif (
                self.catalogue.venue_confirmation_required
                and _is_venue_question(user_text)
            ):
                reply = self.catalogue.approved_faq_reply(["venue"])
            elif _is_utap_question(user_text):
                reply = self.catalogue.approved_faq_reply(["UTAP"])
            else:
                approved_reply = self.catalogue.approved_faq_reply(
                    faq_result.matched_topics
                )
                reply = self.catalogue.ground_faq_answer(approved_reply)
            reply = clean_customer_copy(reply)
            agent_name = "faq_agent"
            if draft and draft.status != "confirmed":
                if name and reply != self.catalogue.no_intakes_message:
                    reply = _personalise_reply(reply, name)
                continuation = self.catalogue.enrollment_faq_resume_prompt
                reply += f"\n\n{continuation}"
            else:
                if name and reply != self.catalogue.no_intakes_message:
                    reply = _personalise_reply(reply, name)
            if conversation.active_intent != "enrollment":
                conversation.active_intent = "faq"
            attachment = self.faq_attachments.for_reply(
                user_text, faq_result.matched_topics
            )
        elif classification.intent == "enrollment":
            conversation.active_intent = "enrollment"
            reply, draft = self.enrollment.handle(
                conversation,
                user_text,
                self._format_context(prior_messages),
            )
            agent_name = "enrollment_agent"
            attachment = None
        else:
            reply = UNCLEAR_REPLY
            agent_name = "intent_classifier"
            attachment = None

        assistant_message = self.repository.add_message(
            conversation,
            "assistant",
            reply,
            agent_name=agent_name,
            detected_intent=classification.intent,
            classification_confidence=classification.confidence,
            image_url=attachment["image_url"] if attachment else None,
            image_alt=attachment["image_alt"] if attachment else None,
            image_status=attachment["image_status"] if attachment else None,
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
    serialized = {
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
    if message.image_url and message.image_alt:
        serialized.update(
            image_url=message.image_url,
            image_alt=message.image_alt,
            image_status=message.image_status,
        )
    return serialized


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
        "Please confirm your enrolment details:",
        content or "",
    )
    cleaned = re.sub(
        r"(?i)your enrollment draft is still saved\. We can continue it whenever you are ready\.",
        "We can continue your enrolment whenever you’re ready.",
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
        return "I can help with course information or guide you through enrolment."
    return cleaned or "I’m sorry, I don’t have that information at the moment."


def _first_name(full_name):
    return full_name.split()[0] if full_name else None


def _is_intake_question(message):
    lowered = message.casefold()
    return _contains_close_word(lowered, "intake") or any(
        term in lowered
        for term in (
            "course date",
            "intake",
            "available date",
            "next class",
            "next course",
            "when is the course",
            "when are the classes",
        )
    )


def _is_utap_question(message):
    return _contains_close_word(message.casefold(), "utap")


def _contains_close_word(message, expected):
    words = re.findall(r"[a-z]+", message.casefold())
    return bool(get_close_matches(expected, words, n=1, cutoff=0.7))


def _is_venue_question(message):
    lowered = message.casefold()
    return any(term in lowered for term in ("where", "venue", "location", "held"))


def _personalise_reply(reply, first_name):
    if re.search(rf"(?i)\b{re.escape(first_name)}\b", reply):
        return reply
    return f"Hi {first_name} 👋\n\n{reply}"
