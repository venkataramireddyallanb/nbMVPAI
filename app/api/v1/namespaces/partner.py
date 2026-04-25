"""/partner namespace — cohort dashboards + scheme registry.

Strict rule: benchmark exposure requires min cohort of 20 firms.
Enforced in the service layer; when n < 20 the is_exposed flag goes
false and numeric fields are zeroed so no PII leaks.
"""
from __future__ import annotations

from flask import g
from flask_restx import Namespace, Resource, fields

from app.api.v1.security import role_required
from app.models.user import UserRole
from app.services.partner_service import (
    cohort_benchmark,
    cohort_distribution,
    list_schemes,
)

ns = Namespace("partner",
    description="Partner cohort dashboards, distributions, and schemes",
    path="/partner")

SECTOR_CODES = ["manufacturing", "pharma", "textile", "automotive",
                "agro", "services", "it", "distribution"]


cohort_output = ns.model("Cohort", {
    "sector_code": fields.String,
    "n_firms": fields.Integer(example=42),
    "median_composite": fields.Integer(example=62),
    "median_by_dimension": fields.Raw(
        example={"S": 55, "O": 64, "SM": 58, "T": 48, "SK": 62}),
    "scheme_uptake": fields.Raw,
    "is_exposed": fields.Boolean(example=True,
        description="False when n < 20; numeric fields zeroed in that case"),
})


distribution_bucket = ns.model("DistributionBucket", {
    "band": fields.String(
        enum=["Legacy", "Siloed", "Strategic", "Future-Ready"]),
    "n_firms": fields.Integer(example=14),
    "pct": fields.Float(example=33.3,
        description="Percentage of cohort in this band"),
})


distribution_output = ns.model("CohortDistribution", {
    "sector_code": fields.String,
    "n_firms": fields.Integer(example=42),
    "is_exposed": fields.Boolean,
    "distribution": fields.List(fields.Nested(distribution_bucket)),
})


scheme_output = ns.model("Scheme", {
    "scheme_code": fields.String(example="pli"),
    "scheme_name": fields.String(example="Production Linked Incentive"),
    "ministry": fields.String(example="Ministry of Commerce & Industry"),
    "applicable_sectors": fields.List(fields.String),
    "applicable_size_bands": fields.List(fields.String),
    "deadline": fields.String(allow_null=True, example="2026-12-31"),
    "summary": fields.String,
    "evidence_tier": fields.String(example="L0b"),
})


# ---- Endpoints --------------------------------------------------------

@ns.route("/cohort/<string:sector_code>")
@ns.param("sector_code", "Sector to aggregate over", enum=SECTOR_CODES)
class CohortBenchmark(Resource):
    @ns.doc("get_cohort_benchmark", tags=["Partner"])
    @ns.response(200, "Cohort benchmark (masked if n<20)", cohort_output)
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(403, "Caller is not PARTNER role")
    @role_required(UserRole.PARTNER)
    @ns.marshal_with(cohort_output)
    def get(self, sector_code):
        """Return the sector cohort benchmark for a partner.

        Medians across all completed NRAs in the sector (cross-tenant
        aggregate). No PII. If n < 20, numeric fields are zeroed.
        """
        return cohort_benchmark(sector_code=sector_code, tenant_id=g.tenant_id)


@ns.route("/cohort/<string:sector_code>/distribution")
@ns.param("sector_code", "Sector to aggregate over", enum=SECTOR_CODES)
class CohortDistribution(Resource):
    @ns.doc("get_cohort_distribution", tags=["Partner"])
    @ns.response(200, "Band distribution (masked if n<20)", distribution_output)
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(403, "Caller is not PARTNER role")
    @role_required(UserRole.PARTNER)
    @ns.marshal_with(distribution_output)
    def get(self, sector_code):
        """Return the distribution of firms across the 4 bands for a sector.

        Useful for visualising "how many firms are still in Legacy vs.
        Strategic?" Drives partner UIs that need to show the mix rather
        than a single median.
        """
        return cohort_distribution(sector_code=sector_code, tenant_id=g.tenant_id)


@ns.route("/schemes")
class SchemeList(Resource):
    @ns.doc("list_schemes", tags=["Partner"])
    @ns.response(200, "Applicable schemes and windows", [scheme_output])
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(403, "Caller is not PARTNER role")
    @role_required(UserRole.PARTNER)
    @ns.marshal_list_with(scheme_output)
    def get(self):
        """List schemes applicable to the partner's watchlist.

        In v5.0 this is a stub registry (L0b). v5.1 wires it to the GST /
        MCA / PLI feeds so the macro-context strip is live-refreshed.
        """
        return list_schemes()
