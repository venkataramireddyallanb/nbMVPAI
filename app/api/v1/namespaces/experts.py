"""/experts namespace — directory, matching, and expert self-service."""
from __future__ import annotations

from flask import g, request
from flask_restx import Namespace, Resource, fields

from app.api.v1.security import login_required, role_required
from app.extensions import db
from app.models.charter import CharterStatus
from app.models.engagement import Match
from app.models.expert import Expert
from app.models.user import UserRole
from app.services.matching_service import match_experts_for_charter

ns = Namespace("experts",
    description="Expert marketplace directory, matching, and self-service",
    path="/experts")


# ---- Shared models ----------------------------------------------------

expert_output = ns.model("Expert", {
    "id": fields.String,
    "display_name": fields.String(example="Priya Rao"),
    "headline": fields.String(example="Operations & Lean specialist"),
    "expertise_codes": fields.List(fields.String, example=["ops.lean", "ops.oee"]),
    "sector_codes": fields.List(fields.String, example=["manufacturing", "textile"]),
    "languages": fields.List(fields.String, example=["en", "hi"]),
    "states_served": fields.List(fields.String, example=["Maharashtra", "Gujarat"]),
    "availability_score": fields.Float(example=0.9,
        description="0..1 — feeds the Match Ranker availability term"),
    "has_anchor_evidence": fields.Boolean(example=True,
        description="True only when ≥1 L0 or L3 anchor is attached. "
                    "Required to appear in match shortlists."),
})

expert_profile_input = ns.model("ExpertProfileInput", {
    "headline": fields.String(required=True, example="Operations & Lean specialist"),
    "bio": fields.String(required=False),
    "expertise_codes": fields.List(fields.String, required=True,
        example=["ops.lean", "ops.oee"]),
    "sector_codes": fields.List(fields.String, required=True,
        example=["manufacturing", "textile"]),
    "languages": fields.List(fields.String, required=True, example=["en", "hi"]),
    "states_served": fields.List(fields.String, required=True,
        example=["Maharashtra", "Gujarat"]),
    "availability_score": fields.Float(required=False, example=0.9, min=0, max=1),
})

match_output = ns.model("ExpertMatch", {
    "expert_id": fields.String,
    "display_name": fields.String,
    "fit_score": fields.Float(example=0.84),
    "reason_codes": fields.List(fields.String,
        example=["strong_expertise_match", "sector_specialist"]),
    "rank_position": fields.Integer(example=1),
})

lead_output = ns.model("ExpertLead", {
    "charter_id": fields.String,
    "charter_title": fields.String(example="OEE programme on binding line"),
    "firm_name": fields.String(example="Rao Textiles Pvt Ltd"),
    "firm_sector": fields.String(example="textile"),
    "firm_state": fields.String(example="Gujarat"),
    "fit_score": fields.Float(example=0.84),
    "reason_codes": fields.List(fields.String),
    "rank_position": fields.Integer,
    "charter_status": fields.String(example="pending_approval"),
    "created_at": fields.DateTime,
})

outcome_record = ns.model("ExpertOutcome", {
    "charter_id": fields.String,
    "charter_title": fields.String,
    "closed_at": fields.DateTime,
    "evidence_grade": fields.String(
        enum=["low_evidence", "evidenced", "proven"], example="evidenced"),
    "delta_pct": fields.Float(example=18.4,
        description="Outcome delta vs. baseline (positive = improvement)"),
    "summary": fields.String,
})


def _expert_serialize(e: Expert) -> dict:
    return dict(id=e.id,
        display_name=(e.person.full_name if e.person else ""),
        headline=e.headline,
        expertise_codes=e.expertise_codes or [],
        sector_codes=e.sector_codes or [],
        languages=e.languages or [],
        states_served=e.states_served or [],
        availability_score=e.availability_score,
        has_anchor_evidence=(str(e.has_anchor_evidence).lower() == "true"))


# ---- Directory --------------------------------------------------------

@ns.route("/")
class ExpertList(Resource):
    @ns.doc("list_experts", tags=["Experts"])
    @ns.response(200, "All experts (PII-free display fields)", [expert_output])
    @ns.response(401, "Missing or invalid bearer token")
    @login_required
    @ns.marshal_list_with(expert_output)
    def get(self):
        """List all experts visible to the caller (PII-free).

        Cross-tenant visibility is intentional — experts are the marketplace
        supply side. Only public display fields are returned.
        """
        return [_expert_serialize(e) for e in Expert.query.all()]


@ns.route("/match/<string:charter_id>")
@ns.param("charter_id", "UUID of the charter to match experts to")
class MatchForCharter(Resource):
    @ns.doc("match_experts", tags=["Experts"])
    @ns.response(200, "Top-3 expert matches", [match_output])
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(404, "Charter not found in caller tenant")
    @login_required
    @ns.marshal_list_with(match_output)
    def get(self, charter_id):
        """Top-3 expert matches for a charter.

        Deterministic ranker. Experts without ≥1 L0/L3 anchor are dropped
        before scoring.
        """
        return match_experts_for_charter(charter_id, tenant_id=g.tenant_id)


# ---- Expert self-service ---------------------------------------------

def _my_expert() -> Expert:
    """Return the Expert row owned by the caller's tenant.

    One expert tenant may have one Expert row. 404s if missing — callers
    should POST to /experts/me first (create-or-update).
    """
    expert = Expert.query.filter_by(tenant_id=g.tenant_id).first()
    if not expert:
        ns.abort(404, "No expert profile for this tenant. POST to /experts/me to create.")
    return expert


@ns.route("/me")
class MyExpertProfile(Resource):
    @ns.doc("get_my_expert_profile", tags=["Experts"])
    @ns.response(200, "Caller's expert profile", expert_output)
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(403, "Caller is not EXPERT role")
    @ns.response(404, "No expert profile for this tenant yet")
    @role_required(UserRole.EXPERT)
    @ns.marshal_with(expert_output)
    def get(self):
        """Return the caller's own expert profile."""
        return _expert_serialize(_my_expert())

    @ns.doc("upsert_my_expert_profile", tags=["Experts"])
    @ns.expect(expert_profile_input, validate=True)
    @ns.response(200, "Profile updated", expert_output)
    @ns.response(201, "Profile created", expert_output)
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(403, "Caller is not EXPERT role")
    @role_required(UserRole.EXPERT)
    @ns.marshal_with(expert_output)
    def put(self):
        """Create-or-update the caller's expert profile.

        On first call, creates the ``Expert`` row (linked to a new
        ``Person``). Subsequent calls patch the existing row.
        """
        body = request.get_json()
        expert = Expert.query.filter_by(tenant_id=g.tenant_id).first()
        created = False

        if not expert:
            # First call — create Expert + Person (Person is tenant-free
            # so dual-role users stay identified by a single Person id).
            from app.models.person import Person
            user = g.current_user
            person = Person.query.filter_by(email=user.email).first()
            if not person:
                person = Person(full_name=user.full_name, email=user.email)
                db.session.add(person)
                db.session.flush()
            expert = Expert(tenant_id=g.tenant_id, person_id=person.id,
                headline="", expertise_codes=[], sector_codes=[],
                languages=[], states_served=[], availability_score=1.0)
            db.session.add(expert)
            created = True

        # Patch fields
        expert.headline = body["headline"]
        expert.bio = body.get("bio") or None
        expert.expertise_codes = body["expertise_codes"]
        expert.sector_codes = body["sector_codes"]
        expert.languages = body["languages"]
        expert.states_served = body["states_served"]
        if "availability_score" in body:
            expert.availability_score = body["availability_score"]

        db.session.commit()
        if created:
            return _expert_serialize(expert), 201
        return _expert_serialize(expert)


@ns.route("/me/leads")
class MyExpertLeads(Resource):
    @ns.doc("list_my_leads", tags=["Experts"])
    @ns.response(200, "Charters where caller is top-3 matched", [lead_output])
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(403, "Caller is not EXPERT role")
    @role_required(UserRole.EXPERT)
    @ns.marshal_list_with(lead_output)
    def get(self):
        """List charters where the caller appears in the top-3 match.

        Cross-tenant read — an expert sees every SME charter they've been
        shortlisted against, with fit_score and reason_codes. PII in the
        firm name is intentional here: once the SME has shortlisted the
        expert, the introduction is editorially sanctioned.
        """
        expert = _my_expert()
        rows = (db.session.query(Match)
                .filter(Match.expert_id == expert.id)
                .order_by(Match.rank_position.asc())
                .all())
        return [
            {
                "charter_id": m.charter_id,
                "charter_title": m.charter.title if m.charter else "",
                "firm_name": (m.charter.firm.legal_name
                              if m.charter and m.charter.firm else ""),
                "firm_sector": (m.charter.firm.sector.code
                                if m.charter and m.charter.firm
                                and m.charter.firm.sector else ""),
                "firm_state": (m.charter.firm.state
                               if m.charter and m.charter.firm else ""),
                "fit_score": m.fit_score,
                "reason_codes": m.reason_codes or [],
                "rank_position": m.rank_position,
                "charter_status": (m.charter.status.value
                                   if m.charter else "unknown"),
                "created_at": m.created_at,
            }
            for m in rows
        ]


@ns.route("/me/outcomes")
class MyExpertOutcomes(Resource):
    @ns.doc("list_my_outcomes", tags=["Experts"])
    @ns.response(200, "Outcome records delivered by caller", [outcome_record])
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(403, "Caller is not EXPERT role")
    @role_required(UserRole.EXPERT)
    @ns.marshal_list_with(outcome_record)
    def get(self):
        """List outcomes for charters delivered by the caller.

        Promotion ladder: low_evidence → evidenced → proven. Proven
        outcomes feed the sector-default uplift in the ranker's next
        run (spec's "outputs as inputs" flywheel).
        """
        expert = _my_expert()
        from app.models.charter import Charter, Outcome
        # Charters the expert actually won (APPROVED + completed delivery).
        rows = (db.session.query(Outcome)
                .join(Charter, Outcome.charter_id == Charter.id)
                .join(Match, Match.charter_id == Charter.id)
                .filter(Match.expert_id == expert.id)
                .filter(Charter.status == CharterStatus.COMPLETED)
                .all())
        return [
            {
                "charter_id": o.charter_id,
                "charter_title": o.charter.title if o.charter else "",
                "closed_at": o.closed_at,
                "evidence_grade": o.evidence_grade,
                "delta_pct": o.delta_pct,
                "summary": o.summary,
            }
            for o in rows
        ]
