"""/prescreener namespace — W0.1 six-question band classifier."""
from __future__ import annotations

from flask import request
from flask_restx import Namespace, Resource, fields

from app.api.v1.security import login_required
from app.services.scoring.engine import bankers_round, boundary_snap, classify_band

ns = Namespace("prescreener",
    description="W0.1 six-question pre-screener (low confidence by design)",
    path="/prescreener")

prescreener_input = ns.model("PrescreenerInput", {
    "answers": fields.List(fields.Integer(min=0, max=4),
        required=True, min_items=6, max_items=6,
        example=[2, 3, 2, 1, 3, 2],
        description="Exactly 6 integer answers in [0, 4]"),
})

prescreener_output = ns.model("PrescreenerOutput", {
    "probable_score": fields.Integer(example=54),
    "probable_band": fields.String(
        enum=["Legacy", "Siloed", "Strategic", "Future-Ready"], example="Siloed"),
    "confidence": fields.String(enum=["low", "medium"], default="low"),
})


@ns.route("/")
class Prescreener(Resource):
    @ns.doc("run_prescreener", tags=["Prescreener"])
    @ns.expect(prescreener_input, validate=True)
    @ns.response(200, "Probable band", prescreener_output)
    @ns.response(400, "Wrong number of answers")
    @ns.response(401, "Missing or invalid bearer token")
    @login_required
    @ns.marshal_with(prescreener_output)
    def post(self):
        """Return the probable band from 6 indicative answers."""
        body = request.get_json()
        answers = body["answers"]
        if len(answers) != 6:
            ns.abort(400, f"Expected 6 answers, got {len(answers)}")
        scaled = sum(answers) * 100 / 24
        score = boundary_snap(bankers_round(scaled))
        band = classify_band(score)
        return {"probable_score": score, "probable_band": band.value, "confidence": "low"}
