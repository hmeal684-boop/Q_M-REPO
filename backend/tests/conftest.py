"""Shared fixtures with a deterministic substitute for OpenAI/Crew execution."""

import json
import re

import pytest

from backend.agents.schemas import (
    AIServiceError,
    EnrollmentExtraction,
    EnrollmentFields,
    FAQAnswer,
    IntentClassification,
)
from backend.app import create_app


class FakeAIService:
    def __init__(self):
        self.classify_calls = []
        self.faq_calls = []
        self.enrollment_calls = []

    def classify(self, message, context, active_intent, draft_status):
        self.classify_calls.append(
            {
                "message": message,
                "context": context,
                "active_intent": active_intent,
                "draft_status": draft_status,
            }
        )
        lowered = message.casefold()
        faq_terms = (
            "fee",
            "fees",
            "cost",
            "much",
            "duration",
            "how long",
            "location",
            "where",
            "whr",
            "venue",
            "held",
            "funding",
            "course",
            "corse",
            "class",
            "classes",
            "certificate",
            "capacity",
            "experience",
            "time",
            "date",
            "skillsfuture",
            "skillfuture",
            "skilsfuture",
            "mid-career",
            "mid career",
            "paynow",
            "pay now",
            "payment",
            "paymnt",
            "screenshot",
            "proof of payment",
            "invoice",
            "claim steps",
            "utap",
            "qualification",
            "qualific",
            "qualified",
            "job",
            "position",
            "website",
        )
        enrollment_terms = (
            "enrol",
            "enroll",
            "enrl",
            "register",
            "regster",
            "sign up",
            "sign upp",
            "apply",
        )
        is_question = "?" in message or lowered.startswith(
            (
                "what",
                "wat",
                "when",
                "where",
                "whr",
                "can",
                "could",
                "how",
                "hw",
                "is",
                "do",
                "does",
                "tell",
            )
        )
        asks_how_to_enroll = is_question and any(
            term in lowered for term in enrollment_terms
        )
        direct_enrollment = any(
            term in lowered
            for term in (
                "i want to enrol",
                "i want to enroll",
                "i wana enrl",
                "i would like to register",
                "please register me",
                "register me",
                "sign me up",
                "sign me upp",
                "ready to enrol",
                "ready to enroll",
            )
        )
        starts_enrollment = any(term in lowered for term in enrollment_terms)
        if direct_enrollment or (starts_enrollment and not asks_how_to_enroll):
            intent = "enrollment"
        elif asks_how_to_enroll or (
            any(term in lowered for term in faq_terms)
            and (is_question or active_intent != "enrollment")
        ):
            intent = "faq"
        elif active_intent == "enrollment":
            intent = "enrollment"
        else:
            intent = "unclear"
        return IntentClassification(
            intent=intent,
            confidence=0.96,
            short_reason="Deterministic test classification.",
        )

    def answer_faq(
        self, message, context, catalogue_context, customer_first_name=None
    ):
        self.faq_calls.append(
            {
                "message": message,
                "context": context,
                "customer_first_name": customer_first_name,
            }
        )
        catalogue = json.loads(catalogue_context)
        course = catalogue["course"]
        lowered = message.casefold()
        faq_answers = {item["topic"]: item["answer"] for item in catalogue["faqs"]}
        topics = []
        asks_fee = any(term in lowered for term in ("fee", "fees", "cost", "much", "expensive"))
        asks_duration = any(term in lowered for term in ("duration", "how long", "time"))
        if "mid-career" in lowered or "mid career" in lowered:
            topics = ["Mid-Career SkillsFuture"]
            answer = faq_answers["Mid-Career SkillsFuture"]
        elif any(term in lowered for term in ("skillsfuture", "skillfuture", "skilsfuture", "funding")):
            topics = ["SkillsFuture"]
            answer = course["skillsfuture"]["customer_reply"]
            answer += f" You can check your balance at {course['skillsfuture']['claim_page']}."
        elif "utap" in lowered or "union" in lowered:
            topics = ["UTAP"]
            answer = course["utap"]["customer_reply"]
        elif "paynow" in lowered or "pay now" in lowered or "uen" in lowered:
            topics = ["PayNow"]
            answer = course["paynow"]["customer_reply"]
        elif any(term in lowered for term in ("payment option", "payment mode", "paymnt")):
            topics = ["payment options"]
            answer = faq_answers["payment options"]
        elif asks_fee and asks_duration:
            topics = ["course fee and value", "duration and timing"]
            answer = (
                f"The full course fee is {course['fee']['display']}. Training runs "
                f"over {course['duration']}, from {course['training_time']}."
            )
        elif asks_fee:
            topics = ["course fee and value"]
            answer = faq_answers["course fee and value"]
        elif asks_duration:
            topics = ["duration and timing"]
            answer = faq_answers["duration and timing"]
        elif "location" in lowered or "where" in lowered or "venue" in lowered:
            topics = ["venue"]
            answer = course["venue"]["customer_reply"]
        elif any(
            term in lowered
            for term in ("date", "intake", "when", "next class", "next course")
        ):
            topics = ["course dates"]
            answer = course["no_intakes_message"]
        elif "qualification" in lowered or "qualified" in lowered or "requirement" in lowered:
            topics = ["minimum qualification"]
            answer = course["minimum_qualification"]
        elif "job" in lowered or "position" in lowered or "work" in lowered:
            topics = ["job opportunities"]
            answer = course["employment"]["customer_reply"]
        elif "website" in lowered or "more details" in lowered:
            topics = ["course website"]
            answer = f"You can find more course details at {course['website']}."
        elif "invoice" in lowered or "claim steps" in lowered:
            topics = ["invoice and claim guidance"]
            answer = faq_answers["invoice and claim guidance"]
        elif "screenshot" in lowered or "proof of payment" in lowered:
            topics = ["payment screenshot channel"]
            answer = faq_answers["payment screenshot channel"]
        elif "enrol" in lowered or "enroll" in lowered or "register" in lowered:
            topics = ["enrolment process"]
            answer = course["enrollment"]["customer_reply"]
        elif "parking" in lowered:
            answer = catalogue["reply_style"]["staff_confirmation_message"]
        else:
            topics = ["course description"]
            answer = faq_answers["course description"]
        if customer_first_name:
            answer = f"Hi {customer_first_name}. {answer}"
        return FAQAnswer(answer=answer, matched_topics=topics)

    def extract_enrollment(self, message, context, draft_state):
        self.enrollment_calls.append(
            {"message": message, "context": context, "draft_state": draft_state}
        )
        lowered = message.casefold().strip()
        fields = {}

        name_match = re.search(
            r"(?:full\s+name|name)\s*(?:is|:)?\s*([A-Za-z][A-Za-z '\-]+?)(?=\s*(?:;|,|\band\b|$))",
            message,
            re.IGNORECASE,
        )
        if name_match:
            fields["full_name"] = name_match.group(1).strip()

        nric_match = re.search(r"\b[STFGM]\d{7}[A-Z]\b", message, re.IGNORECASE)
        if nric_match:
            fields["nric"] = nric_match.group(0)
        elif "nric" in lowered:
            fields["nric"] = message.split()[-1].strip(".,;")

        email_match = re.search(r"\b[^\s,;@]+@[^\s,;@]+\.[^\s,;@]+\b", message)
        if email_match:
            fields["email"] = email_match.group(0)
        elif "email" in lowered:
            fields["email"] = message.split()[-1].strip(".,;")

        dob_match = re.search(
            r"(?:dob|date of birth)\s*(?:is|:)?\s*([^,;]+)", message, re.IGNORECASE
        )
        if dob_match:
            fields["date_of_birth"] = dob_match.group(1).strip()

        intake_match = re.search(
            r"(?:intake|preferred date)\s*(?:is|:)?\s*([^,;]+)",
            message,
            re.IGNORECASE,
        )
        if intake_match:
            fields["preferred_intake_date"] = intake_match.group(1).strip()

        mobile_match = re.search(
            r"(?:mobile|phone|hp)(?:\s+number)?\s*(?:is|:)?\s*(\+?65[\s-]?)?([89]\d{3}[\s-]?\d{4})",
            message,
            re.IGNORECASE,
        )
        if mobile_match:
            fields["mobile_number"] = "".join(
                part for part in mobile_match.groups() if part
            )

        payment_terms = []
        if "mid-career" in lowered or "mid career" in lowered:
            payment_terms.append("Mid-Career SkillsFuture")
        elif "skillsfuture" in lowered or "sfc" in lowered:
            payment_terms.append("SkillsFuture")
        if "utap" in lowered or "union" in lowered:
            payment_terms.append("UTAP")
        if "paynow" in lowered or "pay now" in lowered:
            payment_terms.append("PayNow")
        if any(term in lowered for term in ("cash", "credit card", "cheque")):
            payment_terms.append(message.strip())
        if payment_terms:
            fields["payment_method"] = " and ".join(payment_terms)

        skillsfuture_match = re.search(
            r"(?:skillsfuture|sfc)(?:\s+(?:credit|credits|amount))?\s*(?:is|:)?\s*(?:s\$|\$)?\s*(\d+(?:\.\d{1,2})?)",
            message,
            re.IGNORECASE,
        )
        if not skillsfuture_match:
            skillsfuture_match = re.search(
                r"(?:s\$|\$)?\s*(\d+(?:\.\d{1,2})?)\s*"
                r"(?:of\s+)?(?:skillsfuture|sfc)",
                message,
                re.IGNORECASE,
            )
        if skillsfuture_match:
            fields["skillsfuture_amount"] = skillsfuture_match.group(1)

        paynow_match = re.search(
            r"(?:paynow|pay now)(?:\s+amount)?\s*(?:is|:)?\s*(?:s\$|\$)?\s*(\d+(?:\.\d{1,2})?)",
            message,
            re.IGNORECASE,
        )
        if not paynow_match:
            paynow_match = re.search(
                r"(?:remaining\s+)?(?:s\$|\$)?\s*(\d+(?:\.\d{1,2})?)\s*"
                r"(?:by|via|through)?\s*(?:paynow|pay now)",
                message,
                re.IGNORECASE,
            )
        if paynow_match:
            fields["paynow_amount"] = paynow_match.group(1)

        standalone_amount = re.fullmatch(
            r"(?:s\$|\$)?\s*(\d+(?:\.\d{1,2})?)", message.strip(), re.IGNORECASE
        )
        if standalone_amount and draft_state.get("payment_method") == "skillsfuture_paynow":
            if draft_state.get("skillsfuture_amount") is None:
                fields["skillsfuture_amount"] = standalone_amount.group(1)
            elif draft_state.get("paynow_amount") is None:
                fields["paynow_amount"] = standalone_amount.group(1)

        if "2-day basic certificate" in lowered:
            fields["course"] = "2-Day Basic Certificate in Dental Assisting"

        confirmation = (
            "confirm"
            if lowered in {"yes", "yes, confirm", "confirm", "correct", "all correct"}
            else "reject"
            if lowered in {"no", "not correct"}
            else "none"
        )
        return EnrollmentExtraction(
            extracted_fields=EnrollmentFields(**fields),
            confirmation=confirmation,
            correction_requested=any(
                term in lowered for term in ("change", "correct", "update")
            ),
        )


class FailingAIService(FakeAIService):
    def classify(self, *args, **kwargs):
        raise AIServiceError("provider detail that must not reach the response")


@pytest.fixture()
def fake_ai():
    return FakeAIService()


@pytest.fixture()
def app(tmp_path, fake_ai):
    database_path = (tmp_path / "test.db").as_posix()
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only-secret",
            "OPENAI_API_KEY": "",
            "OPENAI_MODEL": "gpt-5-mini",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
        },
        ai_service=fake_ai,
    )


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def conversation_id(client):
    return client.post("/api/conversations").get_json()["conversation_id"]


def send(client, conversation_id, message):
    return client.post(
        "/api/chat",
        json={"conversation_id": conversation_id, "message": message},
    )
