"""/snapshot namespace — W0.0 Instant Snapshot (read-only)."""
from __future__ import annotations

from flask_restx import Namespace, Resource, fields

from app.api.v1.security import login_required
from app.models.reference import Sector
from app.services.snapshot_service import render_snapshot

ns = Namespace("snapshot",
    description="W0.0 Instant Snapshot — 60-second, zero-input, read-only",
    path="/snapshot")

SECTOR_CODES = ["manufacturing", "pharma", "textile", "automotive",
                "agro", "services", "it", "distribution"]

scheme_change = ns.model("SchemeChange", {
    "scheme": fields.String(example="PLI Scheme"),
    "change": fields.String(example="Tier-2 auto-ancillary window extended"),
    "evidence_tier": fields.String(example="L0b"),
})

macro_context = ns.model("MacroContext", {
    "sector_growth_pct_yoy": fields.Float(example=7.4),
    "roic_median_pct": fields.Float(example=11.2),
    "recent_scheme_changes": fields.List(fields.Nested(scheme_change)),
    "refreshed_at": fields.String(example="2026-04-24T09:00:00Z"),
})

snapshot_initiative = ns.model("SnapshotInitiative", {
    "title": fields.String(example="Implement OEE programme on the binding line"),
    "transformation_type": fields.String(
        enum=["process", "organisational", "digital", "hybrid", "none_yet"],
        example="process"),
    "target_dimension": fields.String(enum=["S", "O", "SM", "T", "SK"], example="O"),
    "roic_impact_bps": fields.Integer(example=180),
    "horizon_months": fields.Integer(example=9),
    "evidence_tier": fields.String(example="L0b"),
})

snapshot_output = ns.model("Snapshot", {
    "sector_code": fields.String(example="manufacturing"),
    "sector_name": fields.String(example="Manufacturing"),
    "macro_context": fields.Nested(macro_context),
    "top_initiatives": fields.List(fields.Nested(snapshot_initiative)),
    "narrative": fields.String(description="Narrator prose with L-pill citations"),
    "is_read_only": fields.Boolean(default=True),
})


@ns.route("/<string:sector_code>")
@ns.param("sector_code", "Sector slug", enum=SECTOR_CODES)
class SectorSnapshot(Resource):
    @ns.doc("get_snapshot", tags=["Snapshot"])
    @ns.response(200, "Instant Snapshot for the sector", snapshot_output)
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(404, "Unknown sector code")
    @login_required
    @ns.marshal_with(snapshot_output)
    def get(self, sector_code):
        """Return the W0.0 Instant Snapshot for a sector.

        Strictly non-writing — no rows created in the NRA store (AC #9).
        """
        sector = Sector.query.filter_by(code=sector_code).first()
        if not sector:
            ns.abort(404, f"Unknown sector '{sector_code}'")
        return render_snapshot(sector)
