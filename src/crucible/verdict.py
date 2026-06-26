"""The verdict: a claim's standing, computed from a measurement, never asserted.

``verdict_for`` is the spine and the differentiator: a pure function with no model in it, so a
verdict recomputes from the stored record and a confident assertion has no effect on the rechecked
result. A measurement within tolerance is MATCH, outside is DRIFT, absent or unmeasurable is
UNVERIFIABLE. UNVERIFIABLE is fail-closed: an axis that cannot be measured is never read as holding.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from crucible.claim import Claim
from crucible.thesis import FENCED, PUBLISHABLE

MATCH = "MATCH"
DRIFT = "DRIFT"
UNVERIFIABLE = "UNVERIFIABLE"


@dataclass(frozen=True, slots=True)
class Measurement:
    """A measurement of a claim against a substrate: a deviation from what the claim predicts and the
    tolerance that separates holding from breaking. ``deviation`` None, non-finite, or negative reads
    as unmeasurable. ``evidence`` carries references or content hashes that ground the measurement."""

    claim_id: str
    claim_sha256: str
    deviation: float | None
    tolerance: float
    method: str
    measured_at: float
    evidence: tuple[str, ...] = ()
    recheck: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class Verdict:
    """A claim's standing: MATCH / DRIFT / UNVERIFIABLE, with the measurement it was computed from and
    a one-line grounds. The status recomputes from (deviation, tolerance), so inconsistent stored
    verdict rows are caught by recheck."""

    claim_id: str
    claim_sha256: str
    status: str
    deviation: float | None
    tolerance: float
    margin: float | None
    method: str
    grounds: str
    disposition: str = PUBLISHABLE


def _trusted(x: float | None) -> float | None:
    """Return x as a finite, non-negative float, or None if it cannot be trusted (None, a bool, a
    non-number, NaN, infinity, or negative). Booleans are rejected so True does not read as 1.0."""
    if x is None or isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    xf = float(x)
    return xf if math.isfinite(xf) and xf >= 0 else None


def _disposition(value: str) -> str:
    if value not in (PUBLISHABLE, FENCED):
        raise ValueError(f"disposition must be {PUBLISHABLE!r} or {FENCED!r}, got {value!r}")
    return value


def _unverifiable(
    cid: str,
    csha: str,
    deviation: float | None,
    tolerance: float,
    method: str,
    grounds: str,
    disposition: str,
) -> Verdict:
    return Verdict(cid, csha, UNVERIFIABLE, deviation, tolerance, None, method, grounds, disposition)


def verdict_for(claim: Claim, measurement: Measurement | None, *, disposition: str = PUBLISHABLE) -> Verdict:
    """Compute a claim's verdict from its measurement. PURE: no model, recomputable from the record.

    The order of the checks is the honesty ladder:
    1. A claim with no falsification condition states nothing testable: UNVERIFIABLE.
    2. No measurement, or one that binds to a different claim: UNVERIFIABLE.
    3. A deviation or tolerance that cannot be trusted (None, non-finite, negative, or a non-positive
       tolerance): UNVERIFIABLE, fail-closed.
    4. Otherwise margin = (tolerance - deviation) / tolerance: MATCH if within (margin >= 0), else DRIFT.
    """
    cid, csha = claim.id, claim.sha256
    disp = _disposition(disposition)
    if not claim.falsification:
        return _unverifiable(cid, csha, None, 0.0, "none", "claim states no falsification condition", disp)
    if measurement is None:
        return _unverifiable(cid, csha, None, 0.0, "none", "no measurement", disp)
    if measurement.claim_sha256 != csha:
        return _unverifiable(cid, csha, None, measurement.tolerance, measurement.method,
                             "measurement does not bind to this claim", disp)
    dev = _trusted(measurement.deviation)
    tol = _trusted(measurement.tolerance)
    if dev is None or tol is None or tol <= 0:
        return _unverifiable(cid, csha, dev, tol if tol is not None else 0.0, measurement.method,
                             "deviation or tolerance not measurable", disp)
    margin = (tol - dev) / tol
    if margin >= 0.0:
        return Verdict(cid, csha, MATCH, dev, tol, margin, measurement.method,
                       f"deviation {dev:g} within tolerance {tol:g}", disp)
    return Verdict(cid, csha, DRIFT, dev, tol, margin, measurement.method,
                   f"deviation {dev:g} exceeds tolerance {tol:g}", disp)
