"""The tolerance that decides MATCH/DRIFT is sealed with the claim, so a verdict cannot be rescued
by widening it after the fact. These are falsifiers for that guarantee: the honest measurement
decides, the widened one is refused, and a hand-forged rescue fails re-derivation."""
from __future__ import annotations

from crucible.assess import (
    _VSEAL_FIELDS,
    Assessment,
    _measurement_seal,
    _record_fields,
    _seal_record,
    _seal_rows,
    assess,
    recheck_assessment,
)
from crucible.claim import make_claim
from crucible.thesis import make_thesis
from crucible.verdict import DRIFT, MATCH, UNVERIFIABLE, Measurement, verdict_for

_CLOCK = lambda: 1000.0  # noqa: E731 - an injected clock, the record replays


def _sealed_claim():
    return make_claim("the k5 interval holds", "pass@5 lands outside the sealed band", tolerance=0.05)


def _measurement(claim, deviation, tolerance):
    return Measurement(claim.id, claim.sha256, deviation=deviation, tolerance=tolerance,
                       method="bench", measured_at=1001.0)


def test_matching_tolerance_still_decides():
    claim = _sealed_claim()
    assert verdict_for(claim, _measurement(claim, 0.02, 0.05)).status == MATCH
    assert verdict_for(claim, _measurement(claim, 0.08, 0.05)).status == DRIFT


def test_mismatched_tolerance_is_unverifiable_fail_closed():
    claim = _sealed_claim()
    v = verdict_for(claim, _measurement(claim, 0.08, 0.10))
    assert v.status == UNVERIFIABLE
    assert "sealed" in v.grounds


def test_widened_tolerance_cannot_rescue_a_sealed_drift():
    claim = _sealed_claim()
    thesis = make_thesis("prereg", [claim], clock=_CLOCK)
    _, honest = assess(thesis, [_measurement(claim, 0.08, 0.05)], clock=_CLOCK)
    assert honest[0].status == DRIFT
    # The rescue attempt: same thesis, tolerance widened at adjudication time.
    _, widened = assess(thesis, [_measurement(claim, 0.08, 0.10)], clock=_CLOCK)
    assert widened[0].status == UNVERIFIABLE  # refused at the source, never a MATCH


def test_hand_forged_match_fails_rederivation():
    # The full launder: a MATCH verdict row plus the widened measurement, every seal recomputed
    # consistently. verify_assessment cannot see it (the seals are self-consistent); the
    # re-derivation must, because verdict_for refuses the unsealed tolerance.
    claim = _sealed_claim()
    thesis = make_thesis("prereg", [claim], clock=_CLOCK)
    forged_v = {"claim_id": claim.id, "claim_sha256": claim.sha256, "status": MATCH,
                "deviation": 0.08, "tolerance": 0.10, "margin": 0.2, "method": "bench",
                "grounds": "deviation 0.08 within tolerance 0.1", "disposition": thesis.disposition}
    forged_m = {"claim_id": claim.id, "claim_sha256": claim.sha256, "deviation": 0.08,
                "tolerance": 0.10, "method": "bench", "measured_at": 1001.0, "evidence": []}
    vseal = _seal_rows([forged_v], _VSEAL_FIELDS)
    mseal = _measurement_seal([forged_m])
    fields = _record_fields(1000.0, thesis.id, thesis.seal, 1, 1, 0, 0, vseal, mseal,
                            thesis.disposition, None)
    forged = Assessment(1000.0, thesis.id, thesis.seal, 1, 1, 0, 0, vseal, mseal,
                        (forged_v,), (forged_m,), thesis.disposition, None, _seal_record(fields))
    result = recheck_assessment(thesis, forged)
    assert result["seals_ok"]  # internally consistent: the forge is competent
    assert not result["verdicts_rederive"]  # and still caught: the sealed tolerance decides


def test_legacy_unsealed_claim_remains_rescuable_the_honest_null():
    # A claim sealed WITHOUT a tolerance keeps the old behavior: the widened tolerance re-derives a
    # self-consistent MATCH. This is why the tolerance belongs in the seal for every new
    # preregistration; existing receipts keep their hashes and this residual hole, stated openly.
    claim = make_claim("the k5 interval holds", "pass@5 lands outside the sealed band")
    thesis = make_thesis("prereg", [claim], clock=_CLOCK)
    _, widened = assess(thesis, [_measurement(claim, 0.08, 0.10)], clock=_CLOCK)
    assert widened[0].status == MATCH
