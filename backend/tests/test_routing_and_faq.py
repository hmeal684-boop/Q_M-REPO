"""Intent routing and grounded FAQ behavior."""

from decimal import Decimal

from backend.services.course_catalogue import CourseCatalogue
from backend.tests.conftest import send
from backend.services.chat_service import clean_customer_copy


def test_company_course_information_is_loaded_without_invented_intakes():
    catalogue = CourseCatalogue()
    assert catalogue.course_name == "2-Day Basic Certificate in Dental Assisting"
    assert catalogue.course_fee == Decimal("600")
    assert catalogue.course["duration"] == "two consecutive days"
    assert catalogue.course["training_time"] == "9:30am to 5:30pm on each day"
    assert catalogue.course["venue"] == "Q&M HQ, Clementi Loop"
    assert catalogue.course["paynow"]["uen"] == "201841969G"
    assert catalogue.intake_dates == []


def test_faq_routes_to_faq_agent_with_customer_friendly_copy(client, conversation_id):
    response = send(client, conversation_id, "What course is available?")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["routing"]["intent"] == "faq"
    assert payload["routing"]["agent"] == "faq_agent"
    assert "2-Day Basic Certificate" in payload["message"]["content"]
    assert "prototype" not in payload["message"]["content"].casefold()
    assert "fictional" not in payload["message"]["content"].casefold()


def test_fee_reply_is_concise_and_customer_friendly(client, conversation_id):
    payload = send(client, conversation_id, "How much is the course fee?").get_json()
    assert "S$600 nett" in payload["message"]["content"]
    assert "💳" in payload["message"]["content"]


def test_duration_and_training_time_are_from_company_information(
    client, conversation_id
):
    payload = send(client, conversation_id, "How long is the course and what time is it?").get_json()
    reply = payload["message"]["content"]
    assert "two consecutive days" in reply
    assert "9:30am to 5:30pm" in reply


def test_skillsfuture_basic_tier_is_accepted(client, conversation_id):
    payload = send(client, conversation_id, "Can I use SkillsFuture?").get_json()
    reply = payload["message"]["content"]
    assert "basic-tier SkillsFuture Credits" in reply
    assert "sfc.myskillsfuture.gov.sg/claim" in reply


def test_mid_career_skillsfuture_is_rejected(client, conversation_id):
    payload = send(
        client, conversation_id, "Can I use Mid-Career SkillsFuture Credits?"
    ).get_json()
    assert "cannot be used" in payload["message"]["content"]


def test_paynow_information_uses_company_uen(client, conversation_id):
    payload = send(client, conversation_id, "Can I pay by PayNow?").get_json()
    reply = payload["message"]["content"]
    assert "PayNow is accepted" in reply
    assert "201841969G" in reply


def test_utap_guidance_explains_reimbursement_rules(client, conversation_id):
    payload = send(client, conversation_id, "How does UTAP work?").get_json()
    reply = payload["message"]["content"]
    assert "pay upfront" in reply
    assert "attend both days" in reply
    assert "within six months" in reply
    assert "cannot be combined with SkillsFuture" in reply


def test_minimum_qualification_guidance(client, conversation_id):
    payload = send(
        client, conversation_id, "What is the minimum qualification?"
    ).get_json()
    reply = payload["message"]["content"]
    assert "GCE N Levels are preferred" in reply
    assert "basic English reading and writing" in reply


def test_job_opportunities_are_not_guaranteed(client, conversation_id):
    payload = send(
        client, conversation_id, "Will I get a job after the course?"
    ).get_json()
    reply = payload["message"]["content"]
    assert "may be considered" in reply
    assert "job is not guaranteed" in reply


def test_missing_current_intakes_use_exact_company_fallback(client, conversation_id):
    payload = send(client, conversation_id, "What course dates are available?").get_json()
    assert payload["message"]["content"].startswith(
        "Our upcoming course dates are being updated. Please leave your contact "
        "details, and our team will confirm the available dates with you."
    )


def test_venue_uses_supplied_reply_template(client, conversation_id):
    payload = send(client, conversation_id, "Where is the course venue?").get_json()
    assert "Q&M HQ, Clementi Loop" in payload["message"]["content"]


def test_course_website_uses_supplied_reply_template(client, conversation_id):
    payload = send(client, conversation_id, "What is the course website?").get_json()
    assert (
        "qandm.edu.sg/Courses/Dental-Assistant/4/Basic-Certificate-In-Dental-Assisting"
        in payload["message"]["content"]
    )


def test_enrollment_process_question_routes_to_faq(client, conversation_id):
    payload = send(client, conversation_id, "How can I enroll?").get_json()
    assert payload["routing"]["intent"] == "faq"
    assert "one detail at a time" in payload["message"]["content"]


def test_unknown_faq_is_answered_honestly(client, conversation_id):
    payload = send(client, conversation_id, "Is parking included with the course?").get_json()
    assert "don’t have" in payload["message"]["content"].casefold()


def test_unclear_message_requests_clarification(client, conversation_id):
    payload = send(client, conversation_id, "Hello there").get_json()
    assert payload["routing"]["intent"] == "unclear"
    assert "learn more about the course" in payload["message"]["content"].casefold()


def test_enrollment_routes_to_enrollment_agent(client, conversation_id):
    payload = send(client, conversation_id, "I would like to register").get_json()
    assert payload["routing"]["intent"] == "enrollment"
    assert payload["routing"]["agent"] == "enrollment_agent"
    assert "full name" in payload["message"]["content"].casefold()


def test_informal_misspelt_enrollment_request_is_understood(client, conversation_id):
    payload = send(client, conversation_id, "i wana enrl").get_json()
    assert payload["routing"]["intent"] == "enrollment"
    assert "full name" in payload["message"]["content"].casefold()


def test_customer_reply_hides_internal_terminology(client, conversation_id):
    payload = send(client, conversation_id, "Tell me about the course").get_json()
    reply = payload["message"]["content"].casefold()
    for hidden_term in (
        "prototype",
        "fictional",
        "synthetic",
        "mock data",
        "crewai",
        "openai",
        "intent classification",
        "routing",
        "faq agent",
    ):
        assert hidden_term not in reply


def test_older_saved_copy_is_cleaned_before_display():
    old_reply = (
        "Prototype notice: fictional demonstration information.\n\n"
        "The fictional prototype course duration is 2 days."
    )
    cleaned = clean_customer_copy(old_reply)
    assert cleaned == "The course duration is 2 days."
