from __future__ import annotations

from crucible.assess import assess
from crucible.claim import make_claim
from crucible.drift import drift_track
from crucible.thesis import make_thesis
from crucible.verdict import Measurement


def _thesis():
    claims = (
        make_claim("stable claim", "stable counterexample"),
        make_claim("improving claim", "improving counterexample"),
        make_claim("regressing claim", "regressing counterexample"),
        make_claim("unmeasured claim", "unmeasured counterexample"),
    )
    return make_thesis("drift thesis", claims, clock=lambda: 1.0)


def _measurement(claim, deviation):
    return Measurement(claim.id, claim.sha256, deviation, 1.0, "oracle", 10.0)


def test_drift_track_classifies_held_improved_regressed_and_moved():
    thesis = _thesis()
    c0, c1, c2, c3 = thesis.claims
    previous, _ = assess(
        thesis,
        [
            _measurement(c0, 0.25),
            _measurement(c1, 0.75),
            _measurement(c2, 0.10),
        ],
        clock=lambda: 100.0,
    )
    current, _ = assess(
        thesis,
        [
            _measurement(c0, 0.25),
            _measurement(c1, 0.20),
            _measurement(c2, 1.50),
            _measurement(c3, 0.00),
        ],
        clock=lambda: 200.0,
    )

    report = drift_track(previous, current)

    assert report.summary == {"held": 1, "moved": 1, "improved": 1, "regressed": 1}
    by_claim = {row.claim_id: row for row in report.rows}
    assert by_claim[c0.id].status == "held"
    assert by_claim[c1.id].status == "improved"
    assert by_claim[c1.id].margin_delta == 0.55
    assert by_claim[c2.id].status == "regressed"
    assert by_claim[c3.id].status == "moved"
    assert by_claim[c3.id].previous_status == "UNVERIFIABLE"
    assert by_claim[c3.id].current_status == "MATCH"


def test_drift_track_marks_unrankable_status_changes_as_moved():
    thesis = _thesis()
    c0 = thesis.claims[0]
    previous, _ = assess(thesis, [], clock=lambda: 100.0)
    current, _ = assess(thesis, [_measurement(c0, 0.0)], clock=lambda: 200.0)

    report = drift_track(previous, current)

    row = next(r for r in report.rows if r.claim_id == c0.id)
    assert row.status == "moved"
    assert row.previous_status == "UNVERIFIABLE"
    assert row.current_status == "MATCH"
    assert row.margin_delta is None


def test_drift_track_rejects_different_theses():
    previous_thesis = _thesis()
    current_thesis = make_thesis(
        "other thesis",
        (make_claim("other claim", "other counterexample"),),
        clock=lambda: 2.0,
    )
    previous, _ = assess(previous_thesis, [], clock=lambda: 100.0)
    current, _ = assess(current_thesis, [], clock=lambda: 200.0)

    import pytest

    with pytest.raises(ValueError, match="same thesis"):
        drift_track(previous, current)
