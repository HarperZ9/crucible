from __future__ import annotations

from crucible.claim import make_claim
from crucible.telos_measure import (
    PROTOCOL,
    TelosMeasure,
    check_content,
    content_hash,
    verify_telos_artifact,
)
from crucible.verdict import DRIFT, MATCH, UNVERIFIABLE, verdict_for

CLOCK = lambda: 1000.0  # noqa: E731


def _artifact(verdict="verified", recheck=None):
    return {
        "protocol": PROTOCOL,
        "flagship": "telos",
        "kind": "conservation-law",
        "subject": {"system": "sho"},
        "claim": "Q = 0.5*v^2 + 0.5*x^2",
        "certificate": {"verdict": verdict, "certified": verdict == "verified", "criterion": "conservation"},
        "recheck": recheck or {"verifier": "conservation", "expr": "energy", "system": "sho"},
    }


def test_verify_telos_artifact_replays_registered_verifier():
    result = verify_telos_artifact(_artifact(), {"conservation": lambda r: "verified"})

    assert result == {"ok": True, "reproduced": "verified", "carried": "verified", "matches": True}


def test_verify_telos_artifact_catches_forged_or_drifted_verdict():
    result = verify_telos_artifact(_artifact("verified"), {"conservation": lambda r: "refuted"})

    assert result["ok"] is True
    assert result["reproduced"] == "refuted"
    assert result["carried"] == "verified"
    assert result["matches"] is False


def test_verify_telos_artifact_fails_closed_without_registered_verifier():
    result = verify_telos_artifact(_artifact(), {})

    assert result["ok"] is False
    assert result["matches"] is False
    assert "no verifier" in result["reason"]


def test_telos_measure_maps_verified_refuted_and_unverifiable_to_measurements():
    claim = make_claim("the Telos artifact's law holds", "Telos re-verifies as refuted")
    verified = TelosMeasure({claim.id: _artifact()}, {"conservation": lambda r: "verified"},
                            clock=CLOCK).measure(claim)
    refuted = TelosMeasure({claim.id: _artifact()}, {"conservation": lambda r: "refuted"},
                           clock=CLOCK).measure(claim)
    unknown = TelosMeasure({claim.id: _artifact()}, {"conservation": lambda r: "unverifiable"},
                           clock=CLOCK).measure(claim)

    assert verified.method == "telos:conservation"
    assert verified.deviation == 0.0
    assert verified.measured_at == 1000.0
    assert verdict_for(claim, verified).status == MATCH
    assert verdict_for(claim, refuted).status == DRIFT
    assert verdict_for(claim, unknown).status == UNVERIFIABLE


def test_telos_measure_treats_unregistered_or_missing_artifact_as_unverifiable():
    claim = make_claim("a law holds", "Telos cannot recheck it")
    no_artifact = TelosMeasure({}, {}, clock=CLOCK).measure(claim)
    no_verifier = TelosMeasure({claim.id: _artifact()}, {}, clock=CLOCK).measure(claim)

    assert no_artifact.deviation is None
    assert no_verifier.deviation is None
    assert verdict_for(claim, no_artifact).status == UNVERIFIABLE
    assert verdict_for(claim, no_verifier).status == UNVERIFIABLE


def test_content_artifact_hash_matches_the_javascript_protocol_shape():
    artifact = _artifact("verified", {"verifier": "content", "hash": content_hash("abc")})

    assert content_hash("abc") == "1a47e90b"
    assert check_content(artifact, "abc") is True
    assert check_content(artifact, "abcd") is False
