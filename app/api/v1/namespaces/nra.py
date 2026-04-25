"""/nra namespace — W1 Needs & Readiness Assessment (40 questions)."""
from __future__ import annotations

from flask import g, request
from flask_restx import Namespace, Resource, fields

from app.api.v1.security import login_required
from app.models.assessment import AssessmentRun
from app.models.firm import Firm
from app.services.nra_service import create_nra_run

ns = Namespace("nra",
    description="W1 forty-question Needs and Readiness Assessment",
    path="/nra")

nra_input = ns.model("NRAInput", {
    "firm_id": fields.String(required=True, example="firm-id"),
    "raw_sums": fields.Raw(required=True,
        example={"S": 20, "O": 18, "SM": 22, "T": 14, "SK": 24},
        description="Per-dimension raw sums. All 5 required. Each in [0, 32]."),
    "priority_preferences": fields.Raw(required=False,
        example={"business_driver": "operating_margin", "timeframe": "short"},
        description="Keys: business_driver, focus_area, timeframe, appetite, urgency"),
    "evidence_tiers": fields.Raw(required=False,
        example={"S": "L1", "O": "L2", "SM": "L0b", "T": "L1", "SK": "L2"}),
    "horizon": fields.String(required=False,
        enum=["immediate", "short", "medium", "long"], example="short",
        description="DDExpert v3.1 §7.1 — captured upstream of dTAS"),
    "priority_mode": fields.String(required=False,
        enum=["mode_a_dimension", "mode_b_driver"], example="mode_b_driver"),
    "priority_dimension": fields.String(required=False,
        enum=["S", "O", "SM", "T", "SK"],
        description="Mode A only — named dimension"),
    "priority_driver": fields.String(required=False,
        enum=["revenue_growth", "margin", "working_capital", "productivity",
              "market_expansion", "customer_retention", "compliance_risk"],
        description="Mode B only — one of the 7 business drivers"),
    "include_narrative": fields.Boolean(default=False,
        description="If true and OPENAI_API_KEY is set, runs the Narrator agent."),
})

score_output = ns.model("ScoreOut", {
    "dimension_code": fields.String(enum=["S", "O", "SM", "T", "SK"], example="O"),
    "value": fields.Integer(example=60,
        description="0..80. Values 35 / 65 / 85 are unreachable (AC #1)."),
    "raw_sum": fields.Integer(example=24),
    "evidence_tier": fields.String(
        enum=["L0a", "L0b", "L1", "L2", "L3", "L4"], example="L2"),
})

nra_output = ns.model("NRAOutput", {
    "assessment_id": fields.String,
    "firm_id": fields.String,
    "stage": fields.String(
        enum=["snapshot", "prescreener", "nra", "charter_draft", "delivered"]),
    "composite_score": fields.Integer(example=68),
    "band": fields.String(
        enum=["Legacy", "Siloed", "Strategic", "Future-Ready"]),
    "scores": fields.List(fields.Nested(score_output)),
    "narrative": fields.String(allow_null=True,
        description="Narrator prose — present only when include_narrative=true"),
    "transformation_type": fields.String(allow_null=True,
        enum=["process", "cx", "business_model", "organisational",
              "digital", "hybrid"],
        description="Inferred per DDExpert v3.1 Table 4 — never asked"),
    "transformation_secondary": fields.String(allow_null=True,
        description="Populated only when transformation_type == 'hybrid' "
                    "(top two dims within 5 pts)"),
})


@ns.route("/")
class CreateNRA(Resource):
    @ns.doc("create_nra", tags=["NRA"])
    @ns.expect(nra_input, validate=True)
    @ns.response(201, "Assessment scored and persisted", nra_output)
    @ns.response(400, "Validation error")
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(404, "Firm not found in caller tenant")
    @login_required
    @ns.marshal_with(nra_output, code=201)
    def post(self):
        """Score a new NRA run and optionally draft the narrative.

        Scoring is deterministic — a pure function of raw sums. Persists
        one AssessmentRun + five Score rows under the caller tenant.
        """
        body = request.get_json()
        firm = Firm.query.filter_by(
            id=body["firm_id"], tenant_id=g.tenant_id).first_or_404()
        return create_nra_run(firm=firm,
            raw_sums=body["raw_sums"],
            priority_preferences=body.get("priority_preferences"),
            evidence_tiers=body.get("evidence_tiers"),
            include_narrative=body.get("include_narrative", False)), 201


@ns.route("/<string:assessment_id>")
@ns.param("assessment_id", "UUID of the assessment within caller tenant")
class NRADetail(Resource):
    @ns.doc("get_nra", tags=["NRA"])
    @ns.response(200, "Assessment detail", nra_output)
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(404, "Assessment not found in caller tenant")
    @login_required
    @ns.marshal_with(nra_output)
    def get(self, assessment_id):
        """Fetch a stored assessment by id."""
        run = AssessmentRun.query.filter_by(
            id=assessment_id, tenant_id=g.tenant_id).first_or_404()
        return {
            "assessment_id": run.id, "firm_id": run.firm_id,
            "stage": run.stage.value,
            "composite_score": run.composite_score, "band": run.band,
            "scores": [dict(dimension_code=s.dimension_code, value=s.value,
                            raw_sum=s.raw_sum, evidence_tier=s.evidence_tier)
                       for s in run.scores],
            "narrative": None,
            "transformation_type": run.transformation_type,
            "transformation_secondary": run.transformation_secondary,
        }


# ---- Question catalogue (dTAS v2) ------------------------------------

from app.services.scoring.questions import QUESTIONS as NRA_CATALOGUE  # noqa: E402

question_out = ns.model("NRAQuestion", {
    "code": fields.String(example="S1"),
    "dimension": fields.String(enum=["S", "O", "SM", "T", "SK"]),
    "order": fields.Integer(example=1),
    "text": fields.String(
        example="We have a written 3-year strategy reviewed every quarter."),
    "rubric": fields.List(fields.String,
        description="5-level rubric aligned to answers 0..4. "
                    "Shown to the respondent so scoring is auditable."),
})


@ns.route("/questions")
class QuestionCatalogue(Resource):
    @ns.doc("list_nra_questions", tags=["NRA"])
    @ns.response(200, "The 40-question dTAS v2 catalogue",
                 [question_out])
    @login_required
    @ns.marshal_list_with(question_out)
    def get(self):
        """Return the 40-question NRA catalogue (Organisation scope).

        Ordered by dimension (S / O / SM / T / SK) and within each
        dimension by ``order`` (1..8). Each question carries a 5-level
        rubric so respondents know exactly what each 0..4 answer means.
        """
        return [
            {"code": q.code, "dimension": q.dimension,
             "order": q.order, "text": q.text,
             "rubric": list(q.rubric)}
            for q in NRA_CATALOGUE
        ]

