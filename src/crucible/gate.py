"""Publication gate for thesis export.

crucible can assess fenced research locally, but public export is default-deny for anything labelled
or marked as fenced. The gate is deliberately mechanical: it trusts the sealed thesis disposition and
also scans title, claim text, and falsification fields for explicit restricted markers.
"""
from __future__ import annotations

from crucible.thesis import FENCED, PUBLISHABLE, Thesis

_FENCED_MARKERS = (
    "[fenced]",
    "[restricted]",
    "publication-gate: fenced",
    "publication-gate:fenced",
)


def _has_fenced_marker(text: str) -> bool:
    low = text.lower()
    return any(marker in low for marker in _FENCED_MARKERS)


def gate_check(thesis: Thesis) -> str:
    """Return publishable or fenced. Explicit fenced disposition wins; visible fenced/restricted
    markers in title, claim text, or falsification fail closed to fenced."""
    if thesis.disposition == FENCED:
        return FENCED
    if _has_fenced_marker(thesis.title):
        return FENCED
    for claim in thesis.claims:
        if _has_fenced_marker(claim.text) or _has_fenced_marker(claim.falsification):
            return FENCED
    return PUBLISHABLE


def export_guard(thesis: Thesis) -> None:
    """Raise if a thesis is not safe for public export."""
    if gate_check(thesis) != PUBLISHABLE:
        raise PermissionError("thesis is fenced and cannot be exported")


def export_thesis(thesis: Thesis) -> dict:
    """Return the public thesis contract after applying the publication gate.

    Runtime metadata such as registration time is intentionally omitted. The export carries the
    content-bound claim receipts and thesis seal a downstream reader needs to re-check integrity.
    """
    export_guard(thesis)
    return {
        "id": thesis.id,
        "title": thesis.title,
        "disposition": thesis.disposition,
        "seal": thesis.seal,
        "claims": [
            {
                "id": c.id,
                "text": c.text,
                "falsification": c.falsification,
                "sha256": c.sha256,
            }
            for c in thesis.claims
        ],
    }
