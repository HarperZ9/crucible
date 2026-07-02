"""The explain layer: every UNVERIFIABLE verdict names the exact evidence class it is missing and a
concrete next action, and a verifiable claim gets no explanation at all. The explanation derives
from the same pure ladder as ``verdict_for``, so it can never disagree with the verdict."""
from __future__ import annotations

import pytest

from crucible.claim import make_claim
from crucible.explain import (
    CLAIM_BINDING,
    FALSIFICATION_CONDITION,
    MEASUREMENT,
    MISSING_CLASSES,
    POSITIVE_TOLERANCE,
    TRUSTED_DEVIATION,
    explain_claim,
    explain_thesis,
    explanation_row,
)
from crucible.thesis import make_thesis
from crucible.verdict import UNVERIFIABLE, Measurement, verdict_for

CLOCK = lambda: 1000.0  # noqa: E731
SHA_OTHER = "a" * 64


def _claim():
    return make_claim("latency holds", "latency exceeds budget")


def _measured(claim, *, deviation=0.0, tolerance=0.1, sha=None):
    return Measurement(claim.id, sha or claim.sha256, deviation, tolerance, "bench", 42.0)


def test_missing_falsification_condition_is_named():
    claim = make_claim("an untestable claim", "")
    explanation = explain_claim(claim, _measured(claim))
    assert explanation is not None
    assert explanation.claim_id == claim.id
    assert explanation.missing == FALSIFICATION_CONDITION
    assert claim.id in explanation.needed


def test_missing_measurement_names_the_binding_sha():
    claim = _claim()
    explanation = explain_claim(claim, None)
    assert explanation.missing == MEASUREMENT
    assert claim.id in explanation.needed
    assert claim.sha256 in explanation.needed


def test_binding_mismatch_names_the_expected_sha():
    claim = _claim()
    explanation = explain_claim(claim, _measured(claim, sha=SHA_OTHER))
    assert explanation.missing == CLAIM_BINDING
    assert claim.sha256 in explanation.needed


@pytest.mark.parametrize("deviation", [-0.5, float("nan"), float("inf"), True, None])
def test_untrusted_deviation_is_named(deviation):
    claim = _claim()
    explanation = explain_claim(claim, _measured(claim, deviation=deviation))
    assert explanation.missing == TRUSTED_DEVIATION
    assert claim.id in explanation.needed


@pytest.mark.parametrize("tolerance", [0.0, -1.0, float("nan"), float("inf"), True])
def test_non_positive_tolerance_is_named(tolerance):
    claim = _claim()
    explanation = explain_claim(claim, _measured(claim, tolerance=tolerance))
    assert explanation.missing == POSITIVE_TOLERANCE
    assert claim.id in explanation.needed


def test_verifiable_claims_get_no_explanation():
    claim = _claim()
    assert explain_claim(claim, _measured(claim, deviation=0.0)) is None  # MATCH
    assert explain_claim(claim, _measured(claim, deviation=9.0)) is None  # DRIFT


def test_explanations_always_agree_with_the_verdict():
    claim = _claim()
    unfalsifiable = make_claim("untestable", "")
    cases = [
        (claim, _measured(claim, deviation=0.05)),
        (claim, _measured(claim, deviation=5.0)),
        (claim, None),
        (claim, _measured(claim, sha=SHA_OTHER)),
        (claim, _measured(claim, deviation=-1.0)),
        (claim, _measured(claim, tolerance=0.0)),
        (unfalsifiable, None),
        (unfalsifiable, _measured(unfalsifiable, deviation=0.0)),
    ]
    for c, m in cases:
        explanation = explain_claim(c, m)
        unverifiable = verdict_for(c, m).status == UNVERIFIABLE
        assert (explanation is not None) == unverifiable
        if explanation is not None:
            assert explanation.missing in MISSING_CLASSES


def test_explain_thesis_yields_one_row_per_unverifiable_claim_in_claim_order():
    measured = make_claim("c-measured", "f1")
    unmeasured = make_claim("c-unmeasured", "f2")
    unfalsifiable = make_claim("c-unfalsifiable", "")
    thesis = make_thesis("Explain thesis", [measured, unmeasured, unfalsifiable], clock=CLOCK)
    out = explain_thesis(thesis, [_measured(measured)])
    assert [e.claim_id for e in out] == [unmeasured.id, unfalsifiable.id]
    assert [e.missing for e in out] == [MEASUREMENT, FALSIFICATION_CONDITION]


def test_explanation_row_is_the_typed_dict():
    claim = _claim()
    row = explanation_row(explain_claim(claim, None))
    assert set(row) == {"claim_id", "missing", "needed"}
    assert row["claim_id"] == claim.id
    assert row["missing"] == MEASUREMENT
