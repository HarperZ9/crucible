"""Interop: crucible's assessment verdicts as organ-bundle interchange entries.

The organ bundle is the shared spine gather, index, forum, learn, and crucible
compose on. This module maps crucible's assessment verdicts into that entry
shape, so a crucible assessment can feed forum's evidence lane, seed a learn
lesson, or compose into an index context envelope, all through one contract.

Entry shape matches the proof-surface organ-bundle contract
(entry_id, organ_id, receipt_kind, status, payload_sha256, summary, payload_ref).
gather/src/gather/interop.py is the reference implementation.
"""
from __future__ import annotations

import re

ORGAN = "crucible"
SPINE_KIND = "crucible-assessment"
STATUSES = frozenset({
    "pass", "fail", "unverified", "warn", "needs-human", "not-applicable", "unknown",
})
_HEX = re.compile(r"^[0-9a-f]{64}$")
_FIELDS = ("entry_id", "organ_id", "receipt_kind", "status", "payload_sha256",
           "summary", "payload_ref")

# Map crucible's verdict counts to a spine status.
# A clean assessment (all MATCH) is "pass"; any DRIFT is "fail";
# UNVERIFIABLE without DRIFT is "unverified".
def _verdict_to_status(match: int, drift: int, unverifiable: int) -> str:
    if drift > 0:
        return "fail"
    if match > 0 and unverifiable == 0:
        return "pass"
    if unverifiable > 0 and match == 0:
        return "unverified"
    if match > 0:
        return "warn"
    return "unknown"


def _entry(entry_id: str, status: str, payload_sha256: str, summary: str, ref: str) -> dict:
    return {
        "entry_id": entry_id,
        "organ_id": ORGAN,
        "receipt_kind": SPINE_KIND,
        "status": status,
        "payload_sha256": payload_sha256,
        "summary": summary[:160],
        "payload_ref": ref,
    }


def assessment_entry(assessment, *, entry_id: str = "crucible-assess-1",
                     ref: str = "crucible://assessment") -> dict:
    """Map a crucible Assessment into an organ-bundle entry.

    The assessment's seal is the payload digest; the verdict counts map to a
    spine status; the thesis ID and counts go into the summary.
    """
    status = _verdict_to_status(assessment.match, assessment.drift, assessment.unverifiable)
    summary = (
        f"thesis {assessment.thesis_id}: "
        f"{assessment.match} match, {assessment.drift} drift, "
        f"{assessment.unverifiable} unverifiable ({assessment.disposition})"
    )
    return _entry(
        entry_id=entry_id,
        status=status,
        payload_sha256=assessment.seal,
        summary=summary,
        ref=ref,
    )


def verdict_entry(verdict: dict, *, entry_id: str = "crucible-verdict-1",
                  ref: str = "crucible://verdict") -> dict:
    """Map a single verdict dict (from an assessment's verdicts tuple) into an
    organ-bundle entry. Each claim verdict can compose independently."""
    claim_id = verdict.get("claim_id", "unknown")
    verdict_str = verdict.get("verdict", "UNVERIFIABLE")
    status = {"MATCH": "pass", "DRIFT": "fail"}.get(verdict_str, "unverified")
    sha = verdict.get("verdict_sha256", verdict.get("sha256", ""))
    summary = f"claim {claim_id}: {verdict_str}"
    return _entry(entry_id, status, sha, summary, ref)


def validate_entry(entry: dict) -> bool:
    """Validate one organ-bundle entry shape. Returns True if well-formed."""
    if not isinstance(entry, dict):
        return False
    if set(entry.keys()) != set(_FIELDS):
        return False
    if entry["organ_id"] != ORGAN:
        return False
    if entry["receipt_kind"] != SPINE_KIND:
        return False
    if entry["status"] not in STATUSES:
        return False
    if not _HEX.match(entry.get("payload_sha256", "")):
        return False
    return True
