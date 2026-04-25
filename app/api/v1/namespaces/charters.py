"""/charters namespace — W1.5 Charter draft + Gate-1 approval."""
from __future__ import annotations

from datetime import datetime

from flask import g, request
from flask_restx import Namespace, Resource, fields

from app.api.v1.security import login_required, role_required
from app.extensions import db
from app.models.charter import Charter, CharterStatus
from app.models.user import UserRole
from app.services.charter_service import draft_charter_from_assessment

ns = Namespace("charters",
    description="W1.5 seven-field Charters + Gate-1 OWNER approval",
    path="/charters")

success_metric = ns.model("SuccessMetric", {
    "name": fields.String(example="On-time delivery %"),
    "baseline": fields.Raw(allow_null=True, example=78),
    "target": fields.Raw(allow_null=True, example=95),
    "unit": fields.String(example="percent"),
})

milestone_summary = ns.model("MilestoneSummary", {
    "name": fields.String(example="Kick-off and baseline"),
    "due_in_days": fields.Integer(example=14),
})

charter_output = ns.model("Charter", {
    "id": fields.String,
    "firm_id": fields.String,
    "title": fields.String(example="Charter — OEE on binding line"),
    "purpose": fields.String, "scope": fields.String,
    "success_metrics": fields.List(fields.Nested(success_metric)),
    "milestones_summary": fields.List(fields.Nested(milestone_summary)),
    "risks": fields.List(fields.String, example=["Adoption friction"]),
    "required_skills": fields.List(fields.String, example=["Process design"]),
    "budget_inr": fields.Float(example=2500000),
    "status": fields.String(enum=[s.value for s in CharterStatus], example="draft"),
    "approved_at": fields.DateTime(allow_null=True,
        description="Set when OWNER signs Gate 1"),
})

draft_input = ns.model("CharterDraftInput", {
    "assessment_id": fields.String(required=True),
    "initiative_id": fields.String(required=True),
})


def _serialize(c):
    return dict(id=c.id, firm_id=c.firm_id, title=c.title,
        purpose=c.purpose, scope=c.scope,
        success_metrics=c.success_metrics,
        milestones_summary=c.milestones_summary,
        risks=c.risks, required_skills=c.required_skills,
        budget_inr=c.budget_inr, status=c.status.value,
        approved_at=c.approved_at)


@ns.route("/")
class CharterList(Resource):
    @ns.doc("list_charters", tags=["Charters"])
    @ns.response(200, "Charters in caller tenant", [charter_output])
    @ns.response(401, "Missing or invalid bearer token")
    @login_required
    @ns.marshal_list_with(charter_output)
    def get(self):
        """List charters in the caller tenant, any status."""
        return [_serialize(c) for c in
                Charter.query.filter_by(tenant_id=g.tenant_id).all()]


@ns.route("/draft")
class DraftCharter(Resource):
    @ns.doc("draft_charter", tags=["Charters"])
    @ns.expect(draft_input, validate=True)
    @ns.response(201, "New DRAFT charter", charter_output)
    @ns.response(400, "Unknown assessment_id or initiative_id")
    @ns.response(401, "Missing or invalid bearer token")
    @login_required
    @ns.marshal_with(charter_output, code=201)
    def post(self):
        """Draft a new Charter from an NRA run and initiative.

        Status is 'draft' until OWNER approves. Agents never sign.
        """
        body = request.get_json()
        charter = draft_charter_from_assessment(
            assessment_id=body["assessment_id"],
            initiative_id=body["initiative_id"],
            tenant_id=g.tenant_id)
        return _serialize(charter), 201


@ns.route("/<string:charter_id>/approve")
@ns.param("charter_id", "UUID of the charter within caller tenant")
class ApproveCharter(Resource):
    @ns.doc("approve_charter", tags=["Charters"])
    @ns.response(200, "Charter signed. status=approved", charter_output)
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(403, "Caller is not OWNER")
    @ns.response(404, "Charter not found in caller tenant")
    @ns.response(409, "Charter is not in a pre-approval state")
    @role_required(UserRole.OWNER)
    @ns.marshal_with(charter_output)
    def post(self, charter_id):
        """Gate 1 sign-off. OWNER role only."""
        c = Charter.query.filter_by(id=charter_id, tenant_id=g.tenant_id).first_or_404()
        if c.status not in (CharterStatus.DRAFT, CharterStatus.PENDING_APPROVAL):
            ns.abort(409, f"Charter cannot be approved from status '{c.status.value}'")
        c.status = CharterStatus.APPROVED
        c.approved_at = datetime.utcnow()
        c.approved_by_user_id = g.current_user.id
        db.session.commit()
        return _serialize(c)


@ns.route("/<string:charter_id>")
@ns.param("charter_id", "UUID of the charter within caller tenant")
class CharterDetail(Resource):
    @ns.doc("get_charter", tags=["Charters"])
    @ns.response(200, "Charter detail", charter_output)
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(404, "Charter not found in caller tenant")
    @login_required
    @ns.marshal_with(charter_output)
    def get(self, charter_id):
        """Fetch a single Charter by id."""
        c = Charter.query.filter_by(id=charter_id, tenant_id=g.tenant_id).first_or_404()
        return _serialize(c)
