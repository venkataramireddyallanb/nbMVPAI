"""L-pill citation helpers.

Spec Acceptance Criterion #4: "No unpilled text passes CI." Every narrative
paragraph produced by the Narrator / Drafter agents must end with at least
one citation in the form ``[L0a]`` / ``[L0b]`` / ``[L1]`` / ``[L2]`` /
``[L3]`` / ``[L4]``. The CI step runs ``has_pill_citation()`` on every
paragraph of generated prose; any failure blocks the build.
"""
from __future__ import annotations

import re

PILL_RE = re.compile(r"\[L(?:0a|0b|[1-4])\]")


def has_pill_citation(paragraph: str) -> bool:
    """Return True if the paragraph contains ≥1 L-pill citation."""
    return bool(PILL_RE.search(paragraph))


def assert_all_paragraphs_cited(text: str) -> None:
    """Raise AssertionError on the first unpilled paragraph."""
    for i, para in enumerate(p.strip() for p in text.split("\n\n") if p.strip()):
        if not has_pill_citation(para):
            raise AssertionError(
                f"Paragraph #{i + 1} is missing an L-pill citation: "
                f"{para[:120]}..."
            )
