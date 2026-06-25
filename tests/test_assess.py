"""The witnessed assessment: counts, a re-checkable seal, and a deterministic replay."""
from __future__ import annotations

import dataclasses

from crucible.assess import (
    Assessment,
    assess,
    recheck_assessment,
    verdict_seal,
    verify_assessment,
)
from crucible.claim import make_claim
from crucible.registry import Registry
from crucible.thesis import make_thesis
from crucible.verdict import DRIFT, MATCH, UNVERIFIABLE, Measurement

CLOCK = lambda: 1000.0  # noqa: E731


def _thesis():
    return make_thesis("mixed", [
        make_claim("holds", "f1"),
        make_claim("breaks", "f2"),
        make_claim("untested", "f3"),
    ], clock=CLOCK)


def _measurements(t):
    return [
        Measurement(t.claims[0].id, t.claims[0].sha256, 0.0, 0.1, "oracle", 0.0),
        Measurement(t.claims[1].id, t.claims[1].sha256, 9.0, 0.1, "oracle", 0.0),
        # the third claim gets no measurement -> UNVERIFIABLE
    ]


def test_assess_counts_each_outcome():
    t = _thesis()
    a, verdicts = assess(t, _measurements(t), clock=CLOCK)
    assert (a.match, a.drift, a.unverifiable) == (1, 1, 1)
    assert a.claims == 3
    assert [v.status for v in verdicts] == [MATCH, DRIFT, UNVERIFIABLE]


def test_verdict_seal_is_order_independent():
    t = _thesis()
    _, verdicts = assess(t, _measurements(t), clock=CLOCK)
    assert verdict_seal(verdicts) == verdict_seal(list(reversed(verdicts)))


def test_assessment_seal_verifies_and_tamper_is_caught():
    t = _thesis()
    a, _ = assess(t, _measurements(t), clock=CLOCK)
    assert verify_assessment(a)
    # flipping a count without resealing must be caught
    tampered = dataclasses.replace(a, match=3, drift=0)
    assert not verify_assessment(tampered)


def test_to_dict_from_dict_roundtrip_recheckable():
    t = _thesis()
    a, _ = assess(t, _measurements(t), clock=CLOCK)
    again = Assessment.from_dict(a.to_dict())
    assert again == a
    assert verify_assessment(again)


def test_replay_is_deterministic_with_injected_clock():
    t = _thesis()
    a1, _ = assess(t, _measurements(t), clock=CLOCK)
    a2, _ = assess(t, _measurements(t), clock=CLOCK)
    assert a1.seal == a2.seal


def test_assess_records_into_registry(tmp_path):
    reg = Registry(str(tmp_path), fsync=False)
    t = _thesis()
    reg.register(t)
    a, _ = assess(t, _measurements(t), clock=CLOCK, registry=reg)
    history = list(reg.assessments())
    assert len(history) == 1
    assert Assessment.from_dict(history[0]).seal == a.seal


def test_no_measurements_all_unverifiable():
    t = _thesis()
    a, verdicts = assess(t, None, clock=CLOCK)
    assert a.unverifiable == 3 and a.match == 0 and a.drift == 0


def test_recheck_rederives_verdicts_from_thesis_and_measurements():
    t = _thesis()
    a, _ = assess(t, _measurements(t), clock=CLOCK)
    assert recheck_assessment(t, a) == {"seals_ok": True, "thesis_ok": True, "verdicts_rederive": True}


def test_tampered_measurement_breaks_verify():
    t = _thesis()
    a, _ = assess(t, _measurements(t), clock=CLOCK)
    bad = [dict(m) for m in a.measurements]
    bad[0]["deviation"] = 999.0  # edit a measurement without resealing
    assert not verify_assessment(dataclasses.replace(a, measurements=tuple(bad)))


def test_recheck_exposes_a_forged_but_internally_consistent_verdict():
    # The differentiator: a verdict flipped DRIFT -> MATCH and fully re-sealed passes every seal
    # check, yet re-deriving it from the measurements exposes it. A verdict cannot be asserted.
    from crucible.assess import _VSEAL_FIELDS, _record_fields, _seal_record, _seal_rows

    t = _thesis()
    a, _ = assess(t, _measurements(t), clock=CLOCK)
    forged_verdicts = []
    for vr in a.verdicts:
        vr = dict(vr)
        if vr["status"] == "DRIFT":
            vr["status"] = "MATCH"  # quietly turn a break into a pass
        forged_verdicts.append(vr)
    new_vseal = _seal_rows(forged_verdicts, _VSEAL_FIELDS)
    fields = _record_fields(a.started_at, a.thesis_id, a.thesis_seal, a.claims, 2, 0, 1,
                            new_vseal, a.measurement_seal, a.stored)
    forged = dataclasses.replace(a, verdicts=tuple(forged_verdicts), match=2, drift=0,
                                 verdict_seal=new_vseal, seal=_seal_record(fields))
    assert verify_assessment(forged)  # the forgery is internally consistent: every seal matches
    result = recheck_assessment(t, forged)
    assert result["seals_ok"] and not result["verdicts_rederive"]  # re-derivation exposes the lie
