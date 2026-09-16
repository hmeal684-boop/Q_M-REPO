"""Local checks for genuine CrewAI objects and structured output contracts."""

from types import SimpleNamespace

import pytest
from crewai import Agent, Task
from pydantic import ValidationError

from backend.agents.enrollment_agent import build_enrollment_agent
from backend.agents.faq_agent import build_faq_agent
from backend.agents.intent_classifier import build_intent_classifier
from backend.agents.schemas import EnrollmentExtraction, FAQAnswer, IntentClassification
from backend.services.crewai_service import CrewAIService


def test_all_three_production_agents_are_crewai_agents():
    service = CrewAIService(
        api_key="synthetic-test-key",
        model="gpt-5-mini",
    )
    agents = (
        build_intent_classifier(service.llm),
        build_faq_agent(service.llm),
        build_enrollment_agent(service.llm),
    )
    assert all(isinstance(agent, Agent) for agent in agents)
    assert service.llm.reasoning_effort == "low"
    assert service.llm.max_completion_tokens == 1000
    assert service.llm.timeout == 60
    assert service.llm.max_retries == 2


def test_classifier_contract_rejects_invalid_output():
    with pytest.raises(ValidationError):
        IntentClassification(
            intent="payment",
            confidence=1.5,
            short_reason="Unsupported route.",
        )


def test_each_runtime_operation_builds_task_and_crew_then_calls_kickoff(monkeypatch):
    recorded_crews = []

    class RecordingCrew:
        def __init__(self, *, agents, tasks, **kwargs):
            self.agents = agents
            self.tasks = tasks
            self.kwargs = kwargs
            self.kickoff_calls = 0
            recorded_crews.append(self)

        def kickoff(self):
            self.kickoff_calls += 1
            schema = self.tasks[0].output_pydantic
            outputs = {
                IntentClassification: IntentClassification(
                    intent="faq", confidence=0.99, short_reason="Question"
                ),
                FAQAnswer: FAQAnswer(answer="Approved answer"),
                EnrollmentExtraction: EnrollmentExtraction(),
            }
            return SimpleNamespace(
                pydantic=outputs[schema], json_dict=None, raw=""
            )

    monkeypatch.setattr("backend.services.crewai_service.Crew", RecordingCrew)
    service = CrewAIService(api_key="synthetic-test-key", model="gpt-5-mini")

    service.classify("What is the fee?", "", None, None)
    service.answer_faq("What is the fee?", "", "{}")
    service.extract_enrollment("Please register me", "", {})

    assert len(recorded_crews) == 3
    assert all(len(crew.agents) == 1 for crew in recorded_crews)
    assert all(isinstance(crew.agents[0], Agent) for crew in recorded_crews)
    assert all(len(crew.tasks) == 1 for crew in recorded_crews)
    assert all(isinstance(crew.tasks[0], Task) for crew in recorded_crews)
    assert all(crew.kickoff_calls == 1 for crew in recorded_crews)
    assert [crew.tasks[0].output_pydantic for crew in recorded_crews] == [
        IntentClassification,
        FAQAnswer,
        EnrollmentExtraction,
    ]
