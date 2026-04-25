"""Partner service — cohort benchmarks, distributions, scheme registry.

Rule: benchmark exposure requires n >= PEER_BENCHMARK_MIN_COHORT
(default 20). When n < 20, is_exposed is False and numeric fields are
zeroed / masked so no individual firm's signal can leak.
"""
from __future__ import annotations

from collections import Counter
from statistics import median

from flask import current_app

from app.extensions import db
from app.models.assessment import AssessmentRun, AssessmentStage
from app.models.assessment import Score
from app.models.firm import Firm
from app.models.reference import Sector

DIMENSION_CODES = ("S", "O", "SM", "T", "SK")
BANDS = ("Legacy", "Siloed", "Strategic", "Future-Ready")


# ---------------------------------------------------------------------------
# Cohort medians
# ---------------------------------------------------------------------------

def cohort_benchmark(sector_code: str, tenant_id: str) -> dict:
    """Compute the sector cohort benchmark for a partner view."""
    min_n = current_app.config.get("PEER_BENCHMARK_MIN_COHORT", 20)
    sector = Sector.query.filter_by(code=sector_code).first()
    if not sector:
        return _masked(sector_code, 0, min_n, "median")

    runs = _completed_runs_for(sector)
    n = len(runs)
    if n < min_n:
        return _masked(sector_code, n, min_n, "median")

    composites = [r.composite_score for r in runs]
    median_composite = int(median(composites))

    dim_medians: dict[str, int] = {}
    for code in DIMENSION_CODES:
        values = (db.session.query(Score.value)
                  .join(AssessmentRun, Score.assessment_id == AssessmentRun.id)
                  .join(Firm, AssessmentRun.firm_id == Firm.id)
                  .filter(Firm.sector_id == sector.id)
                  .filter(Score.dimension_code == code)
                  .all())
        flat = [v[0] for v in values if v[0] is not None]
        dim_medians[code] = int(median(flat)) if flat else 0

    return {
        "sector_code": sector_code,
        "n_firms": n,
        "median_composite": median_composite,
        "median_by_dimension": dim_medians,
        "scheme_uptake": {"note": "scheme-uptake join deferred to v5.1"},
        "is_exposed": True,
    }


# ---------------------------------------------------------------------------
# Cohort distribution across bands
# ---------------------------------------------------------------------------

def cohort_distribution(sector_code: str, tenant_id: str) -> dict:
    """Return the distribution of firms across the 4 bands for a sector."""
    min_n = current_app.config.get("PEER_BENCHMARK_MIN_COHORT", 20)
    sector = Sector.query.filter_by(code=sector_code).first()
    if not sector:
        return _masked_distribution(sector_code, 0)

    runs = _completed_runs_for(sector)
    n = len(runs)
    if n < min_n:
        return _masked_distribution(sector_code, n)

    counts = Counter(r.band for r in runs if r.band)
    distribution = []
    for band in BANDS:
        c = counts.get(band, 0)
        distribution.append({
            "band": band,
            "n_firms": c,
            "pct": round(c / n * 100, 1) if n else 0.0,
        })
    return {
        "sector_code": sector_code,
        "n_firms": n,
        "is_exposed": True,
        "distribution": distribution,
    }


# ---------------------------------------------------------------------------
# Scheme registry — stub in v5.0
# ---------------------------------------------------------------------------

_SCHEMES = [
    {
        "scheme_code": "pli",
        "scheme_name": "Production Linked Incentive (PLI)",
        "ministry": "Ministry of Commerce & Industry",
        "applicable_sectors": ["manufacturing", "automotive", "pharma", "textile"],
        "applicable_size_bands": ["small", "mid", "upper_mid"],
        "deadline": "2027-03-31",
        "summary": "Outcome-linked incentive on incremental Indian manufacturing turnover.",
        "evidence_tier": "L0b",
    },
    {
        "scheme_code": "eclgs",
        "scheme_name": "Emergency Credit Line Guarantee Scheme 2.0",
        "ministry": "Ministry of Finance / NCGTC",
        "applicable_sectors": ["manufacturing", "textile", "agro", "services"],
        "applicable_size_bands": ["micro", "small", "mid", "upper_mid"],
        "deadline": "2026-09-30",
        "summary": "Collateral-free working-capital line up to ₹500 Cr.",
        "evidence_tier": "L0b",
    },
    {
        "scheme_code": "msme_champions",
        "scheme_name": "MSME Champions Scheme",
        "ministry": "Ministry of MSME",
        "applicable_sectors": ["manufacturing", "textile", "pharma", "agro"],
        "applicable_size_bands": ["micro", "small", "mid"],
        "deadline": None,
        "summary": "Quality, lean, and zero-defect support for MSME competitiveness.",
        "evidence_tier": "L0b",
    },
    {
        "scheme_code": "tex_pli",
        "scheme_name": "PLI for Textiles (MMF & Technical Textiles)",
        "ministry": "Ministry of Textiles",
        "applicable_sectors": ["textile"],
        "applicable_size_bands": ["mid", "upper_mid"],
        "deadline": "2026-12-31",
        "summary": "Capex-linked incentive for MMF apparel and technical textiles.",
        "evidence_tier": "L0b",
    },
]


def list_schemes() -> list[dict]:
    """Stub registry — replace with feed in v5.1."""
    return list(_SCHEMES)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _completed_runs_for(sector: Sector):
    return (db.session.query(AssessmentRun)
            .join(Firm, AssessmentRun.firm_id == Firm.id)
            .filter(Firm.sector_id == sector.id)
            .filter(AssessmentRun.stage == AssessmentStage.NRA)
            .filter(AssessmentRun.composite_score.isnot(None))
            .all())


def _masked(sector_code: str, n: int, min_n: int, mode: str) -> dict:
    return {
        "sector_code": sector_code,
        "n_firms": n,
        "median_composite": 0,
        "median_by_dimension": {},
        "scheme_uptake": {
            "note": f"Cohort size {n} below PII threshold {min_n}. Suppressed."
        },
        "is_exposed": False,
    }


def _masked_distribution(sector_code: str, n: int) -> dict:
    return {
        "sector_code": sector_code,
        "n_firms": n,
        "is_exposed": False,
        "distribution": [{"band": b, "n_firms": 0, "pct": 0.0} for b in BANDS],
    }
