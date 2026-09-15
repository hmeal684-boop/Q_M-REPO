"""CrewAI execution adapter.

Application code owns routing and persistence. Each method runs one focused CrewAI
agent and returns a validated Pydantic object.
"""

from crewai import Crew, LLM, Process, Task

from backend.agents.enrollment_agent import build_enrollment_agent
from backend.agents.faq_agent import build_faq_agent
from backend.agents.intent_classifier import build_intent_classifier
from backend.agents.schemas import (
    AIConfigurationError,
    AIServiceError,
    EnrollmentExtraction,
    FAQAnswer,
    IntentClassification,
)


class CrewAIService:
    def __init__(self, api_key, model):
        if not api_key or not model:
            raise AIConfigurationError("The AI service is not configured.")

        self.llm = LLM(
            model=model,
            api_key=api_key,
            reasoning_effort="low",
            max_completion_tokens=1000,
            timeout=60,
            max_retries=2,
        )

    def classify(self, message, context, active_intent, draft_status):
        agent = build_intent_classifier(self.llm)
        task = Task(
            description=(
                "Classify the CURRENT MESSAGE. Use recent redacted context only to "
                "resolve short follow-ups, slang, informal wording, and minor spelling "
                "mistakes. A question about course facts, PayNow, SkillsFuture, UTAP, "
                "or how enrollment works is faq. An attempt to begin, continue, "
                "correct, or confirm an application is enrollment. During active "
                "enrollment, a statement "
                "providing a payment preference or payment amount is enrollment, "
                "and a message with insufficient meaning is unclear.\n\n"
                f"Active intent: {active_intent or 'none'}\n"
                f"Enrollment draft status: {draft_status or 'none'}\n"
                f"Recent redacted context:\n{context or '(none)'}\n"
                f"CURRENT MESSAGE:\n{message}"
            ),
            expected_output=(
                "A structured classification with intent faq, enrollment, or unclear; "
                "confidence from 0 to 1; and a brief routing reason."
            ),
            agent=agent,
            output_pydantic=IntentClassification,
        )
        return self._run(agent, task, IntentClassification)

    def answer_faq(self, message, context, catalogue_context):
        agent = build_faq_agent(self.llm)
        task = Task(
            description=(
                "Answer the current question using ONLY the supplied course information. "
                "Reply naturally and concisely in simple Singapore/British English. "
                "Use no more than one or two relevant emojis from 👋 🦷 📚 📅 ✅ 💳. "
                "Do not use emojis for errors, privacy, or sensitive information. "
                "Never mention internal roles, classification, routing, providers, "
                "implementation details, or how the course information is maintained. "
                "If the answer is absent, say politely that you do not have that "
                "information at the moment; do not infer it. When relevant, ask whether "
                "the customer would like to begin enrollment. Understand informal "
                "wording and minor spelling mistakes. If the intake list is empty, "
                "return the supplied no_intakes_message exactly for course-date "
                "questions and never invent a date.\n\n"
                f"Recent context:\n{context or '(none)'}\n"
                f"CURRENT QUESTION:\n{message}\n\n"
                f"COURSE INFORMATION:\n{catalogue_context}"
            ),
            expected_output=(
                "A concise, friendly structured FAQ answer grounded only in the "
                "supplied course information."
            ),
            agent=agent,
            output_pydantic=FAQAnswer,
        )
        return self._run(agent, task, FAQAnswer)

    def extract_enrollment(self, message, context, draft_state):
        agent = build_enrollment_agent(self.llm)
        task = Task(
            description=(
                "Extract any enrollment values explicitly present in the current "
                "message, including informal wording and minor spelling mistakes. Do "
                "not invent missing values. Extract the selected intake date, full "
                "name, NRIC, date of birth, email, mobile number, payment method, "
                "SkillsFuture amount, and PayNow amount when supplied. Recognize "
                "multiple fields, "
                "corrections, and whether the participant confirms or rejects the "
                "displayed summary. Return dates as written when unsure; Python will "
                "validate and normalize them. When the current reply is a bare value, "
                "use the immediately preceding enrollment question to identify its "
                "field, but do not infer a value that the participant did not provide.\n\n"
                f"Current saved draft (NRIC may be masked):\n{draft_state}\n"
                f"Recent enrollment context:\n{context or '(none)'}\n"
                f"CURRENT MESSAGE:\n{message}"
            ),
            expected_output=(
                "Structured extracted_fields, missing_fields, next_question, "
                "ready_for_confirmation, confirmation (confirm/reject/none), and "
                "correction_requested. Never invent a missing value."
            ),
            agent=agent,
            output_pydantic=EnrollmentExtraction,
        )
        return self._run(agent, task, EnrollmentExtraction)

    @staticmethod
    def _run(agent, task, schema):
        try:
            result = Crew(
                agents=[agent],
                tasks=[task],
                process=Process.sequential,
                verbose=False,
                memory=False,
                share_crew=False,
                output_log_file=False,
                tracing=False,
            ).kickoff()
            if result.pydantic is not None:
                return schema.model_validate(result.pydantic)
            if result.json_dict is not None:
                return schema.model_validate(result.json_dict)
            return schema.model_validate_json(result.raw)
        except AIServiceError:
            raise
        except Exception as error:
            raise AIServiceError("The AI service could not complete the request.") from error


__all__ = ["CrewAIService"]
