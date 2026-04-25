"""Matching service — wraps the Expert Match Ranker + persistence."""
from __future__ import annotations

from app.extensions import db
from app.models.charter import Charter
from app.models.engagement import Match
from app.models.expert import Expert
from app.services.ranking.expert_ranker import ExpertCandidate, rank_experts


def match_experts_for_charter(charter_id: str, tenant_id: str) -> list[dict]:
    """Return the top-3 expert matches for a charter.

    Existing matches are cleared and replaced so the top-3 invariant holds
    (no accidental top-5 after a re-match).
    """
    charter = Charter.query.filter_by(
        id=charter_id, tenant_id=tenant_id
    ).first()
    if not charter:
        return []

    # Wipe prior matches before writing the new top-3.
    Match.query.filter_by(charter_id=charter.id).delete()
    db.session.flush()

    experts = Expert.query.all()
    candidates = [
        ExpertCandidate(
            id=e.id,
            display_name=e.person.full_name if e.person else e.headline or "",
            expertise=_score_expertise(e, charter),
            sector=_score_sector(e, charter),
            geography=_score_geography(e, charter),
            language=_score_language(e, charter),
            availability=e.availability_score,
            has_anchor_evidence=(e.has_anchor_evidence == "true"),
        )
        for e in experts
    ]

    top = rank_experts(candidates)

    # Persist + shape response.
    response: list[dict] = []
    for c in top:
        match = Match(
            tenant_id=tenant_id,
            charter_id=charter.id,
            expert_id=c.id,
            expertise_score=c.expertise,
            sector_score=c.sector,
            geography_score=c.geography,
            language_score=c.language,
            availability_score=c.availability,
            fit_score=c.fit_score,
            reason_codes=c.reason_codes,
            rank_position=c.rank_position,
        )
        db.session.add(match)
        response.append({
            "expert_id": c.id,
            "display_name": c.display_name,
            "fit_score": c.fit_score,
            "reason_codes": c.reason_codes,
            "rank_position": c.rank_position,
        })
    db.session.commit()
    return response


# ---------------------------------------------------------------------------
# Sub-score heuristics — in prod these draw from the Expert profile vs. the
# Charter's required_skills / firm's sector / geography. Kept simple here.
# ---------------------------------------------------------------------------

def _score_expertise(e: Expert, c: Charter) -> float:
    required = set(c.required_skills or [])
    if not required:
        return 0.5
    have = set(e.expertise_codes or [])
    return min(1.0, len(required & have) / max(1, len(required)))


def _score_sector(e: Expert, c: Charter) -> float:
    firm_sector = c.firm.sector.code if c.firm and c.firm.sector else None
    if not firm_sector:
        return 0.5
    return 1.0 if firm_sector in (e.sector_codes or []) else 0.3


def _score_geography(e: Expert, c: Charter) -> float:
    firm_state = c.firm.state if c.firm else None
    if not firm_state:
        return 0.5
    return 1.0 if firm_state in (e.states_served or []) else 0.4


def _score_language(e: Expert, c: Charter) -> float:
    # Firms don't carry a primary language yet — default OK.
    return 0.7 if e.languages else 0.5
