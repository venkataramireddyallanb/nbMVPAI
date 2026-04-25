"""NicheBrains Crew — exactly two LLM agents (Narrator + Drafter).

This is the single orchestration surface for AI generation. CrewAI's
``Crew`` abstracts away the LLM-call plumbing; the Narrator and Drafter
are both backed by the same OpenAI model but get different ``role``,
``goal``, and ``backstory`` so the model behaves distinctly.

Why CrewAI here:
    The spec mandates two LLM agents and prohibits more. CrewAI gives us
    multi-agent ORCHESTRATION (sequential tasks, shared context, callbacks,
    structured output) WITHOUT requiring a third agent. We get the
    orchestration benefits while staying compliant with Acceptance
    Criterion #10.

Why agents, not raw LLM calls:
    Every Snapshot, NRA narrative, and Charter draft must be auditable.
    CrewAI's task abstraction lets us record the prompt, the chain of
    intermediate outputs, and the final artefact — handy for the seven-year
    audit log requirement and for the "L-pill citation on every paragraph"
    invariant (the post-processor scans Drafter output for unpilled text).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from flask import current_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy CrewAI import — keeps the rest of the app importable in environments
# without the CrewAI dependency installed (eg. lightweight CI for the
# scoring engine).
# ---------------------------------------------------------------------------

def _crewai_components():
    """Lazy import. Raises a friendly error if CrewAI is missing.

    CrewAI 1.x ships its own ``LLM`` class and no longer requires a
    LangChain wrapper. We try the native class first and fall back to
    ``langchain_openai.ChatOpenAI`` for environments still on the older
    integration — both are accepted by CrewAI's ``Agent(llm=...)``.
    """
    try:
        from crewai import Agent, Crew, Process, Task  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "CrewAI is required for NicheBrainsCrew. "
            "Install with: pip install 'crewai>=1.14,<2'"
        ) from exc

    # Prefer CrewAI-native LLM (available since 0.28+, first-class in 1.x).
    LLM = None
    try:
        from crewai import LLM  # type: ignore
    except ImportError:
        pass

    # LangChain fallback.
    ChatOpenAI = None
    if LLM is None:
        try:
            from langchain_openai import ChatOpenAI  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Neither crewai.LLM nor langchain_openai.ChatOpenAI is "
                "available. Install one of them:\n"
                "  pip install 'crewai>=1.14,<2'  # brings LLM\n"
                "  pip install 'langchain-openai>=0.3'  # fallback"
            ) from exc

    return Agent, Crew, Process, Task, LLM, ChatOpenAI


# ---------------------------------------------------------------------------
# Agent definitions — backstories quoted from spec where applicable.
# ---------------------------------------------------------------------------

NARRATOR_DEFINITION = {
    "role": "Sector Narrator for Indian MSMEs",
    "goal": (
        "Compose sector framing, commentary, explanations of dimension "
        "scores, and the prose body of the Instant Snapshot. Every "
        "narrative paragraph must end with at least one L-pill citation "
        "(L0a/L0b/L1/L2/L3/L4) so the reader can trace the evidence."
    ),
    "backstory": (
        "You are a senior strategy consultant who has spent 20 years "
        "studying Indian MSMEs in the ₹10–500 Cr revenue band. You read "
        "MCA filings before breakfast. You write in calm, declarative "
        "prose — never breathless, never vague. You refuse to make a "
        "claim without a source: every statement is backed by an L-pill."
    ),
    "verbose": False,
    "allow_delegation": False,  # Hard rule: no agent-to-agent delegation.
}


DRAFTER_DEFINITION = {
    "role": "Instant-Report Drafter & Charter Author",
    "goal": (
        "Compose the NRA report, the charter draft, and the outcome "
        "summary. Output must include the seven Charter fields verbatim: "
        "Purpose, Scope, Success metrics, 90-day Milestones, Risks, "
        "Required Skills, Budget. Never sign, pay, or commit on the "
        "user's behalf — every action is human-gated."
    ),
    "backstory": (
        "You are a Senior Full-Stack Developer turned business analyst, "
        "fluent in both code and capital. You produce documents the "
        "owner can sign without re-reading. You honour every gate: "
        "Charter sign-off, Expert Intro, External Filing, Payment. "
        "You never improvise scoring, ranking, or matching — those come "
        "from deterministic services. Your job is to translate them into "
        "language the owner understands."
    ),
    "verbose": False,
    "allow_delegation": False,
}


# ---------------------------------------------------------------------------
# Crew wrapper
# ---------------------------------------------------------------------------

@dataclass
class CrewOutput:
    """Structured result of a Crew run."""

    snapshot_text: str | None = None
    nra_narrative: str | None = None
    charter_draft: dict | None = None
    raw_output: Any = None


class NicheBrainsCrew:
    """Orchestrates the two production LLM agents."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.2,
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.api_key = api_key
        self._agent_cache: dict[str, Any] = {}

    # ---- Agent factories -------------------------------------------------

    def _llm(self):
        """Build an LLM object CrewAI accepts — native first, LangChain fallback."""
        _, _, _, _, LLM, ChatOpenAI = _crewai_components()
        if LLM is not None:
            # CrewAI-native LLM — preferred on 1.x.
            return LLM(
                model=self.model,
                temperature=self.temperature,
                api_key=self.api_key or None,
            )
        return ChatOpenAI(
            model=self.model,
            temperature=self.temperature,
            openai_api_key=self.api_key or None,
        )

    def _agent(self, definition: dict):
        Agent, *_ = _crewai_components()
        return Agent(llm=self._llm(), **definition)

    @property
    def narrator(self):
        if "narrator" not in self._agent_cache:
            self._agent_cache["narrator"] = self._agent(NARRATOR_DEFINITION)
        return self._agent_cache["narrator"]

    @property
    def drafter(self):
        if "drafter" not in self._agent_cache:
            self._agent_cache["drafter"] = self._agent(DRAFTER_DEFINITION)
        return self._agent_cache["drafter"]

    # ---- Public crew tasks ------------------------------------------------

    def run_snapshot(
        self,
        sector_name: str,
        sector_context: dict,
        top_initiatives: list[dict],
    ) -> CrewOutput:
        """W0.0 Instant Snapshot — Narrator only, no questions asked.

        STRICTLY READ-ONLY: this method MUST NOT write to the NRA store
        (Acceptance Criterion #9). The repository layer enforces it; we
        repeat the contract here as a comment for any future maintainer.
        """
        _, Crew, Process, Task, _, _ = _crewai_components()

        task = Task(
            description=(
                f"Compose the Instant Snapshot for an Indian MSME in the "
                f"'{sector_name}' sector. Use the provided sector context "
                f"and the deterministically-ranked top initiatives. Keep "
                f"the snapshot under 250 words, in three paragraphs, each "
                f"ending with at least one L-pill citation.\n\n"
                f"SECTOR CONTEXT:\n{sector_context}\n\n"
                f"TOP THREE INITIATIVES (ranker output — DO NOT modify):\n"
                f"{top_initiatives}"
            ),
            expected_output=(
                "Three paragraphs of prose. Each paragraph ends with one "
                "or more L-pill citations like '[L0b]' or '[L2]'."
            ),
            agent=self.narrator,
        )

        crew = Crew(
            agents=[self.narrator],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
        )

        result = crew.kickoff()
        return CrewOutput(snapshot_text=str(result), raw_output=result)

    def run_nra_report_and_charter(
        self,
        firm_profile: dict,
        scoring_result: dict,
        ranked_initiatives: list[dict],
        ranked_experts: list[dict],
    ) -> CrewOutput:
        """W1 → W1.5 — Narrator drafts the NRA narrative, Drafter authors the Charter.

        The two agents run sequentially: Narrator's output becomes part of
        the Drafter's context. Both agents work strictly from the
        deterministic inputs — they never re-score, re-rank, or re-match.
        """
        _, Crew, Process, Task, _, _ = _crewai_components()

        narrative_task = Task(
            description=(
                "Compose the NRA narrative (~600 words) explaining the "
                "firm's five-dimension reading and the top gaps. Honour "
                "the L-pill citation rule on every paragraph.\n\n"
                f"FIRM PROFILE:\n{firm_profile}\n\n"
                f"DETERMINISTIC SCORING RESULT (DO NOT modify):\n{scoring_result}"
            ),
            expected_output=(
                "Five paragraphs (one per dimension) plus a closing "
                "paragraph identifying the two highest-priority gaps."
            ),
            agent=self.narrator,
        )

        charter_task = Task(
            description=(
                "Using the narrative above, draft a Charter for the "
                "highest-ranked initiative. Output the seven Charter "
                "fields verbatim: Purpose, Scope, Success metrics, "
                "90-day Milestones, Risks, Required Skills, Budget. "
                "List the top-3 expert matches by name with their "
                "fit_score. STATUS = 'draft' — DO NOT sign or commit. "
                "The owner approves at Gate 1.\n\n"
                f"RANKED INITIATIVES (top item = subject of Charter):\n"
                f"{ranked_initiatives}\n\n"
                f"RANKED EXPERT MATCHES (top-3 only):\n{ranked_experts}"
            ),
            expected_output=(
                "JSON with keys: purpose, scope, success_metrics (list), "
                "milestones_summary (list), risks (list), required_skills "
                "(list), budget_inr (number), proposed_experts (list of "
                "{name, fit_score, reason_codes})."
            ),
            agent=self.drafter,
            context=[narrative_task],  # Drafter sees Narrator's output
        )

        crew = Crew(
            agents=[self.narrator, self.drafter],
            tasks=[narrative_task, charter_task],
            process=Process.sequential,
            verbose=False,
        )

        result = crew.kickoff()
        return CrewOutput(
            nra_narrative=str(narrative_task.output) if narrative_task.output else None,
            charter_draft={"raw": str(result)},
            raw_output=result,
        )


def build_crew() -> NicheBrainsCrew:
    """Build a NicheBrainsCrew from the active Flask app's config."""
    cfg = current_app.config
    return NicheBrainsCrew(
        model=cfg.get("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=cfg.get("LLM_TEMPERATURE", 0.2),
        api_key=cfg.get("OPENAI_API_KEY") or None,
    )
