"""Intent routing and grounded FAQ behavior."""

from decimal import Decimal

from backend.agents.schemas import FAQAnswer
from backend.app import create_app
from backend.services.course_catalogue import CourseCatalogue
from backend.services.chat_service import clean_customer_copy
from backend.tests.conftest import FakeAIService, send


def test_company_course_information_is_loaded_without_invented_intakes():
    catalogue = CourseCatalogue()
    assert catalogue.course_name == "2-Day Basic Certificate in Dental Assisting"
    assert catalogue.course_fee == Decimal("600")
    assert catalogue.course["duration"] == "two consecutive training days"
    assert catalogue.course["training_time"] == "9:30am to 5:30pm on each day"
    assert catalogue.course["venue"]["reply_template_wording"] == "our HQ at Clementi Loop"
    assert catalogue.course["venue"]["confirmation_required"] is True
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


def test_course_description_matches_approved_reply_material(client, conversation_id):
    reply = send(client, conversation_id, "What will I learn in this course?").get_json()[
        "message"
    ]["content"]
    assert "dental instruments and materials" in reply
    assert "infection control" in reply
    assert "anticipate a dentist’s needs" in reply


def test_fee_reply_is_concise_and_customer_friendly(client, conversation_id):
    payload = send(client, conversation_id, "How much is the course fee?").get_json()
    assert "S$600 nett" in payload["message"]["content"]
    assert "course materials" in payload["message"]["content"]
    assert not any(emoji in payload["message"]["content"] for emoji in "👋😊📚📅✅💳")


def test_duration_and_training_time_are_from_company_information(
    client, conversation_id
):
    payload = send(client, conversation_id, "How long is the course and what time is it?").get_json()
    reply = payload["message"]["content"]
    assert "two consecutive training days" in reply
    assert "9:30am to 5:30pm" in reply


def test_skillsfuture_basic_tier_is_accepted(client, conversation_id):
    payload = send(client, conversation_id, "Can I use SkillsFuture?").get_json()
    reply = payload["message"]["content"]
    assert "basic-tier SkillsFuture Credits" in reply
    assert "Mid-Career SkillsFuture Credits cannot be used" in reply
    assert "submit your own claim" in reply
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
    assert "SkillsFuture amount" in reply
    assert not any(emoji in reply for emoji in "👋😊📚📅✅💳")


def test_utap_guidance_explains_reimbursement_rules(client, conversation_id):
    payload = send(client, conversation_id, "How does UTAP work?").get_json()
    reply = payload["message"]["content"]
    assert "pay upfront" in reply
    assert "attend both training days" in reply
    assert "within six months" in reply
    assert "S$250 per year" in reply
    assert "S$500 per year" in reply
    assert "proof of payment and completion" in reply
    assert "NTUC U Portal" in reply
    assert "cannot be combined with SkillsFuture" in reply


def test_misspelt_utap_question_uses_approved_guidance(client, conversation_id):
    reply = send(client, conversation_id, "How does UTP reimbursment wrk?").get_json()[
        "message"
    ]["content"]
    assert "pay upfront" in reply
    assert "within six months" in reply
    assert "NTUC U Portal" in reply


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
    assert "may consider suitable candidates" in reply
    assert "last day of the class" in reply
    assert "interview performance" in reply
    assert "employment is not guaranteed" in reply


def test_missing_current_intakes_use_exact_company_fallback(
    client, conversation_id, fake_ai
):
    payload = send(client, conversation_id, "When is the next class?").get_json()
    assert payload["message"]["content"].startswith(
        "Our upcoming course dates are being updated. Please leave your contact "
        "details, and our team will confirm the available dates with you."
    )
    assert fake_ai.faq_calls[-1]["message"] == "When is the next class?"


def test_misspelt_intake_question_uses_exact_company_fallback(
    client, conversation_id
):
    payload = send(client, conversation_id, "Wen is the nxt intke?").get_json()
    assert payload["message"]["content"].startswith(
        "Our upcoming course dates are being updated. Please leave your contact "
        "details, and our team will confirm the available dates with you."
    )


def test_venue_uses_reply_template_wording_and_flags_source_conflict(
    client, conversation_id
):
    payload = send(client, conversation_id, "Where is the course venue?").get_json()
    reply = payload["message"]["content"]
    assert "our HQ at Clementi Loop" in reply
    assert "different venue" in reply
    assert "team will confirm the exact venue" in reply


def test_course_website_uses_supplied_reply_template(client, conversation_id):
    payload = send(client, conversation_id, "What is the course website?").get_json()
    assert (
        "qandm.edu.sg/Courses/Dental-Assistant/4/Basic-Certificate-In-Dental-Assisting"
        in payload["message"]["content"]
    )


def test_enrollment_process_question_routes_to_faq(client, conversation_id):
    payload = send(client, conversation_id, "How can I enroll?").get_json()
    assert payload["routing"]["intent"] == "faq"
    assert "one at a time" in payload["message"]["content"]
    assert "summary" in payload["message"]["content"]


def test_payment_guidance_uses_only_approved_options(client, conversation_id):
    reply = send(client, conversation_id, "Wat are the paymnt options?").get_json()[
        "message"
    ]["content"]
    assert "PayNow" in reply
    assert "basic-tier SkillsFuture Credits" in reply
    assert "UTAP reimbursement" in reply
    assert "cannot be combined" in reply


def test_payment_screenshot_guidance_prefers_email(client, conversation_id):
    reply = send(
        client, conversation_id, "Can I send my payment screenshot by WhatsApp?"
    ).get_json()["message"]["content"]
    assert "email or WhatsApp" in reply
    assert "Email is the preferred channel" in reply


def test_unknown_faq_is_answered_honestly(client, conversation_id):
    payload = send(client, conversation_id, "Is parking included with the course?").get_json()
    assert "team will need to confirm" in payload["message"]["content"].casefold()


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


def test_misspelt_indirect_fee_question_routes_to_faq(client, conversation_id):
    payload = send(client, conversation_id, "hi, hw much iz da corse?").get_json()
    assert payload["routing"]["intent"] == "faq"
    assert "S$600 nett" in payload["message"]["content"]


def test_customer_first_name_personalises_faq_during_enrollment(
    client, conversation_id
):
    send(client, conversation_id, "Please register me")
    send(client, conversation_id, "My name is Test Student")
    payload = send(client, conversation_id, "How much is the fee?").get_json()
    assert payload["message"]["content"].startswith("Hi Test.")
    assert "continue your enrolment" in payload["message"]["content"]


def test_fabricated_high_risk_facts_are_replaced_with_staff_confirmation(tmp_path):
    class FabricatingAIService(FakeAIService):
        def answer_faq(self, *args, **kwargs):
            return FAQAnswer(
                answer="The fee is S$999 and the next intake is 1 January 2030.",
                matched_topics=["course fee and value"],
            )

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'guard.db').as_posix()}",
        },
        ai_service=FabricatingAIService(),
    )
    client = app.test_client()
    conversation_id = client.post("/api/conversations").get_json()["conversation_id"]
    reply = send(client, conversation_id, "How much is the course fee?").get_json()[
        "message"
    ]["content"]
    assert "S$999" not in reply
    assert "1 January 2030" not in reply
    assert "S$600 nett" in reply
    assert "course materials" in reply


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
