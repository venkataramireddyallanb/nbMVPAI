"""/firms namespace — CRUD for the SME profile (Company Master)."""
from __future__ import annotations

from flask import g, request
from flask_restx import Namespace, Resource, fields

from app.api.v1.security import login_required
from app.extensions import db
from app.models.firm import Firm
from app.models.reference import Sector

ns = Namespace("firms", description="SME / MSME profiles (Company Master)", path="/firms")

SECTOR_CODES = ["manufacturing", "pharma", "textile", "automotive",
                "agro", "services", "it", "distribution"]

firm_output = ns.model("Firm", {
    "id": fields.String,
    "legal_name": fields.String(example="Rao Textiles Pvt Ltd"),
    "display_name": fields.String(allow_null=True),
    "sector_code": fields.String(enum=SECTOR_CODES, example="textile"),
    "size_band": fields.String(enum=["micro", "small", "mid", "upper_mid"],
        example="mid",
        description="Revenue band: micro<10Cr, small 10-50, mid 50-150, upper_mid 150-500"),
    "cin": fields.String(example="U17299GJ2008PTC054321"),
    "gstin": fields.String(example="24ABCDE1234F1Z5"),
    "state": fields.String(example="Gujarat"),
    "city": fields.String(example="Ahmedabad"),
    "founded_year": fields.String(example="2008"),
    "sub_persona_tags": fields.Raw(description="Free-form cluster or persona tags"),
})

firm_input = ns.model("FirmInput", {
    "legal_name": fields.String(required=True, example="Rao Textiles Pvt Ltd"),
    "sector_code": fields.String(required=True, example="textile"),
    "size_band": fields.String(required=False, default="small",
        enum=["micro", "small", "mid", "upper_mid"]),
    "cin": fields.String, "gstin": fields.String,
    "state": fields.String, "city": fields.String,
    "founded_year": fields.String, "sub_persona_tags": fields.Raw,
})


def _serialize(f):
    return dict(id=f.id, legal_name=f.legal_name, display_name=f.display_name,
                sector_code=f.sector.code if f.sector else None,
                size_band=f.size_band, cin=f.cin, gstin=f.gstin,
                state=f.state, city=f.city, founded_year=f.founded_year,
                sub_persona_tags=f.sub_persona_tags)


@ns.route("/")
class FirmList(Resource):
    @ns.doc("list_firms", tags=["Firms"])
    @ns.response(200, "Firms in caller tenant", [firm_output])
    @ns.response(401, "Missing or invalid bearer token")
    @login_required
    @ns.marshal_list_with(firm_output)
    def get(self):
        """List firms in the caller tenant."""
        return [_serialize(f) for f in
                Firm.query.filter_by(tenant_id=g.tenant_id).all()]

    @ns.doc("create_firm", tags=["Firms"])
    @ns.expect(firm_input, validate=True)
    @ns.response(201, "Firm created", firm_output)
    @ns.response(400, "Unknown sector_code or validation error")
    @ns.response(401, "Missing or invalid bearer token")
    @login_required
    @ns.marshal_with(firm_output, code=201)
    def post(self):
        """Create a new Firm under the caller tenant."""
        body = request.get_json()
        sector = Sector.query.filter_by(code=body["sector_code"]).first()
        if not sector:
            ns.abort(400, f"Unknown sector '{body['sector_code']}'")
        firm = Firm(tenant_id=g.tenant_id, legal_name=body["legal_name"],
            sector_id=sector.id, size_band=body.get("size_band", "small"),
            cin=body.get("cin"), gstin=body.get("gstin"),
            state=body.get("state"), city=body.get("city"),
            founded_year=body.get("founded_year"),
            sub_persona_tags=body.get("sub_persona_tags"))
        db.session.add(firm)
        db.session.commit()
        return _serialize(firm), 201


@ns.route("/<string:firm_id>")
@ns.param("firm_id", "UUID of the firm within the caller tenant")
class FirmDetail(Resource):
    @ns.doc("get_firm", tags=["Firms"])
    @ns.response(200, "Firm detail", firm_output)
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(404, "Firm not found in caller tenant")
    @login_required
    @ns.marshal_with(firm_output)
    def get(self, firm_id):
        """Fetch one firm by id (tenant-scoped)."""
        f = Firm.query.filter_by(id=firm_id, tenant_id=g.tenant_id).first_or_404()
        return _serialize(f)


# ---- Driver tree (ROIC value-creation) ------------------------------

from app.services.value_creation.service import get_driver_tree_for_firm  # noqa: E402

driver_node = ns.model("DriverNode", {
    "label": fields.String(example="Operating Margin"),
    "value": fields.Float(example=15.0),
    "unit": fields.String(enum=["INR", "percent", "ratio"], example="percent"),
    "delta_bps": fields.Float(allow_null=True,
        description="Change in basis points vs. baseline (for uplift nodes)"),
    "note": fields.String(example="OP / Revenue"),
})

value_reading = ns.model("ValueReading", {
    "operating_margin_pct": fields.Float(example=15.0),
    "capital_turnover": fields.Float(example=1.25),
    "effective_tax_rate_pct": fields.Float(example=25.0),
    "roic_pct": fields.Float(example=14.06,
        description="ROIC = OM × CT × (1 − ETR) per spec"),
    "roa_pct": fields.Float(allow_null=True,
        description="Only populated for asset-intensive sectors "
                    "(Manufacturing / Pharma / Textile / Agro)"),
    "drivers": fields.List(fields.Nested(driver_node)),
})

driver_tree_output = ns.model("DriverTree", {
    "firm_id": fields.String,
    "sector_code": fields.String(allow_null=True),
    "is_asset_intensive": fields.Boolean(example=True,
        description="True when sector ∈ {manufacturing, pharma, textile, agro} → dual view"),
    "period_code": fields.String(allow_null=True, example="FY25"),
    "period_end_year": fields.Integer(allow_null=True, example=2025),
    "evidence_tier": fields.String(example="L1"),
    "current": fields.Nested(value_reading, allow_null=True,
        description="Current-period reading. Null if no FirmFinancials rows yet."),
    "projected": fields.Nested(value_reading, allow_null=True,
        description="12-month projected ROIC with initiative uplifts applied"),
    "initiative_uplifts_bps": fields.List(fields.Integer,
        description="bps uplifts sourced from approved initiatives"),
})


@ns.route("/<string:firm_id>/driver-tree")
@ns.param("firm_id", "UUID of the firm within caller tenant")
class DriverTree(Resource):
    @ns.doc("get_firm_driver_tree", tags=["Firms"])
    @ns.response(200, "Driver-tree + ROIC reading", driver_tree_output)
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(404, "Firm not found in caller tenant")
    @login_required
    @ns.marshal_with(driver_tree_output)
    def get(self, firm_id):
        """Return the value-creation driver tree for a firm.

        Computes:
          • ROIC = Operating Margin × Capital Turnover × (1 − Effective Tax Rate)
          • ROA  = Net Income / Total Assets (asset-intensive sectors only)
          • Current + 12-month projected (with approved-initiative uplifts)

        The projected reading is null when the firm has no approved
        initiatives; the current reading is null when no FirmFinancials
        rows exist yet (nudge the owner to input P&L primitives).
        """
        tree = get_driver_tree_for_firm(firm_id, tenant_id=g.tenant_id)
        if tree is None:
            ns.abort(404, f"Firm '{firm_id}' not found in caller tenant")
        return tree


# ---- Firm financials (P&L + BS inputs for ROIC) ---------------------

from app.models.financials import FirmFinancials  # noqa: E402

financials_input = ns.model("FirmFinancialsInput", {
    "period_code": fields.String(required=True, example="FY25"),
    "period_end_year": fields.Integer(required=True, example=2025),
    "revenue": fields.Float(required=True, example=142_00_00_000,
        description="Annual revenue in INR (nominal)"),
    "operating_profit": fields.Float(required=True, example=16_75_00_000,
        description="EBIT in INR"),
    "profit_before_tax": fields.Float(required=True, example=14_20_00_000),
    "tax": fields.Float(required=True, example=3_55_00_000),
    "invested_capital": fields.Float(required=True, example=88_00_00_000,
        description="Debt + Equity − Cash"),
    "total_assets": fields.Float(required=False, example=156_00_00_000,
        description="Required for ROA in asset-intensive sectors"),
    "evidence_tier": fields.String(required=False, default="L0a",
        enum=["L0a", "L0b", "L1", "L2", "L3", "L4"]),
    "source": fields.String(required=False, default="owner_input",
        enum=["owner_input", "mca", "gst", "upload"]),
})

financials_output = ns.model("FirmFinancials", {
    "id": fields.String,
    "firm_id": fields.String,
    "period_code": fields.String,
    "period_end_year": fields.Integer,
    "revenue": fields.Float,
    "operating_profit": fields.Float,
    "profit_before_tax": fields.Float,
    "tax": fields.Float,
    "invested_capital": fields.Float,
    "total_assets": fields.Float(allow_null=True),
    "evidence_tier": fields.String,
    "source": fields.String,
})


def _serialize_fin(f):
    return dict(id=f.id, firm_id=f.firm_id,
                period_code=f.period_code, period_end_year=f.period_end_year,
                revenue=f.revenue, operating_profit=f.operating_profit,
                profit_before_tax=f.profit_before_tax, tax=f.tax,
                invested_capital=f.invested_capital,
                total_assets=f.total_assets,
                evidence_tier=f.evidence_tier, source=f.source)


@ns.route("/<string:firm_id>/financials")
@ns.param("firm_id", "UUID of the firm within caller tenant")
class FinancialsList(Resource):
    @ns.doc("list_firm_financials", tags=["Firms"])
    @ns.response(200, "All periods for this firm (newest first)",
                 [financials_output])
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(404, "Firm not found in caller tenant")
    @login_required
    @ns.marshal_list_with(financials_output)
    def get(self, firm_id):
        """List FirmFinancials rows for a firm, newest period first."""
        firm = Firm.query.filter_by(id=firm_id, tenant_id=g.tenant_id).first_or_404()
        rows = (FirmFinancials.query
                .filter_by(firm_id=firm.id, tenant_id=g.tenant_id)
                .order_by(FirmFinancials.period_end_year.desc()).all())
        return [_serialize_fin(r) for r in rows]

    @ns.doc("create_firm_financials", tags=["Firms"])
    @ns.expect(financials_input, validate=True)
    @ns.response(201, "Financial period created", financials_output)
    @ns.response(400, "Validation error")
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(404, "Firm not found in caller tenant")
    @login_required
    @ns.marshal_with(financials_output, code=201)
    def post(self, firm_id):
        """Create a FirmFinancials row for one period.

        Once at least one row exists, /firms/{id}/driver-tree returns
        the live ROIC + driver-tree reading.
        """
        firm = Firm.query.filter_by(id=firm_id, tenant_id=g.tenant_id).first_or_404()
        body = request.get_json()
        if body["invested_capital"] <= 0:
            ns.abort(400, "invested_capital must be > 0")

        row = FirmFinancials(
            tenant_id=g.tenant_id, firm_id=firm.id,
            period_code=body["period_code"],
            period_end_year=int(body["period_end_year"]),
            revenue=float(body["revenue"]),
            operating_profit=float(body["operating_profit"]),
            profit_before_tax=float(body["profit_before_tax"]),
            tax=float(body["tax"]),
            invested_capital=float(body["invested_capital"]),
            total_assets=(float(body["total_assets"])
                          if body.get("total_assets") else None),
            evidence_tier=body.get("evidence_tier", "L0a"),
            source=body.get("source", "owner_input"),
        )
        db.session.add(row)
        db.session.commit()
        return _serialize_fin(row), 201

