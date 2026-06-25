"""The verdict ladder: pure, grounded, fail-closed. MATCH / DRIFT / UNVERIFIABLE."""
from __future__ import annotations

import math

from crucible.claim import make_claim
from crucible.verdict import DRIFT, MATCH, UNVERIFIABLE, Measurement, verdict_for


def _claim():
    return make_claim("the constant is 12.526", "a measurement outside 12.526 plus or minus 0.1")


def _m(claim, deviation, tolerance=0.1, method="oracle"):
    return Measurement(claim.id, claim.sha256, deviation, tolerance, method, 0.0)


def test_match_when_within_tolerance():
    c = _claim()
    v = verdict_for(c, _m(c, 0.05))
    assert v.status == MATCH
    assert v.margin is not None and v.margin > 0
    assert v.claim_sha256 == c.sha256


def test_match_at_the_exact_boundary():
    c = _claim()
    v = verdict_for(c, _m(c, 0.1))  # deviation equals tolerance: margin 0, still MATCH
    assert v.status == MATCH and v.margin == 0.0


def test_drift_when_outside_tolerance():
    c = _claim()
    v = verdict_for(c, _m(c, 0.5))
    assert v.status == DRIFT
    assert v.margin is not None and v.margin < 0


def test_unverifiable_with_no_measurement():
    c = _claim()
    v = verdict_for(c, None)
    assert v.status == UNVERIFIABLE and v.margin is None


def test_unverifiable_when_claim_has_no_falsification():
    c = make_claim("consciousness is fundamental")  # no falsification condition
    v = verdict_for(c, _m(c, 0.0))  # even with a measurement, nothing would settle it
    assert v.status == UNVERIFIABLE
    assert "falsification" in v.grounds


def test_unverifiable_fail_closed_on_bad_deviation():
    c = _claim()
    for bad in (None, -1.0, float("nan"), float("inf")):
        assert verdict_for(c, _m(c, bad)).status == UNVERIFIABLE


def test_unverifiable_on_non_positive_tolerance():
    c = _claim()
    assert verdict_for(c, _m(c, 0.05, tolerance=0.0)).status == UNVERIFIABLE
    assert verdict_for(c, _m(c, 0.05, tolerance=-1.0)).status == UNVERIFIABLE


def test_unverifiable_when_measurement_binds_to_a_different_claim():
    c = _claim()
    other = make_claim("a different claim", "its own refutation")
    stale = Measurement(c.id, other.sha256, 0.0, 0.1, "oracle", 0.0)
    v = verdict_for(c, stale)
    assert v.status == UNVERIFIABLE and "bind" in v.grounds


def test_non_numeric_deviation_is_unverifiable_not_a_crash():
    c = _claim()
    bogus = Measurement(c.id, c.sha256, "not a number", 0.1, "oracle", 0.0)  # type: ignore[arg-type]
    v = verdict_for(c, bogus)
    assert v.status == UNVERIFIABLE


def test_margin_formula():
    c = _claim()
    v = verdict_for(c, _m(c, 0.02, tolerance=0.1))
    assert math.isclose(v.margin, (0.1 - 0.02) / 0.1)
