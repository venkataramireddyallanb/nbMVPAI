"""AI agent layer.

Per spec Acceptance Criterion #10, production runs EXACTLY TWO LLM agents:

    1. Narrator                — sector framing, dimension commentary,
                                  Snapshot prose, macro context.
    2. Instant-Report Drafter  — NRA report, charter draft, outcome summary.

Everything else marketed as an "agent" in the spec (Manufacturing Agent,
Finance Agent, etc.) is a deterministic capability bundle implemented as
plain Python services — NOT an LLM agent. The CrewAI ``Crew`` defined here
is the single orchestration surface for the two LLM agents.
"""
from app.agents.crews.nichebrains_crew import (  # noqa: F401
    NicheBrainsCrew,
    build_crew,
)

__all__ = ["NicheBrainsCrew", "build_crew"]
