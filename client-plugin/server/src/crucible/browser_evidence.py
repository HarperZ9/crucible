"""Verification helpers for Telos browser evidence packets.

Browser evidence packets are compact handles over captured browser state. Crucible checks their
SHAPE and passes through a carried FAILURE verdict; raw DOM, screenshots, and session data stay
outside the model/council boundary unless a later tool explicitly dereferences them. Crucible cannot
re-run the packet's own verifier here, so it never re-mints a carried MATCH as its own verdict: a
self-declared success plus a well-formed shape is UNVERIFIABLE (no receipt, no accept), while a
carried DRIFT/UNVERIFIABLE is passed through because it only ever downgrades.
"""
from __future__ import annotations

from collections.abc import Mapping

SCHEMA = "project-telos.browser-evidence/v1"
VERDICTS = {"MATCH", "DRIFT", "UNVERIFIABLE"}


def verify_browser_evidence(packet: Mapping) -> dict:
    """Return a local verdict for a Telos browser evidence packet.

    This is a SHAPE check plus a fail-safe pass-through, not a re-verification: crucible does not
    re-execute the packet's verifier (the raw evidence is outside the boundary). A carried DRIFT or
    UNVERIFIABLE is relayed (a self-reported failure only ever downgrades, never launders). A carried
    MATCH is NOT relayed as crucible's MATCH -- a well-formed packet is reported UNVERIFIABLE with the
    carried verdict preserved under ``carried_verdict``, so a consumer keyed on ``verdict`` can never
    accept a self-asserted success as crucible-verified.
    """
    if packet.get("schema") != SCHEMA:
        return {"verdict": "UNVERIFIABLE", "reason": "schema_mismatch"}

    verification = packet.get("verification")
    if not isinstance(verification, Mapping):
        return {"verdict": "UNVERIFIABLE", "reason": "missing_verification"}

    carried = verification.get("verdict")
    if carried not in VERDICTS:
        return {"verdict": "UNVERIFIABLE", "reason": "invalid_carried_verdict"}
    if carried == "DRIFT":
        return {"verdict": "DRIFT", "reason": "carried_verdict_drift", "carried_verdict": "DRIFT"}
    if carried == "UNVERIFIABLE":
        return {"verdict": "UNVERIFIABLE", "reason": "carried_verdict_unverifiable",
                "carried_verdict": "UNVERIFIABLE"}

    if not packet.get("artifact_hashes"):
        return {"verdict": "UNVERIFIABLE", "reason": "missing_artifact_hashes"}
    if not isinstance(packet.get("side_effect"), Mapping):
        return {"verdict": "UNVERIFIABLE", "reason": "missing_side_effect"}

    # Shape is well-formed and the packet carries MATCH, but crucible re-ran nothing: the carried
    # success is not crucible's verdict. Fail closed to UNVERIFIABLE, preserving the carried claim.
    return {
        "verdict": "UNVERIFIABLE",
        "reason": "carried_verdict_match_not_reverified",
        "carried_verdict": "MATCH",
    }
