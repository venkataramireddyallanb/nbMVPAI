"""/platform namespace — system-wide overview & status surface.

Returns a role-aware "where am I in the platform" payload. Used by the
frontend Platform Overview page to render personalised callouts (e.g.
"You are an Expert in Wave W2 of the SME's journey").
"""
from __future__ import annotations

from flask import g
from flask_restx import Namespace, Resource, fields

from app.api.v1.security import login_required
from app.extensions import db
from app.models.charter import Charter
from app.models.expert import Expert
from app.models.firm import Firm
from app.models.user import User

ns = Namespace("platform",
    description="Platform overview, status, and role-aware framing",
    path="/platform")


persona_card = ns.model("PersonaCard", {
    "key": fields.String(enum=["sme", "expert", "partner"], example="sme"),
    "label": fields.String(example="SME owner / operator"),
    "tagline": fields.String,
    "value_props": fields.List(fields.String),
})

wave_step = ns.model("WaveStep", {
    "code": fields.String(example="W1"),
    "name": fields.String(example="NRA Assessment"),
    "summary": fields.String,
    "personas": fields.List(fields.String,
        description="Personas with a touchpoint in this wave"),
})

invariant_item = ns.model("InvariantItem", {
    "code": fields.String(example="AC#1"),
    "summary": fields.String(example="Scores 35/65/85 are unreachable"),
    "enforced_by": fields.String(example="services.scoring.engine.boundary_snap"),
})

caller_context = ns.model("CallerContext", {
    "role": fields.String,
    "tenant_id": fields.String,
    "persona": fields.String(enum=["sme", "expert", "partner", "admin"]),
    "current_wave": fields.String(allow_null=True,
        example="W1.5", description="Spec wave the caller is meaningfully in"),
    "headline_metric": fields.Raw(
        description="Role-specific KPI: composite for SME, leads for Expert, "
                    "cohort coverage for Partner"),
})

overview_output = ns.model("PlatformOverview", {
    "platform_name": fields.String(example="nicheBrains"),
    "platform_version": fields.String(example="5.0.0"),
    "tagline": fields.String,
    "personas": fields.List(fields.Nested(persona_card)),
    "waves": fields.List(fields.Nested(wave_step)),
    "invariants": fields.List(fields.Nested(invariant_item)),
    "you": fields.Nested(caller_context),
})


# ---- Static catalogues ----------------------------------------------

PERSONAS = [
    {
        "key": "sme",
        "label": "SME owner / operator",
        "tagline": "From diagnosis to delivery — with evidence.",
        "value_props": [
            "60-second Instant Snapshot of your sector's three highest-ROIC plays",
            "40-question NRA returns an evidenced reading across S/O/SM/T/SK",
            "Top-3 expert shortlist with reason chips and fit scores",
            "Owner signs every Gate — agents never sign, pay, or commit",
        ],
    },
    {
        "key": "expert",
        "label": "Expert / practitioner",
        "tagline": "Shortlists where your evidence speaks.",
        "value_props": [
            "Top-3-only shortlists keep your pipeline curated",
            "Anchor evidence (L0/L3) determines who appears in shortlists",
            "Outcomes promote on the L0a → L4 evidence ladder",
            "Proven outcomes feed sector-default uplifts in the next ranker run",
        ],
    },
    {
        "key": "partner",
        "label": "Ecosystem partner",
        "tagline": "Cohort intelligence with PII on a leash.",
        "value_props": [
            "Sector medians + band distribution across your cohort",
            "Min cohort of 20 firms before any benchmark exposure",
            "Scheme registry with applicability windows",
            "No PII ever — only medians, counts, and rollups",
        ],
    },
]

WAVES = [
    {"code": "W0.0", "name": "Instant Snapshot",
     "summary": "60-second sector-only read. Read-only by contract.",
     "personas": ["sme"]},
    {"code": "W0.1", "name": "Pre-screener",
     "summary": "6 questions → probable band (low confidence).",
     "personas": ["sme"]},
    {"code": "W1",   "name": "NRA Assessment",
     "summary": "40 questions, deterministic scoring. Composite + 5-dim.",
     "personas": ["sme"]},
    {"code": "W1.5", "name": "Charter draft + Gate 1",
     "summary": "Drafter agent composes the 7-field Charter. Owner signs.",
     "personas": ["sme", "expert"]},
    {"code": "W2",   "name": "Matchmaking & Engagement",
     "summary": "Top-3 expert shortlist. Anchor evidence required.",
     "personas": ["sme", "expert"]},
    {"code": "W3",   "name": "Proposal & Contracting",
     "summary": "Expert proposal, owner approves. Gate 2.",
     "personas": ["sme", "expert"]},
    {"code": "W4",   "name": "Execution & Monitoring",
     "summary": "Milestones tracked. Finance Agent watches working capital.",
     "personas": ["sme", "expert"]},
    {"code": "W5",   "name": "Outcomes & Copilot",
     "summary": "Outcomes promote on the evidence ladder.",
     "personas": ["sme", "expert", "partner"]},
    {"code": "W6",   "name": "Vertical Agents",
     "summary": "Manufacturing / Pharma / Textile playbooks.",
     "personas": ["sme", "partner"]},
]

INVARIANTS = [
    {"code": "AC#1",  "summary": "Scores 35 / 65 / 85 are mathematically unreachable",
     "enforced_by": "app.services.scoring.engine.boundary_snap"},
    {"code": "AC#4",  "summary": "Every narrative paragraph carries an L-pill citation",
     "enforced_by": "app.utils.citations.assert_all_paragraphs_cited"},
    {"code": "AC#6",  "summary": "Initiative shortlist is 3 ≤ N ≤ 5",
     "enforced_by": "app.services.ranking.initiative_ranker.rank_initiatives"},
    {"code": "AC#9",  "summary": "Instant Snapshot is strictly read-only",
     "enforced_by": "app.services.snapshot_service.render_snapshot"},
    {"code": "AC#10", "summary": "Exactly 2 LLM agents in production (Narrator + Drafter)",
     "enforced_by": "app.agents.crews.nichebrains_crew.NicheBrainsCrew"},
    {"code": "—",     "summary": "Expert match top-3 only; L0/L3 anchor required",
     "enforced_by": "app.services.ranking.expert_ranker.rank_experts"},
    {"code": "—",     "summary": "Benchmarks require cohort ≥ 20 (PII guard)",
     "enforced_by": "app.services.partner_service.cohort_benchmark"},
    {"code": "—",     "summary": "Multi-tenant isolation on every domain row",
     "enforced_by": "app.models.base.TenantScopedMixin"},
    {"code": "—",     "summary": "Agents never sign, pay, or commit",
     "enforced_by": "app.api.v1.namespaces.charters.ApproveCharter (OWNER role only)"},
]


# ---- Caller-context resolution --------------------------------------

def _persona_for(user: User) -> str:
    role = user.role.value
    if role == "expert":  return "expert"
    if role == "partner": return "partner"
    if role == "admin":   return "admin"
    return "sme"


def _caller_context(user: User) -> dict:
    persona = _persona_for(user)
    tenant_id = user.tenant_id

    if persona == "sme":
        firm = Firm.query.filter_by(tenant_id=tenant_id).first()
        latest_charter = (Charter.query.filter_by(tenant_id=tenant_id)
                          .order_by(Charter.created_at.desc()).first())
        wave = "W0.0"
        if firm: wave = "W0.0"
        if latest_charter:
            if latest_charter.status.value in ("draft", "pending_approval"):
                wave = "W1.5"
            elif latest_charter.status.value == "approved":
                wave = "W2"
            elif latest_charter.status.value == "in_delivery":
                wave = "W4"
            elif latest_charter.status.value == "completed":
                wave = "W5"
        return {
            "role": user.role.value,
            "tenant_id": tenant_id,
            "persona": persona,
            "current_wave": wave,
            "headline_metric": {
                "kind": "composite",
                "label": "Latest composite score",
                "value": "—",
            },
        }

    if persona == "expert":
        expert = Expert.query.filter_by(tenant_id=tenant_id).first()
        # Lead count without circular import — count Match rows for this expert.
        leads = 0
        if expert:
            from app.models.engagement import Match
            leads = db.session.query(Match).filter(Match.expert_id == expert.id).count()
        return {
            "role": user.role.value,
            "tenant_id": tenant_id,
            "persona": persona,
            "current_wave": "W2",
            "headline_metric": {
                "kind": "leads",
                "label": "Active leads (top-3 shortlist)",
                "value": leads,
            },
        }

    if persona == "partner":
        return {
            "role": user.role.value,
            "tenant_id": tenant_id,
            "persona": persona,
            "current_wave": "W5",
            "headline_metric": {
                "kind": "cohort_coverage",
                "label": "Cohort coverage",
                "value": "see /partner",
            },
        }

    # admin
    return {
        "role": user.role.value,
        "tenant_id": tenant_id,
        "persona": persona,
        "current_wave": None,
        "headline_metric": {"kind": "platform", "label": "Cross-tenant view", "value": "all"},
    }


# ---- Endpoint -------------------------------------------------------

@ns.route("/overview")
class PlatformOverview(Resource):
    @ns.doc("get_platform_overview", tags=["Platform"])
    @ns.response(200, "Platform overview tailored to caller", overview_output)
    @ns.response(401, "Missing or invalid bearer token")
    @login_required
    @ns.marshal_with(overview_output)
    def get(self):
        """Return the platform overview, personalised by caller role + tenant.

        Designed for the frontend /overview page. Static fields (personas,
        waves, invariants) are constant; ``you`` is computed per request.
        """
        from flask import current_app
        return {
            "platform_name": current_app.config.get("APP_NAME", "nicheBrains"),
            "platform_version": current_app.config.get("APP_VERSION", "5.0.0"),
            "tagline": "AI-native digital transformation for Indian MSMEs.",
            "personas": PERSONAS,
            "waves": WAVES,
            "invariants": INVARIANTS,
            "you": _caller_context(g.current_user),
        }


# ---- Product & Data Architecture -----------------------------------

entity_info = ns.model("ArchitectureEntity", {
    "name": fields.String(example="Firm"),
    "table": fields.String(example="firms"),
    "tenant_scoped": fields.Boolean,
    "row_count": fields.Integer(
        description="Row count within the caller's tenant "
                    "(NULL for global reference tables)"),
    "purpose": fields.String,
})

relationship_info = ns.model("ArchitectureRelationship", {
    "parent": fields.String(example="Firm"),
    "child": fields.String(example="AssessmentRun"),
    "kind": fields.String(enum=["1-to-many", "1-to-1", "many-to-many"]),
    "cascade": fields.String(enum=["CASCADE", "SET NULL", "none"]),
    "note": fields.String,
})

layer_info = ns.model("ArchitectureLayer", {
    "name": fields.String(example="HTTP (api/)"),
    "responsibility": fields.String,
    "examples": fields.List(fields.String),
})

wave_mapping = ns.model("ArchitectureWaveMapping", {
    "wave": fields.String(example="W1"),
    "endpoint": fields.String(example="POST /api/v1/nra/"),
    "tables_written": fields.List(fields.String),
    "tables_read": fields.List(fields.String),
})

architecture_output = ns.model("ProductArchitecture", {
    "layers": fields.List(fields.Nested(layer_info)),
    "entities": fields.List(fields.Nested(entity_info)),
    "relationships": fields.List(fields.Nested(relationship_info)),
    "wave_mapping": fields.List(fields.Nested(wave_mapping)),
})


# ---- Static catalogues ---------------------------------------------

LAYERS = [
    {"name": "HTTP (api/)", "responsibility":
        "Flask-RESTX namespaces. Parse request, shape response. No business rules.",
     "examples": ["api/v1/namespaces/auth.py", "api/v1/namespaces/nra.py"]},
    {"name": "Application (services/)", "responsibility":
        "Orchestration of models + agents + engines. Tenant-scoped.",
     "examples": ["services/nra_service.py", "services/charter_service.py",
                  "services/matching_service.py", "services/partner_service.py",
                  "services/value_creation/"]},
    {"name": "Deterministic engines (services/scoring, services/ranking)",
     "responsibility":
        "Pure functions. No framework deps. Spec invariants live here.",
     "examples": ["services/scoring/engine.py",
                  "services/ranking/initiative_ranker.py",
                  "services/ranking/expert_ranker.py",
                  "services/value_creation/engine.py"]},
    {"name": "AI agents (agents/)", "responsibility":
        "Exactly 2 LLM agents — Narrator + Drafter (AC #10).",
     "examples": ["agents/crews/nichebrains_crew.py"]},
    {"name": "Domain (models/)", "responsibility":
        "SQLAlchemy ORM. Every domain row carries tenant_id.",
     "examples": ["models/base.py", "models/firm.py", "models/charter.py"]},
]

ENTITIES = [
    # (name, table, tenant_scoped, purpose)
    ("Tenant", "tenants", False, "Root of multi-tenant isolation"),
    ("User", "users", False, "Authenticated login (tenant FK, not mixin)"),
    ("Person", "persons", False, "Human identity across dual roles"),
    ("Sector", "sectors", False, "Global reference: sector taxonomy"),
    ("Dimension", "dimensions", False, "Global reference: S/O/SM/T/SK"),
    ("Firm", "firms", True, "SME / Company Master"),
    ("FirmFinancials", "firm_financials", True, "P&L + BS per period"),
    ("Expert", "experts", True, "Marketplace supply side"),
    ("Partner", "partners", True, "Ecosystem partner org"),
    ("AssessmentRun", "assessment_runs", True, "One dTAS run per scope/period"),
    ("Score", "scores", True, "Per-dimension integer score"),
    ("EvidenceRecord", "evidence_records", True, "Normalised atomic input"),
    ("Evidence", "evidence", True, "Uploaded artefact (polymorphic attach)"),
    ("Initiative", "initiatives", True, "Ranker output candidate"),
    ("Charter", "charters", True, "7-field plan · Gate 1"),
    ("Milestone", "milestones", True, "90-day steps"),
    ("Outcome", "outcomes", True, "Closed-charter reading"),
    ("Match", "matches", True, "Top-3 expert proposal"),
]

RELATIONSHIPS = [
    {"parent": "Tenant", "child": "User", "kind": "1-to-many",
     "cascade": "CASCADE", "note": "Users delete with tenant"},
    {"parent": "Tenant", "child": "Firm", "kind": "1-to-many",
     "cascade": "CASCADE", "note": "SME tenants typically have 1 firm"},
    {"parent": "Firm", "child": "AssessmentRun", "kind": "1-to-many",
     "cascade": "CASCADE", "note": "History of dTAS runs"},
    {"parent": "AssessmentRun", "child": "Score", "kind": "1-to-many",
     "cascade": "CASCADE", "note": "Exactly 5 — one per dimension"},
    {"parent": "AssessmentRun", "child": "EvidenceRecord", "kind": "1-to-many",
     "cascade": "CASCADE", "note": "Normalised inputs"},
    {"parent": "AssessmentRun", "child": "Initiative", "kind": "1-to-many",
     "cascade": "CASCADE", "note": "Ranker output"},
    {"parent": "Initiative", "child": "Charter", "kind": "1-to-1",
     "cascade": "SET NULL", "note": "Charter operationalises one initiative"},
    {"parent": "AssessmentRun", "child": "Charter", "kind": "1-to-many",
     "cascade": "SET NULL", "note": "nra_run_id on charter (invariant)"},
    {"parent": "Charter", "child": "Milestone", "kind": "1-to-many",
     "cascade": "CASCADE", "note": "90-day milestones"},
    {"parent": "Charter", "child": "Outcome", "kind": "1-to-many",
     "cascade": "CASCADE", "note": "Closed-charter readings"},
    {"parent": "Charter", "child": "Match", "kind": "1-to-many",
     "cascade": "CASCADE", "note": "Top-3 only — replaced on re-match"},
    {"parent": "Expert", "child": "Match", "kind": "1-to-many",
     "cascade": "CASCADE", "note": "Cross-tenant join via Match"},
    {"parent": "Person", "child": "User", "kind": "1-to-many",
     "cascade": "SET NULL", "note": "Dual-role — one Person, many logins"},
    {"parent": "Person", "child": "Expert", "kind": "1-to-1",
     "cascade": "CASCADE", "note": "Expert identity"},
    {"parent": "Firm", "child": "FirmFinancials", "kind": "1-to-many",
     "cascade": "CASCADE", "note": "One row per period"},
]

WAVE_MAPPING = [
    {"wave": "W0.0", "endpoint": "GET /snapshot/{sector}",
     "tables_written": [], "tables_read": ["sectors"]},
    {"wave": "W0.1", "endpoint": "POST /prescreener/",
     "tables_written": [], "tables_read": []},
    {"wave": "W1",   "endpoint": "POST /nra/",
     "tables_written": ["assessment_runs", "scores"], "tables_read": ["firms"]},
    {"wave": "W1.5", "endpoint": "POST /charters/draft",
     "tables_written": ["charters"],
     "tables_read": ["assessment_runs", "initiatives"]},
    {"wave": "Gate 1", "endpoint": "POST /charters/{id}/approve",
     "tables_written": ["charters"], "tables_read": []},
    {"wave": "W2",   "endpoint": "GET /experts/match/{charter_id}",
     "tables_written": ["matches"],
     "tables_read": ["experts", "charters", "firms"]},
    {"wave": "W4",   "endpoint": "GET /firms/{id}/driver-tree",
     "tables_written": [],
     "tables_read": ["firms", "firm_financials", "initiatives"]},
    {"wave": "Partner", "endpoint": "GET /partner/cohort/{sector}",
     "tables_written": [],
     "tables_read": ["assessment_runs", "scores", "firms", "sectors"]},
    {"wave": "Expert", "endpoint": "GET /experts/me/leads",
     "tables_written": [],
     "tables_read": ["experts", "matches", "charters", "firms"]},
]


@ns.route("/architecture")
class ProductArchitecture(Resource):
    @ns.doc("get_product_architecture", tags=["Platform"])
    @ns.response(200, "Live architecture descriptor", architecture_output)
    @ns.response(401, "Missing or invalid bearer token")
    @login_required
    @ns.marshal_with(architecture_output)
    def get(self):
        """Product & Data Architecture — layers, entities (with live row
        counts for the caller's tenant), relationships, and wave-to-
        endpoint mapping.

        Designed for the frontend /architecture page. Row counts reflect
        the caller's tenant only, which makes this a living diagram.
        """
        from app.extensions import db
        from app.models.assessment import (AssessmentRun, EvidenceRecord,
                                           Score)
        from app.models.charter import Charter, Milestone, Outcome
        from app.models.engagement import Initiative, Match
        from app.models.evidence import Evidence
        from app.models.expert import Expert
        from app.models.financials import FirmFinancials
        from app.models.firm import Firm
        from app.models.partner import Partner
        from app.models.person import Person
        from app.models.reference import Dimension, Sector
        from app.models.tenant import Tenant
        from app.models.user import User

        # Map entity name → SQLAlchemy class for count queries.
        tenant_scoped_map = {
            "Firm": Firm, "FirmFinancials": FirmFinancials,
            "Expert": Expert, "Partner": Partner,
            "AssessmentRun": AssessmentRun, "Score": Score,
            "EvidenceRecord": EvidenceRecord, "Evidence": Evidence,
            "Initiative": Initiative, "Charter": Charter,
            "Milestone": Milestone, "Outcome": Outcome, "Match": Match,
        }
        unscoped_map = {
            "Tenant": Tenant, "User": User, "Person": Person,
            "Sector": Sector, "Dimension": Dimension,
        }

        tenant_id = g.tenant_id
        entities = []
        for name, table, scoped, purpose in ENTITIES:
            if scoped:
                cls = tenant_scoped_map.get(name)
                count = (db.session.query(cls)
                         .filter(cls.tenant_id == tenant_id).count()
                         if cls else 0)
            else:
                cls = unscoped_map.get(name)
                count = db.session.query(cls).count() if cls else 0
            entities.append({
                "name": name, "table": table,
                "tenant_scoped": scoped, "row_count": count,
                "purpose": purpose,
            })

        return {
            "layers": LAYERS,
            "entities": entities,
            "relationships": RELATIONSHIPS,
            "wave_mapping": WAVE_MAPPING,
        }


# ---- v3.1 Benchmark Family (Table 5) -------------------------------

from app.services.benchmarks import CATALOGUE as BENCHMARK_CATALOGUE  # noqa: E402

benchmark_gate = ns.model("BenchmarkGate", {
    "output_type": fields.String(example="Initiative Shortlist"),
    "benchmark_kind": fields.String(example="Precision-at-3 vs expert-adjudicated"),
    "target_bar": fields.String(example="≥ 0.75"),
    "promotion_gate_for": fields.String(example="DRG Recommendation Engine launch"),
})


@ns.route("/benchmarks")
class BenchmarkFamily(Resource):
    @ns.doc("get_benchmark_family", tags=["Platform"])
    @ns.response(200, "DDExpert v3.1 Table 5 — promotion gates",
                 [benchmark_gate])
    @ns.response(401, "Missing or invalid bearer token")
    @login_required
    @ns.marshal_list_with(benchmark_gate)
    def get(self):
        """Return the v3.1 benchmark family.

        Every promotion (rule → model → LLM → agent) must clear the named
        benchmark gate before shipping. The corpus is frozen, versioned,
        and withheld from all training runs (§6.6).
        """
        return [
            {"output_type": b.output_type,
             "benchmark_kind": b.benchmark_kind,
             "target_bar": b.target_bar,
             "promotion_gate_for": b.promotion_gate_for}
            for b in BENCHMARK_CATALOGUE
        ]

