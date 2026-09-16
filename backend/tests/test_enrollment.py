"""Enrollment collection, validation, correction, and confirmation tests."""

import json
from decimal import Decimal

import pytest

from backend.app import create_app
from backend.extensions import db
from backend.models import EnrollmentDraft
from backend.services.course_catalogue import CATALOGUE_PATH, CourseCatalogue
from backend.services.validation import has_valid_identity_checksum, validate_field
from backend.tests.conftest import FakeAIService, send


SYNTHETIC_NAME = "Test Student"
SYNTHETIC_NRIC = "S1234567D"
SYNTHETIC_EMAIL = "test.student@example.com"
SYNTHETIC_MOBILE = "91234567"


def complete_draft(client, conversation_id, payment_message="I will pay by PayNow"):
    send(client, conversation_id, "I want to enroll")
    send(client, conversation_id, f"My name is {SYNTHETIC_NAME}")
    send(client, conversation_id, f"My NRIC is {SYNTHETIC_NRIC}")
    send(client, conversation_id, "My DOB is 1990-01-02")
    send(client, conversation_id, f"My email is {SYNTHETIC_EMAIL}")
    send(client, conversation_id, f"My mobile number is {SYNTHETIC_MOBILE}")
    return send(client, conversation_id, payment_message)


@pytest.fixture()
def dated_catalogue(tmp_path):
    data = json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))
    data["course"]["intakes"] = [
        {"date": "2027-10-17", "display": "17 October 2027"}
    ]
    path = tmp_path / "course_information.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return CourseCatalogue(path)


def test_agent_collects_one_missing_field_at_a_time(client, conversation_id):
    first = send(client, conversation_id, "I want to enroll").get_json()
    second = send(
        client, conversation_id, f"My name is {SYNTHETIC_NAME}"
    ).get_json()
    assert "full name" in first["message"]["content"].casefold()
    assert "nric" in second["message"]["content"].casefold()
    assert "Test" in second["message"]["content"]


def test_multiple_fields_can_be_extracted_from_one_message(client, conversation_id):
    send(client, conversation_id, "I want to enroll")
    response = send(
        client,
        conversation_id,
        f"Full name: {SYNTHETIC_NAME}; NRIC: {SYNTHETIC_NRIC}; "
        f"DOB: 1990-01-02; email: {SYNTHETIC_EMAIL}; "
        f"mobile: {SYNTHETIC_MOBILE}; PayNow",
    )
    payload = response.get_json()
    assert payload["enrollment"]["status"] == "awaiting_confirmation"
    assert payload["enrollment"]["missing_fields"] == []
    assert "S*******D" in payload["message"]["content"]
    assert "S$600.00" in payload["message"]["content"]


def test_no_dates_saves_enrollment_awaiting_course_date_confirmation(
    app, client, conversation_id
):
    summary = complete_draft(client, conversation_id).get_json()
    assert summary["enrollment"]["status"] == "awaiting_confirmation"
    assert "Awaiting confirmation from our team" in summary["message"]["content"]

    confirmation = send(client, conversation_id, "Yes, confirm").get_json()
    assert confirmation["enrollment"]["status"] == "awaiting_course_date"
    assert "team will confirm an available date" in confirmation["message"]["content"]
    with app.app_context():
        saved = EnrollmentDraft.query.one()
        assert saved.preferred_intake_date is None
        assert saved.confirmed_at is not None


def test_all_nine_enrollment_fields_are_stored_and_confirmed(
    tmp_path, fake_ai, dated_catalogue
):
    from backend.app import create_app

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'dated.db').as_posix()}",
        },
        ai_service=fake_ai,
        catalogue=dated_catalogue,
    )
    client = app.test_client()
    conversation_id = client.post("/api/conversations").get_json()["conversation_id"]
    send(client, conversation_id, "I want to enroll")
    response = send(
        client,
        conversation_id,
        "Intake: 17 October 2027; "
        f"full name: {SYNTHETIC_NAME}; NRIC: {SYNTHETIC_NRIC}; "
        f"DOB: 1990-01-02; email: {SYNTHETIC_EMAIL}; "
        f"mobile: {SYNTHETIC_MOBILE}; SkillsFuture S$400; PayNow S$200",
    ).get_json()
    assert response["enrollment"] == {
        "status": "awaiting_confirmation",
        "missing_fields": [],
    }
    assert "SkillsFuture amount: S$400.00" in response["message"]["content"]
    assert "PayNow amount: S$200.00" in response["message"]["content"]

    confirmed = send(client, conversation_id, "confirm").get_json()
    assert confirmed["enrollment"]["status"] == "confirmed"
    with app.app_context():
        draft = EnrollmentDraft.query.one()
        values = (
            draft.preferred_intake_date,
            draft.full_name,
            draft.nric,
            draft.date_of_birth,
            draft.email,
            draft.mobile_number,
            draft.payment_method,
            draft.skillsfuture_amount,
            draft.paynow_amount,
        )
        assert all(value is not None for value in values)
        assert draft.payment_method == "skillsfuture_paynow"
        assert draft.skillsfuture_amount == Decimal("400.00")
        assert draft.paynow_amount == Decimal("200.00")


def test_repeated_confirmation_does_not_create_duplicate(app, client, conversation_id):
    complete_draft(client, conversation_id)
    send(client, conversation_id, "confirm")
    repeated = send(client, conversation_id, "confirm").get_json()
    assert "details are saved" in repeated["message"]["content"]
    with app.app_context():
        assert db.session.query(EnrollmentDraft).count() == 1


def test_user_can_correct_a_field_before_confirmation(client, conversation_id):
    complete_draft(client, conversation_id)
    corrected = send(
        client, conversation_id, "Change my email to corrected@example.com"
    ).get_json()
    assert corrected["enrollment"]["status"] == "awaiting_confirmation"
    assert "Thanks, Test. I’ve updated your email address." in corrected["message"]["content"]
    assert "corrected@example.com" in corrected["message"]["content"]


def test_faq_interruption_preserves_and_resumes_enrollment(client, conversation_id):
    send(client, conversation_id, "I want to enroll")
    send(client, conversation_id, f"My name is {SYNTHETIC_NAME}")
    faq = send(client, conversation_id, "What is the course fee?").get_json()
    assert faq["routing"]["intent"] == "faq"
    assert "continue your enrolment" in faq["message"]["content"]
    resumed = send(client, conversation_id, f"My NRIC is {SYNTHETIC_NRIC}").get_json()
    assert resumed["routing"]["intent"] == "enrollment"
    assert "date of birth" in resumed["message"]["content"].casefold()


def test_paynow_payment_defaults_are_stored(app, client, conversation_id):
    complete_draft(client, conversation_id)
    with app.app_context():
        draft = EnrollmentDraft.query.one()
        assert draft.payment_method == "paynow"
        assert draft.skillsfuture_amount == Decimal("0.00")
        assert draft.paynow_amount == Decimal("600.00")


def test_utap_requires_upfront_payment_without_skillsfuture(app, client, conversation_id):
    complete_draft(client, conversation_id, "I will use UTAP")
    with app.app_context():
        draft = EnrollmentDraft.query.one()
        assert draft.payment_method == "utap"
        assert draft.skillsfuture_amount == Decimal("0.00")
        assert draft.paynow_amount == Decimal("600.00")


def test_skillsfuture_and_paynow_must_total_course_fee(client, conversation_id):
    send(client, conversation_id, "I want to enroll")
    response = send(
        client, conversation_id, "SkillsFuture S$400 and PayNow S$100"
    ).get_json()
    assert "must total S$600" in response["message"]["content"]


def test_later_payment_extraction_cannot_revalidate_or_replace_saved_identity(
    tmp_path,
):
    class EchoingDraftFieldsAI(FakeAIService):
        def extract_enrollment(self, message, context, draft_state):
            result = super().extract_enrollment(message, context, draft_state)
            if "remaining" in message.casefold():
                result.extracted_fields.nric = draft_state["nric"]
                result.extracted_fields.full_name = "Unrelated Person"
                result.extracted_fields.date_of_birth = "[DATE REDACTED]"
                result.extracted_fields.email = ""
                result.extracted_fields.mobile_number = "80000000"
                result.extracted_fields.payment_method = "PayNow"
            return result

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'echoed.db').as_posix()}",
        },
        ai_service=EchoingDraftFieldsAI(),
    )
    client = app.test_client()
    conversation_id = client.post("/api/conversations").get_json()["conversation_id"]
    for message in (
        "I want to enroll",
        f"My name is {SYNTHETIC_NAME}",
        f"My NRIC is {SYNTHETIC_NRIC}",
        "My DOB is 15 May 2000",
        f"My email is {SYNTHETIC_EMAIL}",
        f"My mobile number is {SYNTHETIC_MOBILE}",
    ):
        send(client, conversation_id, message)

    payment = send(
        client,
        conversation_id,
        "I want to use $400 SkillsFuture and pay the remaining $200 by PayNow.",
    ).get_json()

    assert payment["enrollment"] == {
        "status": "awaiting_confirmation",
        "missing_fields": [],
    }
    assert "valid Singapore NRIC" not in payment["message"]["content"]
    assert "S1234567D" not in payment["message"]["content"]
    assert "S*******D" in payment["message"]["content"]
    with app.app_context():
        draft = EnrollmentDraft.query.filter_by(
            conversation_id=conversation_id
        ).one()
        assert draft.full_name == SYNTHETIC_NAME
        assert draft.nric == SYNTHETIC_NRIC
        assert draft.date_of_birth.isoformat() == "2000-05-15"
        assert draft.email == SYNTHETIC_EMAIL
        assert draft.mobile_number == SYNTHETIC_MOBILE
        assert draft.payment_method == "skillsfuture_paynow"
        assert draft.skillsfuture_amount == Decimal("400.00")
        assert draft.paynow_amount == Decimal("200.00")


def test_extraction_cannot_fill_a_field_absent_from_the_current_message(tmp_path):
    class InventingAI(FakeAIService):
        def extract_enrollment(self, message, context, draft_state):
            result = super().extract_enrollment(message, context, draft_state)
            if "nric" in message.casefold():
                result.extracted_fields.email = "invented@example.com"
                result.extracted_fields.mobile_number = "89999999"
            return result

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'invented.db').as_posix()}",
        },
        ai_service=InventingAI(),
    )
    client = app.test_client()
    conversation_id = client.post("/api/conversations").get_json()["conversation_id"]
    send(client, conversation_id, "I want to enroll")
    send(client, conversation_id, f"My name is {SYNTHETIC_NAME}")
    send(client, conversation_id, f"My NRIC is {SYNTHETIC_NRIC}")

    with app.app_context():
        draft = EnrollmentDraft.query.filter_by(
            conversation_id=conversation_id
        ).one()
        assert draft.nric == SYNTHETIC_NRIC
        assert draft.email is None
        assert draft.mobile_number is None


def test_valid_nric_checksum_is_accepted_and_wrong_checksum_is_rejected():
    assert has_valid_identity_checksum(SYNTHETIC_NRIC) is True
    valid, valid_error = validate_field("nric", SYNTHETIC_NRIC, CourseCatalogue())
    assert valid == SYNTHETIC_NRIC
    assert valid_error is None

    invalid, invalid_error = validate_field("nric", "S1234567A", CourseCatalogue())
    assert invalid is None
    assert "checksum" in invalid_error


def test_enrollment_drafts_do_not_leak_between_conversations(app, client):
    first_id = client.post("/api/conversations").get_json()["conversation_id"]
    second_id = client.post("/api/conversations").get_json()["conversation_id"]
    send(client, first_id, "I want to enroll")
    send(client, first_id, f"My name is {SYNTHETIC_NAME}")
    send(client, first_id, f"My NRIC is {SYNTHETIC_NRIC}")
    second_reply = send(client, second_id, "I want to enroll").get_json()

    assert second_reply["enrollment"]["missing_fields"][0] == "full_name"
    with app.app_context():
        first = EnrollmentDraft.query.filter_by(conversation_id=first_id).one()
        second = EnrollmentDraft.query.filter_by(conversation_id=second_id).one()
        assert first.nric == SYNTHETIC_NRIC
        assert second.full_name is None
        assert second.nric is None


def test_skillsfuture_and_utap_cannot_be_combined():
    value, error = validate_field(
        "payment_method", "SkillsFuture and UTAP", CourseCatalogue()
    )
    assert value is None
    assert "cannot be combined" in error


def test_mid_career_skillsfuture_cannot_be_used():
    value, error = validate_field(
        "payment_method", "Mid-Career SkillsFuture", CourseCatalogue()
    )
    assert value is None
    assert "cannot be used" in error


def test_unsupported_payment_method_requires_staff_confirmation():
    value, error = validate_field("payment_method", "cash", CourseCatalogue())
    assert value is None
    assert "team will confirm" in error


@pytest.mark.parametrize("value", ["12345678", "71234567", "+65 8123"])
def test_invalid_mobile_number_is_rejected(value):
    normalized, error = validate_field("mobile_number", value, CourseCatalogue())
    assert normalized is None
    assert "valid 8-digit Singapore mobile number" in error


def test_mobile_number_is_normalized():
    normalized, error = validate_field(
        "mobile_number", "+65 9123-4567", CourseCatalogue()
    )
    assert error is None
    assert normalized == SYNTHETIC_MOBILE


def test_invalid_nric_is_rejected(client, conversation_id):
    send(client, conversation_id, "I want to enroll")
    response = send(client, conversation_id, "My NRIC is 1234").get_json()
    assert "valid Singapore NRIC" in response["message"]["content"]


def test_invalid_email_is_rejected(client, conversation_id):
    send(client, conversation_id, "I want to enroll")
    response = send(client, conversation_id, "My email is invalid-email").get_json()
    assert "valid email" in response["message"]["content"]


def test_invalid_dob_is_rejected(client, conversation_id):
    send(client, conversation_id, "I want to enroll")
    response = send(client, conversation_id, "My DOB is 2099-01-01").get_json()
    assert "in the past" in response["message"]["content"]


def test_unconfigured_intake_is_not_accepted(client, conversation_id):
    send(client, conversation_id, "I want to enroll")
    response = send(client, conversation_id, "My intake is 1 January 2030").get_json()
    expected = CourseCatalogue().no_intakes_message
    assert expected in response["message"]["content"]


def test_full_name_must_contain_letters():
    value, error = validate_field("full_name", "12345", CourseCatalogue())
    assert value is None
    assert "containing letters" in error


def test_invalid_course_is_rejected():
    value, error = validate_field("course", "Advanced Orthodontics", CourseCatalogue())
    assert value is None
    assert "currently available" in error
