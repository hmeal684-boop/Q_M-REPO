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
            "cost",
            "duration",
            "how long",
            "location",
            "where",
            "funding",
            "course",
            "certificate",
            "capacity",
            "experience",
            "time",
            "date",
            "skillsfuture",
            "mid-career",
            "mid career",
            "paynow",
            "utap",
            "qualification",
            "qualified",
            "job",
            "website",
        )
        enrollment_terms = ("enrol", "enroll", "enrl", "register", "sign up", "apply")
        is_question = "?" in message or lowered.startswith(
            ("what", "when", "where", "can", "could", "how", "is", "do", "does", "tell")
        )
        asks_how_to_enroll = is_question and any(
            term in lowered for term in enrollment_terms
        )
        starts_enrollment = any(term in lowered for term in enrollment_terms)
        if starts_enrollment and not asks_how_to_enroll:
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

    def answer_faq(self, message, context, catalogue_context):
        catalogue = json.loads(catalogue_context)
        course = catalogue["course"]
        lowered = message.casefold()
        if "mid-career" in lowered or "mid career" in lowered:
            answer = "Mid-Career SkillsFuture Credits cannot be used for this course."
        elif "skillsfuture" in lowered or "funding" in lowered:
            answer = (
                "You may use basic-tier SkillsFuture Credits for this course. Please "
                f"check your balance and submit your claim at {course['skillsfuture']['claim_page']}."
            )
        elif "utap" in lowered or "union" in lowered:
            answer = (
                "Eligible NTUC Union members may claim 50% of the unfunded course fee, "
                "subject to the annual cap. You must pay upfront, attend both days, and "
                "claim within six months after completion. UTAP cannot be combined with "
                "SkillsFuture Credits."
            )
        elif "paynow" in lowered:
            answer = f"PayNow is accepted using UEN {course['paynow']['uen']}. 💳"
        elif "fee" in lowered or "cost" in lowered or "expensive" in lowered:
            answer = (
                f"The full course fee is {course['fee']['display']}. 💳 Would you like "
                "to know about the payment options?"
            )
        elif "duration" in lowered or "how long" in lowered or "time" in lowered:
            answer = (
                f"Training runs over {course['duration']}, from "
                f"{course['training_time']}. 🦷"
            )
        elif "location" in lowered or "where" in lowered or "venue" in lowered:
            answer = f"The course venue is {course['venue']}."
        elif "date" in lowered or "intake" in lowered or "when" in lowered:
            answer = course["no_intakes_message"]
        elif "qualification" in lowered or "qualified" in lowered or "requirement" in lowered:
            answer = course["minimum_qualification"]
        elif "job" in lowered or "position" in lowered or "work" in lowered:
            answer = course["job_opportunities"]
        elif "website" in lowered or "more details" in lowered:
            answer = f"You can find more course details at {course['website']}."
        elif "enrol" in lowered or "enroll" in lowered or "register" in lowered:
            answer = (
                "I can guide you through enrollment one detail at a time, then show "
                "you a summary to confirm."
            )
        elif "parking" in lowered:
            answer = "I’m sorry, I don’t have parking information at the moment."
        else:
            answer = (
                f"Our {course['name']} is {course['overview'][0].lower()}"
                f"{course['overview'][1:]} 🦷 Would you like to know about the course "
                "fee, dates, or enrollment process?"
            )
        return FAQAnswer(answer=answer)

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
        if skillsfuture_match:
            fields["skillsfuture_amount"] = skillsfuture_match.group(1)

        paynow_match = re.search(
            r"(?:paynow|pay now)(?:\s+amount)?\s*(?:is|:)?\s*(?:s\$|\$)?\s*(\d+(?:\.\d{1,2})?)",
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
