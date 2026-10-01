"""Explain exactly what evidence an UNVERIFIABLE claim is missing.

UNVERIFIABLE is an honesty state, not a bare failure: the record says the claim could not be
verified, and this layer says what would verify it. ``explain_claim`` is pure and derives from
``verdict_for`` itself, so an explanation exists exactly when the verdict is UNVERIFIABLE and can
never disagree with it. Each explanation names one missing-evidence class and a one-line concrete
next action.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from crucible.claim import Claim
from crucible.thesis import Thesis
from crucible.verdict import UNVERIFIABLE, Measurement, _trusted, verdict_for

FALSIFICATION_CONDITION = "falsification_condition"
MEASUREMENT = "measurement"
CLAIM_BINDING = "claim_binding"
TRUSTED_DEVIATION = "trusted_deviation"
POSITIVE_TOLERANCE = "positive_tolerance"

MISSING_CLASSES = (
    FALSIFICATION_CONDITION,
    MEASUREMENT,
    CLAIM_BINDING,
    TRUSTED_DEVIATION,
    POSITIVE_TOLERANCE,
)


@dataclass(frozen=True, slots=True)
class Explanation:
    """One UNVERIFIABLE claim's evidence request: which class of evidence is ``missing``
    (one of ``MISSING_CLASSES``) and the concrete next action (``needed``) that would supply it."""

    claim_id: str
    missing: str
    needed: str


def _missing_class(claim: Claim, measurement: Measurement | None) -> str:
    """Which rung of ``verdict_for``'s honesty ladder failed. Mirrors the ladder rung by rung, so
    the named class is the first (and binding) reason the claim reads UNVERIFIABLE."""
    if not claim.falsification:
        return FALSIFICATION_CONDITION
    if measurement is None:
        return MEASUREMENT
    if measurement.claim_sha256 != claim.sha256:
        return CLAIM_BINDING
    if _trusted(measurement.deviation) is None:
        return TRUSTED_DEVIATION
    return POSITIVE_TOLERANCE


def _needed(missing: str, claim: Claim) -> str:
    """The one-line concrete next action that would supply the missing evidence class."""
    if missing == FALSIFICATION_CONDITION:
        return f"state the observation that would refute claim {claim.id}, then re-register the thesis"
    if missing == MEASUREMENT:
        return f"provide a measurement row binding claim {claim.id} by sha256 {claim.sha256}"
    if missing == CLAIM_BINDING:
        return f"rebind the measurement to claim {claim.id}: its claim_sha256 must be {claim.sha256}"
    if missing == TRUSTED_DEVIATION:
        return f"record a finite, non-negative numeric deviation for claim {claim.id}"
    return f"set a finite tolerance greater than zero for claim {claim.id}"


def explain_claim(claim: Claim, measurement: Measurement | None) -> Explanation | None:
    """The evidence request for one claim, or None when the claim verifies (MATCH or DRIFT).

    PURE, and gated on ``verdict_for`` itself: an explanation is emitted exactly when the verdict
    is UNVERIFIABLE, so the explain layer cannot drift from the verdict spine.
    """
    if verdict_for(claim, measurement).status != UNVERIFIABLE:
        return None
    missing = _missing_class(claim, measurement)
    return Explanation(claim.id, missing, _needed(missing, claim))


def _index(measurements: Mapping[str, Measurement] | Iterable[Measurement] | None) -> dict:
    if measurements is None:
        return {}
    if isinstance(measurements, Mapping):
        return dict(measurements)
    return {m.claim_id: m for m in measurements}


def explain_thesis(
    thesis: Thesis,
    measurements: Mapping[str, Measurement] | Iterable[Measurement] | None = None,
) -> tuple[Explanation, ...]:
    """Evidence requests for every UNVERIFIABLE claim in a thesis, in thesis claim order.

    ``measurements`` takes the same shapes as ``assess``: a mapping keyed by claim id, or an
    iterable of Measurements keyed by their ``claim_id``. Verifiable claims yield nothing.
    """
    by_id = _index(measurements)
    out = (explain_claim(c, by_id.get(c.id)) for c in thesis.claims)
    return tuple(e for e in out if e is not None)


def explanation_row(explanation: Explanation) -> dict:
    """The JSON row for one explanation: ``{claim_id, missing, needed}``."""
    return {
        "claim_id": explanation.claim_id,
        "missing": explanation.missing,
        "needed": explanation.needed,
    }
