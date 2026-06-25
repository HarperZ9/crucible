"""The measure seam: a sound oracle over a substrate decides the claim; verdict_for turns it into
MATCH / DRIFT / UNVERIFIABLE. The Null default measures nothing; the table oracle is fail-closed."""
from __future__ import annotations

import pytest

from crucible.claim import make_claim
from crucible.measure import MetricSpec, NullMeasure, TableMeasure, measure_thesis
from crucible.thesis import make_thesis
from crucible.verdict import DRIFT, MATCH, UNVERIFIABLE, verdict_for

CLOCK = lambda: 1000.0  # noqa: E731


def test_metric_spec_rejects_an_unknown_metric():
    # An unknown metric is a misconfiguration; it must not silently compute absolute difference.
    with pytest.raises(ValueError, match="metric must be"):
        MetricSpec(1.0, 0.1, "x", metric="relative")
    MetricSpec(1.0, 0.1, "x", metric="abs")  # the valid ones do not raise
    MetricSpec(1.0, 0.1, "x", metric="rel")


def test_null_measure_produces_no_measurement():
    c = make_claim("c", "f")
    m = NullMeasure(clock=CLOCK).measure(c)
    assert m.deviation is None and m.method == "null"
    assert verdict_for(c, m).status == UNVERIFIABLE


def test_table_measure_abs_metric_decides_match_and_drift():
    holds = make_claim("x is 11", "x deviates from 11")
    breaks = make_claim("x is 3", "x deviates from 3")
    specs = {holds.id: MetricSpec(11.0, 0.5, "x"), breaks.id: MetricSpec(3.0, 0.5, "x")}
    tm = TableMeasure(specs, {"x": 11.0}, clock=CLOCK)
    mh, mb = tm.measure(holds), tm.measure(breaks)
    assert mh.deviation == 0.0 and verdict_for(holds, mh).status == MATCH
    assert mb.deviation == 8.0 and verdict_for(breaks, mb).status == DRIFT
    assert mh.method == "table" and mh.evidence  # the measurement carries its grounds


def test_table_measure_relative_metric():
    c = make_claim("ratio is 100", "ratio off by too much")
    tm = TableMeasure({c.id: MetricSpec(100.0, 0.05, "r", metric="rel")}, {"r": 102.0}, clock=CLOCK)
    m = tm.measure(c)
    assert abs(m.deviation - 0.02) < 1e-9  # |102 - 100| / 100
    assert verdict_for(c, m).status == MATCH  # 0.02 within the 0.05 tolerance


def test_table_measure_unknown_claim_or_missing_observation_is_unverifiable():
    c = make_claim("c", "f")
    assert TableMeasure({}, {"x": 1.0}, clock=CLOCK).measure(c).deviation is None
    tm = TableMeasure({c.id: MetricSpec(1.0, 0.1, "missing")}, {"x": 1.0}, clock=CLOCK)
    m = tm.measure(c)
    assert m.deviation is None and verdict_for(c, m).status == UNVERIFIABLE


def test_relative_metric_with_zero_prediction_is_unverifiable():
    c = make_claim("z is 0", "z is nonzero")
    tm = TableMeasure({c.id: MetricSpec(0.0, 0.1, "z", metric="rel")}, {"z": 1.0}, clock=CLOCK)
    assert tm.measure(c).deviation is None  # a relative metric is undefined at a zero prediction


def test_measure_thesis_runs_the_oracle_over_every_claim():
    holds = make_claim("a is 5", "a off")
    untested = make_claim("b is 9", "b off")  # no observation provided
    t = make_thesis("t", [holds, untested], clock=CLOCK)
    measurements = measure_thesis(TableMeasure({holds.id: MetricSpec(5.0, 0.5, "a")},
                                               {"a": 5.2}, clock=CLOCK), t)
    assert len(measurements) == 2
    statuses = [verdict_for(c, m).status for c, m in zip(t.claims, measurements)]
    assert statuses == [MATCH, UNVERIFIABLE]
