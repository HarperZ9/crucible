"""Cleanroom bundle review contract helpers."""
from __future__ import annotations

from collections.abc import Mapping

from crucible.assess import Assessment
from crucible.claim import Claim
from crucible.report import render_assessment_report
from crucible.thesis import Thesis, verify_thesis

REQUIRED_FILES = ("spec.json", "run.json", "report.md", "review.md")
ALLOWED_INPUTS = ["spec.json", "run.json", "report.md"]
EXCLUDED_CONTEXT = ["worker context", "reasoning trace", "intermediate steps"]
EXPECTED_ARTIFACT_PATHS = {
    "bundle": ".",
    "report": "report.md",
    "record": "run.json",
    "spec": "spec.json",
    "review": "review.md",
}

REVIEW_INSTRUCTIONS = "\n".join([
    "# cleanroom review",
    "",
    "Verifier inputs:",
    "- `spec.json`: the original thesis spec with claims and falsification conditions.",
    "- `run.json`: the witnessed run record and integrity checks.",
    "- `report.md`: the human-readable assessment artifact.",
    "",
    "Verifier boundary:",
    "- Use only the original spec and the artifact in this packet.",
    "- Do not use worker context, reasoning trace, intermediate steps, prior chat, or notes.",
    "- If success cannot be evaluated from this minimal state, mark the spec not checkable yet.",
]) + "\n"


def artifact_paths(run: Mapping | None, findings: list[str]) -> bool:
    if run is None:
        return False
    ok = True
    for key, expected in EXPECTED_ARTIFACT_PATHS.items():
        if run.get(key) != expected:
            ok = False
    if not ok:
        findings.append("run.json artifact paths must be packet-relative")
    return ok


def expected_report(spec: Mapping | None, run: Mapping | None, findings: list[str]) -> str | None:
    if spec is None or run is None:
        return None
    checks = run.get("checks")
    if not isinstance(checks, Mapping):
        findings.append("run.json checks must be an object")
        return None
    thesis = thesis_from_spec(spec, findings)
    assessment = assessment_from_run(run, findings)
    if thesis is None or assessment is None:
        return None
    return render_assessment_report(thesis, assessment, checks=checks)


def thesis_from_spec(spec: Mapping, findings: list[str]) -> Thesis | None:
    claims_value = spec.get("claims")
    if not isinstance(claims_value, list):
        findings.append("spec.json claims must be a list")
        return None
    claims: list[Claim] = []
    for index, row in enumerate(claims_value, 1):
        if not isinstance(row, Mapping):
            findings.append(f"spec.json claim {index} must be an object")
            return None
        claim = claim_from_spec(row, index, findings)
        if claim is None:
            return None
        claims.append(claim)
    thesis = Thesis(
        id=string(spec, "id", "spec thesis id", findings),
        title=string(spec, "title", "spec thesis title", findings),
        claims=tuple(claims),
        registered_at=0.0,
        disposition=string(spec, "disposition", "spec thesis disposition", findings),
        seal=string(spec, "seal", "spec thesis seal", findings),
    )
    if not verify_thesis(thesis):
        findings.append("spec.json thesis seal or claim receipts do not verify")
        return None
    return thesis


def claim_from_spec(row: Mapping, index: int, findings: list[str]) -> Claim | None:
    claim = Claim(
        id=string(row, "id", f"spec claim {index} id", findings),
        text=string(row, "text", f"spec claim {index} text", findings),
        falsification=string(row, "falsification", f"spec claim {index} falsification", findings),
        sha256=string(row, "sha256", f"spec claim {index} sha256", findings),
    )
    if claim.verify():
        return claim
    findings.append(f"spec claim {index} receipt does not verify")
    return None


def assessment_from_run(run: Mapping, findings: list[str]) -> Assessment | None:
    value = run.get("assessment")
    if not isinstance(value, Mapping):
        findings.append("run.json assessment must be an object")
        return None
    try:
        return Assessment.from_dict(value)
    except (KeyError, TypeError, ValueError) as exc:
        findings.append(f"run.json assessment is invalid: {exc}")
        return None


def string(row: Mapping, key: str, label: str, findings: list[str]) -> str:
    value = row.get(key)
    if isinstance(value, str):
        return value
    findings.append(f"{label} must be a string")
    return ""


def same(left: Mapping, right: Mapping, key: str, findings: list[str], label: str) -> bool:
    return same_cross(left, key, right, key, findings, label)


def same_cross(
    left: Mapping, lk: str, right: Mapping, rk: str, findings: list[str], label: str,
) -> bool:
    if left.get(lk) == right.get(rk):
        return True
    findings.append(f"{label} mismatch")
    return False


def claim_refs(rows: object) -> list[tuple[object, object]]:
    if not isinstance(rows, list):
        return []
    refs = []
    for row in rows:
        if isinstance(row, Mapping):
            refs.append((row.get("id"), row.get("sha256")))
    return refs
