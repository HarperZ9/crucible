"""Verification helpers for Telos browser evidence packets.

Browser evidence packets are compact handles over captured browser state. Crucible verifies their
shape and carried verifier verdict locally; raw DOM, screenshots, and session data stay outside the
model/council boundary unless a later tool explicitly dereferences them.
"""
from __future__ import annotations

from collections.abc import Mapping

SCHEMA = "project-telos.browser-evidence/v1"
VERDICTS = {"MATCH", "DRIFT", "UNVERIFIABLE"}


def verify_browser_evidence(packet: Mapping) -> dict:
    """Return a local verdict for a Telos browser evidence packet."""
    if packet.get("schema") != SCHEMA:
        return {"verdict": "UNVERIFIABLE", "reason": "schema_mismatch"}

    verification = packet.get("verification")
    if not isinstance(verification, Mapping):
        return {"verdict": "UNVERIFIABLE", "reason": "missing_verification"}

    carried = verification.get("verdict")
    if carried not in VERDICTS:
        return {"verdict": "UNVERIFIABLE", "reason": "invalid_carried_verdict"}
    if carried == "DRIFT":
        return {"verdict": "DRIFT", "reason": "carried_verdict_drift"}
    if carried == "UNVERIFIABLE":
        return {"verdict": "UNVERIFIABLE", "reason": "carried_verdict_unverifiable"}

    if not packet.get("artifact_hashes"):
        return {"verdict": "UNVERIFIABLE", "reason": "missing_artifact_hashes"}
    if not isinstance(packet.get("side_effect"), Mapping):
        return {"verdict": "UNVERIFIABLE", "reason": "missing_side_effect"}

    return {"verdict": "MATCH", "reason": "packet-shape-and-artifact-refs-present"}
