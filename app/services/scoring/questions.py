"""dTAS v2 question catalogue — the 40-question Organisation scope.

In production the authoritative catalogue lives in `D-Tas_Design_v2.xlsx`
and is imported into a versioned table at boot. Here we ship the
structure in-code so the system is immediately usable; the text is
indicative but the code + dimension mapping + display order are real.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.scoring.engine import DIMENSION_CODES, QUESTIONS_PER_DIMENSION


@dataclass(frozen=True)
class NRAQuestion:
    code: str            # e.g. 'S1', 'O3', 'SK8'
    dimension: str       # one of DIMENSION_CODES
    order: int           # 1..8 within the dimension
    text: str            # question stem
    rubric: tuple[str, str, str, str, str]
    # 5-level rubric aligned to answers 0..4. Keeps scoring auditable:
    # the user sees what each level means before committing.


# 8 questions × 5 dimensions = 40.
QUESTIONS: tuple[NRAQuestion, ...] = (
    # ---- S — Strategy & Leadership ----
    NRAQuestion("S1", "S", 1, "We have a written 3-year strategy reviewed every quarter.",
        ("No written strategy", "Document exists, rarely reviewed",
         "Reviewed annually", "Reviewed quarterly",
         "Quarterly reviews drive operational plans")),
    NRAQuestion("S2", "S", 2, "Succession clarity for the top 5 roles.",
        ("Not discussed", "Discussed informally", "Named successors",
         "Named + development plan", "Successors tested in rotations")),
    NRAQuestion("S3", "S", 3, "Board / advisory governance cadence.",
        ("No governance", "Family-only meetings", "Advisory board",
         "Advisory + minutes", "Independent directors + charters")),
    NRAQuestion("S4", "S", 4, "Capital-allocation discipline on capex > INR 25L.",
        ("No formal review", "CFO sign-off only", "ROI memo required",
         "ROI + post-mortem", "Portfolio-level tracking + stage gates")),
    NRAQuestion("S5", "S", 5, "Leadership team diversity of experience.",
        ("Single-firm careers", "Two prior firms", "Diverse industries",
         "Diverse + external hires", "Deliberately diverse + mentorship")),
    NRAQuestion("S6", "S", 6, "Strategic KPI visibility across functions.",
        ("Owner-only", "CFO + COO", "Function heads",
         "All managers", "Every employee sees role-linked KPIs")),
    NRAQuestion("S7", "S", 7, "Response speed to sector disruption events.",
        ("Reactive, delayed", "Reactive within weeks", "Proactive scanning",
         "Proactive + playbooks", "Pre-rehearsed scenarios quarterly")),
    NRAQuestion("S8", "S", 8, "Explicit risk register with owners.",
        ("No register", "Informal list", "Register exists",
         "Register + owners", "Register + owners + quarterly stress-tests")),

    # ---- O — Operations & Supply Chain ----
    NRAQuestion("O1", "O", 1, "Documented SOPs for top-5 processes.",
        ("None", "Tribal knowledge", "Partial SOPs",
         "Complete SOPs", "SOPs audited quarterly")),
    NRAQuestion("O2", "O", 2, "Shop-floor / service-delivery KPI visibility.",
        ("No KPIs", "Daily tally", "Weekly dashboard",
         "Real-time board", "Real-time + tier-meetings")),
    NRAQuestion("O3", "O", 3, "Vendor concentration and negotiated terms.",
        (">70% from one vendor", "50-70% concentration",
         "Diversified, spot terms", "Diversified + annual contracts",
         "Strategic + joint planning")),
    NRAQuestion("O4", "O", 4, "Inventory turnover vs sector median.",
        ("Well below median", "Below median", "At median",
         "Above median", "Well above median")),
    NRAQuestion("O5", "O", 5, "On-time-in-full (OTIF) tracking.",
        ("Not tracked", "Monthly aggregate", "Weekly aggregate",
         "Daily by SKU", "Real-time customer-visible")),
    NRAQuestion("O6", "O", 6, "Quality rejection rate trajectory.",
        ("Rising or unknown", "Flat", "Gradually improving",
         "Below sector median", "Best-in-class + root-cause culture")),
    NRAQuestion("O7", "O", 7, "Working-capital days cash-cycle.",
        ("> sector + 30%", "> sector", "At sector",
         "< sector", "< sector - 20%")),
    NRAQuestion("O8", "O", 8, "Continuous-improvement (Kaizen / Lean) cadence.",
        ("None", "Ad-hoc projects", "Quarterly waves",
         "Monthly waves", "Daily at tier-1 boards")),

    # ---- SM — Sales & Marketing ----
    NRAQuestion("SM1", "SM", 1, "Named accounts + share-of-wallet tracked.",
        ("Not tracked", "Top-5 only", "Top-20",
         "All accounts, monthly", "All accounts + expansion plays")),
    NRAQuestion("SM2", "SM", 2, "Customer acquisition cost (CAC) by channel.",
        ("Not measured", "Blended only", "By channel",
         "By channel + LTV", "By cohort + payback")),
    NRAQuestion("SM3", "SM", 3, "Pricing discipline and uplift capture.",
        ("List-price only", "Annual reviews", "Quarterly reviews",
         "SKU-level reviews", "Dynamic + willingness-to-pay data")),
    NRAQuestion("SM4", "SM", 4, "Digital channel contribution to pipeline.",
        ("0%", "< 10%", "10-25%", "25-50%", "> 50%")),
    NRAQuestion("SM5", "SM", 5, "NPS or equivalent customer feedback loop.",
        ("Not collected", "Ad-hoc", "Quarterly",
         "Monthly + actioned", "Real-time + closed-loop")),
    NRAQuestion("SM6", "SM", 6, "Brand presence vs sector peers.",
        ("Invisible", "Local presence", "Sector recognised",
         "Sector thought-leader", "National thought-leader")),
    NRAQuestion("SM7", "SM", 7, "Export / new-geo revenue share.",
        ("0%", "< 5%", "5-15%", "15-30%", "> 30%")),
    NRAQuestion("SM8", "SM", 8, "Sales enablement tooling maturity.",
        ("Spreadsheets", "Basic CRM", "CRM + reporting",
         "CRM + automation", "CRM + AI co-pilots")),

    # ---- T — Technology ----
    NRAQuestion("T1", "T", 1, "ERP deployment and data integrity.",
        ("No ERP", "ERP, inconsistent data", "ERP, clean data",
         "ERP + MES/CRM integrated", "Full data spine across functions")),
    NRAQuestion("T2", "T", 2, "Cloud / hybrid infrastructure posture.",
        ("On-prem only", "Partial cloud", "Cloud-first new workloads",
         "Hybrid strategy", "Cloud-native + multi-region")),
    NRAQuestion("T3", "T", 3, "Cybersecurity + DR maturity.",
        ("None", "Basic antivirus", "Firewall + backups",
         "Formal policy + drills", "ISO 27001 or equivalent")),
    NRAQuestion("T4", "T", 4, "Data-driven decisions in ops reviews.",
        ("Gut-feel", "Some reports", "Dashboards used",
         "Data-first culture", "ML-augmented decisions")),
    NRAQuestion("T5", "T", 5, "Automation of repetitive tasks.",
        ("All manual", "Partial automation", "Workflow tooling",
         "RPA in place", "AI agents in production")),
    NRAQuestion("T6", "T", 6, "Customer-facing digital experience.",
        ("No digital UX", "Static website", "Transactional portal",
         "App + analytics", "Personalised + AI-driven")),
    NRAQuestion("T7", "T", 7, "Engineering / IT team maturity.",
        ("Outsourced only", "Single admin", "Small in-house team",
         "Cross-functional squad", "Product-engineering org")),
    NRAQuestion("T8", "T", 8, "Tech-debt discipline + refactoring budget.",
        ("Ignored", "Recognised, unresourced", "Budgeted",
         "Budgeted + tracked", "Allocated % of run-rate spend")),

    # ---- SK — Skills & Capabilities ----
    NRAQuestion("SK1", "SK", 1, "Role clarity + JD coverage for key roles.",
        ("None", "Informal", "JDs exist", "JDs + KPIs",
         "JDs + KPIs + development plans")),
    NRAQuestion("SK2", "SK", 2, "Learning & development spend per head.",
        ("Zero", "< 0.5% of payroll", "0.5-1%",
         "1-2%", "> 2% + programmes")),
    NRAQuestion("SK3", "SK", 3, "Leadership pipeline depth.",
        ("No bench", "One layer of successors",
         "Two layers", "Three layers", "Identified + assessed + rotated")),
    NRAQuestion("SK4", "SK", 4, "Attrition vs sector benchmark.",
        ("> sector + 10pp", "> sector", "At sector",
         "< sector", "< sector - 10pp")),
    NRAQuestion("SK5", "SK", 5, "Reskilling programme for digital tools.",
        ("None", "Ad-hoc", "Annual cohort",
         "Quarterly cohorts", "Continuous + certification")),
    NRAQuestion("SK6", "SK", 6, "Diversity (gender / background) at senior level.",
        ("Homogeneous", "Tokenism", "Some diversity",
         "Deliberate diversity", "Above-sector diversity")),
    NRAQuestion("SK7", "SK", 7, "Performance management cadence + quality.",
        ("Annual only", "Bi-annual", "Quarterly",
         "Quarterly + calibration", "Continuous + development focus")),
    NRAQuestion("SK8", "SK", 8, "Ability to hire senior talent from outside.",
        ("Cannot attract", "Struggles, rare hires",
         "Occasional hires", "Regular hires", "Strong employer brand")),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def questions_for_dimension(dimension: str) -> tuple[NRAQuestion, ...]:
    return tuple(q for q in QUESTIONS if q.dimension == dimension)


def assert_catalogue_integrity() -> None:
    """Invariant: exactly 8 questions per dimension × 5 dimensions = 40."""
    assert len(QUESTIONS) == len(DIMENSION_CODES) * QUESTIONS_PER_DIMENSION
    for dim in DIMENSION_CODES:
        rows = questions_for_dimension(dim)
        assert len(rows) == QUESTIONS_PER_DIMENSION, (
            f"Dimension {dim} has {len(rows)} questions, expected "
            f"{QUESTIONS_PER_DIMENSION}"
        )
        assert [r.order for r in rows] == list(range(1, QUESTIONS_PER_DIMENSION + 1))


# Fail-fast integrity check at import time.
assert_catalogue_integrity()
