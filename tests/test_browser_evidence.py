from crucible.browser_evidence import verify_browser_evidence


PACKET = {
    "schema": "project-telos.browser-evidence/v1",
    "mode": "research-capture",
    "artifact_hashes": [{"ref": "artifact:x", "hash": "sha256:abc"}],
    "side_effect": {"class": "read", "external_write": False, "reversible": True},
    "verification": {"verdict": "MATCH", "ref": "crucible:shape"},
}


def test_verify_browser_evidence_match():
    assert verify_browser_evidence(PACKET) == {
        "verdict": "MATCH",
        "reason": "packet-shape-and-artifact-refs-present",
    }


def test_verify_browser_evidence_unverifiable_for_malformed_packet():
    result = verify_browser_evidence({"schema": "wrong"})

    assert result["verdict"] == "UNVERIFIABLE"
    assert result["reason"] == "schema_mismatch"


def test_verify_browser_evidence_drift_for_carried_drift():
    packet = {**PACKET, "verification": {"verdict": "DRIFT", "ref": "crucible:drift"}}

    result = verify_browser_evidence(packet)

    assert result["verdict"] == "DRIFT"
    assert result["reason"] == "carried_verdict_drift"


def test_verify_browser_evidence_unverifiable_for_missing_artifacts():
    packet = {**PACKET, "artifact_hashes": []}

    result = verify_browser_evidence(packet)

    assert result["verdict"] == "UNVERIFIABLE"
    assert result["reason"] == "missing_artifact_hashes"
