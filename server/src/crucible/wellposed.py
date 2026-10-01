"""Pre-assessment validation: typed, non-fatal warnings for ill-posed measurement rows.

A measurement row can be well-formed JSON and still be ill-posed: a tolerance that cannot separate
holding from breaking, a deviation no verdict can trust, a boolean that would silently coerce, a
row bound to no claim, or two rows fighting over one claim. ``verdict_for`` already fails closed on
these (UNVERIFIABLE), but silently. This pass names each problem BEFORE assessment runs, as data,
so an operator fixes the measurement file instead of discovering a bare verdict. Warnings never
change a verdict; structurally malformed files stay the loader's fatal domain.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from crucible.thesis import Thesis

NON_POSITIVE_TOLERANCE = "non_positive_tolerance"
UNTRUSTED_DEVIATION = "untrusted_deviation"
BOOLEAN_VALUE = "boolean_value"
UNBOUND_CLAIM = "unbound_claim"
DUPLICATE_CLAIM_BINDING = "duplicate_claim_binding"

WARNING_CODES = (
    NON_POSITIVE_TOLERANCE,
    UNTRUSTED_DEVIATION,
    BOOLEAN_VALUE,
    UNBOUND_CLAIM,
    DUPLICATE_CLAIM_BINDING,
)


@dataclass(frozen=True, slots=True)
class MeasurementWarning:
    """One ill-posed measurement row finding: the 1-based ``row``, the raw ``claim`` reference as
    written, a typed ``code`` (one of ``WARNING_CODES``), and a one-line ``detail``."""

    row: int
    claim: str
    code: str
    detail: str


def measurement_warnings(thesis: Thesis, data: Mapping) -> tuple[MeasurementWarning, ...]:
    """Validate raw measurement rows (parsed measurements JSON) against a thesis. PURE.

    Returns typed warnings in row order; a well-posed file returns ``()``. Rows or files that are
    not the documented shape are skipped here, because the measurement loader already rejects them
    with a fatal, specific error.
    """
    rows = data.get("measurements")
    if not isinstance(rows, list):
        return ()
    warnings: list[MeasurementWarning] = []
    seen: set[str] = set()
    for index, row in enumerate(rows, 1):
        if isinstance(row, Mapping):
            warnings.extend(_row_warnings(thesis, index, row, seen))
    return tuple(warnings)


def _row_warnings(thesis: Thesis, index: int, row: Mapping, seen: set[str]) -> list[MeasurementWarning]:
    ref = row.get("claim", "")
    out = _binding_warnings(thesis, index, ref, seen)
    out.extend(_deviation_warnings(index, ref, row.get("deviation")))
    out.extend(_tolerance_warnings(index, ref, row.get("tolerance")))
    return out


def _binding_warnings(thesis: Thesis, index: int, ref: object, seen: set[str]) -> list[MeasurementWarning]:
    matches = [c for c in thesis.claims if c.id == ref]
    if not matches:
        matches = [c for c in thesis.claims if c.text == ref]
    if not matches:
        detail = "binds to no claim in the thesis"
        return [MeasurementWarning(index, str(ref), UNBOUND_CLAIM, detail)]
    if len(matches) > 1:
        detail = "references ambiguous claim text; bind by claim id"
        return [MeasurementWarning(index, str(ref), UNBOUND_CLAIM, detail)]
    claim_id = matches[0].id
    if claim_id in seen:
        detail = f"claim {claim_id} already has a measurement row; the later row replaces the earlier"
        return [MeasurementWarning(index, str(ref), DUPLICATE_CLAIM_BINDING, detail)]
    seen.add(claim_id)
    return []


def _deviation_warnings(index: int, ref: object, value: object) -> list[MeasurementWarning]:
    if value is None:
        return []  # honestly unmeasured: UNVERIFIABLE with a clean explanation, not ill-posed
    problem = _numeric_problem("deviation", value, minimum_exclusive=False)
    if problem is None:
        return []
    code, detail = problem
    return [MeasurementWarning(index, str(ref), code, detail)]


def _tolerance_warnings(index: int, ref: object, value: object) -> list[MeasurementWarning]:
    if value is None:
        detail = "tolerance is missing; it reads as 0.0 and the verdict is UNVERIFIABLE"
        return [MeasurementWarning(index, str(ref), NON_POSITIVE_TOLERANCE, detail)]
    problem = _numeric_problem("tolerance", value, minimum_exclusive=True)
    if problem is None:
        return []
    code, detail = problem
    return [MeasurementWarning(index, str(ref), code, detail)]


def _numeric_problem(field: str, value: object, *, minimum_exclusive: bool) -> tuple[str, str] | None:
    """The (code, detail) for one ill-posed numeric field, or None when the value is trusted.
    ``minimum_exclusive`` demands strictly positive (tolerance); otherwise non-negative (deviation)."""
    bad = NON_POSITIVE_TOLERANCE if minimum_exclusive else UNTRUSTED_DEVIATION
    if isinstance(value, bool):
        return BOOLEAN_VALUE, f"{field} {value!r} is a boolean and would silently read as {float(value):g}"
    if not isinstance(value, (int, float)):
        return bad, f"{field} {value!r} is not a number"
    number = float(value)
    if not math.isfinite(number):
        return bad, f"{field} {number:g} is not finite"
    if number < 0 or (minimum_exclusive and number == 0):
        floor = "greater than zero" if minimum_exclusive else "non-negative"
        return bad, f"{field} {number:g} must be {floor}"
    return None


def warning_row(warning: MeasurementWarning) -> dict:
    """The JSON row for one warning: ``{row, claim, code, detail}``."""
    return {
        "row": warning.row,
        "claim": warning.claim,
        "code": warning.code,
        "detail": warning.detail,
    }
