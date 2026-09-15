"""Local checks for genuine CrewAI objects and structured output contracts."""

import pytest
from crewai import Agent
from pydantic import ValidationError

from backend.agents.enrollment_agent import build_enrollment_agent
from backend.agents.faq_agent import build_faq_agent
from backend.agents.intent_classifier import build_intent_classifier
from backend.agents.schemas import IntentClassification
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
