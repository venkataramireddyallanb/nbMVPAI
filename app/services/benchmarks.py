"""DDExpert v3.1 Benchmark Family — Table 5.

Every promotion (rule → model → LLM → agent) must clear the named
benchmark gate before shipping. The catalogue here is the spec's
Table 5 in code form so the Architecture page and CI checks can
both reference it.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Benchmark:
    output_type: str
    benchmark_kind: str
    target_bar: str
    promotion_gate_for: str


CATALOGUE: tuple[Benchmark, ...] = (
    Benchmark(
        output_type="Readiness Score",
        benchmark_kind="Forecast-to-realised correlation",
        target_bar="R² > 0.60 with documented error bars",
        promotion_gate_for="Readiness Score API launch",
    ),
    Benchmark(
        output_type="Initiative Shortlist",
        benchmark_kind="Precision-at-3 vs expert-adjudicated",
        target_bar="≥ 0.75",
        promotion_gate_for="DRG Recommendation Engine launch",
    ),
    Benchmark(
        output_type="Project Charter",
        benchmark_kind="Ship-as-is blind rubric",
        target_bar="≥ 85%",
        promotion_gate_for="Strategy & Roadmap wave GA",
    ),
    Benchmark(
        output_type="Proposal Draft",
        benchmark_kind="Ship-as-is blind rubric",
        target_bar="≥ 85%",
        promotion_gate_for="LLM-assisted proposal drafter launch",
    ),
    Benchmark(
        output_type="CFO Board Note / ROIC Narrative",
        benchmark_kind="Ship-as-is + factual-accuracy check",
        target_bar="≥ 85% ship-as-is, 0 factual error",
        promotion_gate_for="Finance Agent LLM promotion",
    ),
    Benchmark(
        output_type="Compliance Output (vertical agents)",
        benchmark_kind="Error rate against regulator format",
        target_bar="< 1% error, 100% human-approved",
        promotion_gate_for="Vertical-agent GA",
    ),
    Benchmark(
        output_type="Continuous Copilot Answer",
        benchmark_kind="Groundedness + citation accuracy",
        target_bar="≥ 95% cited, citations verified",
        promotion_gate_for="Continuous Copilot launch",
    ),
)
