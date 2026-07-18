"""ProofMeasure: the sound oracle for formal claims (a proof / type checker). It must
DECIDE a claim -- an accepted proof is MATCH, a rejected one DRIFTs (the oracle can
fail), a checker that is absent or errors is UNVERIFIABLE (fail-closed, never a fake
pass) -- and carry a recheck descriptor so a stranger re-runs the identical check."""

from crucible.claim import make_claim
from crucible.proof_measure import ProofMeasure
from crucible.verdict import DRIFT, MATCH, UNVERIFIABLE, verdict_for


def _claim(tol=None):
    return make_claim("sqrt(2) is irrational", "the checker rejects the proof",
                      tolerance=tol, id="c1")


def test_accepted_proof_is_a_match_with_zero_deviation():
    c = _claim()
    m = ProofMeasure({"c1": {"checker": "lean", "cmd": ["lean", "irr.lean"]}},
                     runner=lambda cmd: (True, "no errors")).measure(c)
    assert m.deviation == 0.0 and m.method == "checker:proof"
    assert verdict_for(c, m).status == MATCH
    assert m.recheck["oracle"] == "checker:proof" and m.recheck["cmd"] == ("lean", "irr.lean")


def test_rejected_proof_drifts_the_oracle_can_fail():
    c = _claim()
    m = ProofMeasure({"c1": {"checker": "lean", "cmd": ["lean", "bad.lean"]}},
                     runner=lambda cmd: (False, "error: unknown identifier 'foo'")).measure(c)
    assert m.deviation > m.tolerance
    assert verdict_for(c, m).status == DRIFT
    assert "rejected" in m.evidence[0]


def test_absent_checker_is_unverifiable_never_faked():
    c = _claim()

    def not_installed(cmd):
        raise FileNotFoundError("lean: command not found")
    m = ProofMeasure({"c1": {"checker": "lean", "cmd": ["lean", "x"]}},
                     runner=not_installed).measure(c)
    assert m.deviation is None                        # fail-closed: an unrun checker never holds
    assert verdict_for(c, m).status == UNVERIFIABLE


def test_no_spec_for_the_claim_is_unverifiable():
    c = _claim()
    m = ProofMeasure({}, runner=lambda cmd: (True, "")).measure(c)
    assert m.deviation is None and verdict_for(c, m).status == UNVERIFIABLE


def test_non_sequence_checker_command_is_unverifiable_without_running_it():
    c = _claim()
    calls = []
    m = ProofMeasure({"c1": {"checker": "lean", "cmd": "lean proof.lean"}},
                     runner=lambda cmd: (calls.append(cmd), (True, "ok"))[1]).measure(c)
    assert m.deviation is None
    assert verdict_for(c, m).status == UNVERIFIABLE
    assert calls == []


def test_invalid_checker_command_elements_are_unverifiable_without_running_them():
    c = _claim()
    for command in ([None], [""], ["   "], ["lean", None]):
        calls = []
        m = ProofMeasure({"c1": {"checker": "lean", "cmd": command}},
                         runner=lambda cmd: (calls.append(cmd), (True, "ok"))[1]).measure(c)
        assert m.deviation is None
        assert verdict_for(c, m).status == UNVERIFIABLE
        assert calls == []


def test_recheck_binds_the_artifact_for_replay():
    c = _claim()
    m = ProofMeasure({"c1": {"checker": "coq", "cmd": ["coqc", "p.v"], "artifact": "Theorem p. Qed."}},
                     runner=lambda cmd: (True, "ok")).measure(c)
    assert m.recheck["checker"] == "coq"
    assert len(m.recheck["artifact_sha256"]) == 64   # the exact proof text is bound


def test_a_sealed_tolerance_is_honoured_so_the_verdict_binds():
    c = _claim(tol=0.25)
    m = ProofMeasure({"c1": {"checker": "lean", "cmd": ["lean", "x"]}},
                     runner=lambda cmd: (True, "ok")).measure(c)
    assert m.tolerance == 0.25                        # matches the sealed tolerance
    assert verdict_for(c, m).status == MATCH
