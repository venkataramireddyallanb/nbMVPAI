"""Expert Match Ranker — deterministic.

Spec formula (verbatim):

    match = 0.35·expertise + 0.25·sector + 0.15·geography
          + 0.15·language + 0.10·availability

Hard rules:
    * Top-3 only — never more (spec acceptance rule).
    * No expert appears in any shortlist without ≥1 L0 or L3 anchor evidence.
    * Reason-codes are emitted as machine-readable chips for the UI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

W_EXPERTISE = 0.35
W_SECTOR = 0.25
W_GEOGRAPHY = 0.15
W_LANGUAGE = 0.15
W_AVAILABILITY = 0.10

TOP_N_EXPERTS = 3


@dataclass
class ExpertCandidate:
    """One expert candidate to be matched against a charter."""

    id: str
    display_name: str

    # Sub-scores in [0, 1].
    expertise: float
    sector: float
    geography: float
    language: float
    availability: float

    has_anchor_evidence: bool = False  # L0 or L3 anchor required

    # Output (filled in by ranker).
    fit_score: float = field(init=False, default=0.0)
    reason_codes: list[str] = field(init=False, default_factory=list)
    rank_position: int = field(init=False, default=0)


def _emit_reason_codes(c: ExpertCandidate) -> list[str]:
    """Translate sub-score peaks into human-readable chips."""
    codes: list[str] = []
    # Threshold of 0.7 chosen so chips show only meaningful matches.
    if c.expertise >= 0.7:
        codes.append("strong_expertise_match")
    if c.sector >= 0.7:
        codes.append("sector_specialist")
    if c.geography >= 0.7:
        codes.append("local_geography")
    if c.language >= 0.7:
        codes.append("language_match")
    if c.availability >= 0.8:
        codes.append("immediately_available")
    return codes


def rank_experts(candidates: Iterable[ExpertCandidate]) -> list[ExpertCandidate]:
    """Score and return the top-3 expert matches.

    Anchor-evidence rule: candidates without an L0 or L3 anchor are dropped
    BEFORE scoring — they cannot enter the marketplace shortlist.
    """
    eligible: list[ExpertCandidate] = []

    for c in candidates:
        if not c.has_anchor_evidence:
            continue

        c.fit_score = round(
            W_EXPERTISE * c.expertise
            + W_SECTOR * c.sector
            + W_GEOGRAPHY * c.geography
            + W_LANGUAGE * c.language
            + W_AVAILABILITY * c.availability,
            6,
        )
        c.reason_codes = _emit_reason_codes(c)
        eligible.append(c)

    eligible.sort(key=lambda c: c.fit_score, reverse=True)
    top = eligible[:TOP_N_EXPERTS]
    for i, c in enumerate(top, start=1):
        c.rank_position = i
    return top
