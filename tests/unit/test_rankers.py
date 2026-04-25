"""Unit tests for the deterministic rankers."""
from __future__ import annotations

import pytest

from app.services.ranking import (
    HYBRID_PENALTY,
    SHORTLIST_MAX,
    SHORTLIST_MIN,
    TOP_N_EXPERTS,
    ExpertCandidate,
    InitiativeCandidate,
    rank_experts,
    rank_initiatives,
)


def _candidate(id_, score_inputs, **overrides):
    base = dict(
        id=id_,
        title=f"init-{id_}",
        transformation_type="process",
        target_dimension="O",
        closes_gap_weight=0.5,
        transformation_type_fit=0.5,
        horizon_fit=0.5,
        priority_fit=0.5,
        sector_default_uplift=0.5,
        effort_band=0.5,
        feasibility=1.0,
    )
    base.update(score_inputs)
    base.update(overrides)
    return InitiativeCandidate(**base)


class TestInitiativeRanker:
    def test_feasibility_below_threshold_blocks_candidate(self):
        cands = [
            _candidate(str(i), {}, feasibility=1.0) for i in range(SHORTLIST_MIN)
        ] + [_candidate("blocked", {}, feasibility=0.3)]
        out = rank_initiatives(cands)
        assert all(c.id != "blocked" for c in out)

    def test_minimum_shortlist_enforced(self):
        cands = [_candidate("a", {}, feasibility=0.3)]  # all blocked
        with pytest.raises(ValueError, match="Widen the candidate pool"):
            rank_initiatives(cands)

    def test_shortlist_capped_at_max(self):
        cands = [_candidate(str(i), {}) for i in range(10)]
        out = rank_initiatives(cands)
        assert len(out) == SHORTLIST_MAX

    def test_hybrid_penalty_applied_when_evidence_weak(self):
        strong = _candidate(
            "strong", {"closes_gap_weight": 1.0, "transformation_type_fit": 1.0,
                       "horizon_fit": 1.0, "priority_fit": 1.0,
                       "sector_default_uplift": 1.0, "effort_band": 0.0},
            transformation_type="process",
        )
        hybrid_no_evidence = _candidate(
            "hybrid_weak",
            {"closes_gap_weight": 1.0, "transformation_type_fit": 1.0,
             "horizon_fit": 1.0, "priority_fit": 1.0,
             "sector_default_uplift": 1.0, "effort_band": 0.0},
            transformation_type="hybrid",
            hybrid_evidence_strong=False,
        )
        # Add filler candidates to satisfy shortlist minimum.
        fillers = [_candidate(f"f{i}", {}) for i in range(SHORTLIST_MIN)]
        out = rank_initiatives([strong, hybrid_no_evidence, *fillers])
        # Strong process candidate must outrank penalised hybrid.
        ranks = {c.id: c.rank_score for c in out}
        assert ranks["strong"] > ranks["hybrid_weak"]
        # Penalty is exactly HYBRID_PENALTY × identical raw score.
        assert ranks["hybrid_weak"] == pytest.approx(
            ranks["strong"] * HYBRID_PENALTY, rel=1e-6
        )

    def test_conditional_feasibility_flagged_but_not_blocked(self):
        cands = [
            _candidate(str(i), {}) for i in range(SHORTLIST_MIN)
        ] + [_candidate("conditional", {}, feasibility=0.5)]
        out = rank_initiatives(cands)
        flagged = [c for c in out if c.id == "conditional"]
        assert flagged
        assert "conditional_feasibility" in flagged[0].flags


class TestExpertRanker:
    def _expert(self, id_, **kw):
        base = dict(
            id=id_, display_name=f"E{id_}",
            expertise=0.5, sector=0.5, geography=0.5,
            language=0.5, availability=0.5,
            has_anchor_evidence=True,
        )
        base.update(kw)
        return ExpertCandidate(**base)

    def test_top_3_only(self):
        out = rank_experts([self._expert(str(i)) for i in range(7)])
        assert len(out) == TOP_N_EXPERTS

    def test_anchor_evidence_required(self):
        out = rank_experts([
            self._expert("ok"),
            self._expert("no_anchor", has_anchor_evidence=False),
        ])
        assert all(c.id != "no_anchor" for c in out)

    def test_weights_sum_to_one(self):
        from app.services.ranking.expert_ranker import (
            W_AVAILABILITY, W_EXPERTISE, W_GEOGRAPHY, W_LANGUAGE, W_SECTOR,
        )
        assert pytest.approx(
            W_EXPERTISE + W_SECTOR + W_GEOGRAPHY + W_LANGUAGE + W_AVAILABILITY
        ) == 1.0

    def test_rank_position_assigned(self):
        out = rank_experts([self._expert(str(i)) for i in range(3)])
        assert [c.rank_position for c in out] == [1, 2, 3]

    def test_reason_codes_emitted(self):
        out = rank_experts([self._expert(
            "strong", expertise=0.95, sector=0.9, geography=0.5,
            language=0.5, availability=0.9,
        )])
        codes = out[0].reason_codes
        assert "strong_expertise_match" in codes
        assert "sector_specialist" in codes
        assert "immediately_available" in codes
