"""CrewAI Enrollment Agent definition."""

from crewai import Agent


def build_enrollment_agent(llm):
    return Agent(
        role="Enrollment Agent",
        goal=(
            "Extract course-date, identity, contact, payment-preference, payment-amount, "
            "correction, and confirmation details from natural enrollment conversation "
            "without deciding whether values are valid."
        ),
        backstory=(
            "You support a friendly course enrollment conversation and understand "
            "informal wording and minor spelling mistakes. Deterministic Python services "
            "perform validation and persistence after your extraction."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=False,
        memory=False,
        max_iter=3,
    )


__all__ = ["build_enrollment_agent"]
