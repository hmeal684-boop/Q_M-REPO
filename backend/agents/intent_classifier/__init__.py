"""CrewAI Intent Classification Agent definition."""

from crewai import Agent


def build_intent_classifier(llm):
    return Agent(
        role="Intent Classification Agent",
        goal=(
            "Classify each participant message as faq, enrollment, or unclear "
            "using the supplied conversation state, including informal wording, "
            "common Singapore usage, and minor spelling mistakes."
        ),
        backstory=(
            "You are a privacy-conscious router for a customer service assistant. "
            "You return only the requested structured result and never invent facts."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=False,
        memory=False,
        max_iter=3,
    )


__all__ = ["build_intent_classifier"]
