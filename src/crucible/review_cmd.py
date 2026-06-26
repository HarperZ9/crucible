"""CLI command for validating cleanroom review bundles."""
from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping

from crucible.review_contract import (
    ALLOWED_INPUTS,
    EXCLUDED_CONTEXT,
    REQUIRED_FILES,
    REVIEW_INSTRUCTIONS,
    artifact_paths,
    claim_refs,
    expected_report,
    same,
    same_cross,
)


def cmd_review(args) -> int:
    result = review_bundle(args.bundle)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_human(result)
    return 0 if result["ok"] else 1


def review_bundle(bundle: str) -> dict:
    findings: list[str] = []
    base = os.path.abspath(bundle)
    spec: Mapping | None = None
    run: Mapping | None = None
    checks = {
        "required_files": _required_files(base, findings),
        "no_extra_context": _no_extra_context(base, findings),
        "verifier_boundary": False,
        "artifact_paths": False,
        "spec_matches_run": False,
        "report_matches_run": False,
        "review_instructions": False,
        "run_integrity": False,
    }
    if checks["required_files"]:
        spec = _load_json(os.path.join(base, "spec.json"), "spec.json", findings)
        run = _load_json(os.path.join(base, "run.json"), "run.json", findings)
        checks["verifier_boundary"] = _verifier_boundary(run, findings)
        checks["artifact_paths"] = artifact_paths(run, findings)
        checks["spec_matches_run"] = _spec_matches_run(spec, run, findings)
        checks["report_matches_run"] = _report_matches_run(base, spec, run, findings)
        checks["review_instructions"] = _review_instructions(base, findings)
        checks["run_integrity"] = _run_integrity(run, findings)
    return {
        "ok": all(checks.values()),
        "bundle": base,
        "allowed_inputs": ALLOWED_INPUTS,
        "excluded": EXCLUDED_CONTEXT,
        "checks": checks,
        "findings": findings,
    }


def _required_files(base: str, findings: list[str]) -> bool:
    if not os.path.isdir(base):
        findings.append(f"bundle is not a directory: {base}")
        return False
    ok = True
    for name in REQUIRED_FILES:
        path = os.path.join(base, name)
        if not os.path.isfile(path):
            findings.append(f"missing required file: {name}")
            ok = False
    return ok


def _no_extra_context(base: str, findings: list[str]) -> bool:
    if not os.path.isdir(base):
        return False
    try:
        names = sorted(os.listdir(base))
    except OSError as exc:
        findings.append(f"cannot list bundle: {exc}")
        return False
    extras = [name for name in names if name not in REQUIRED_FILES]
    for name in extras:
        findings.append(f"unexpected context file in cleanroom bundle: {name}")
    return not extras


def _run_integrity(run: Mapping | None, findings: list[str]) -> bool:
    if run is None:
        return False
    embedded = run.get("checks")
    if not isinstance(embedded, Mapping):
        findings.append("run.json checks must be an object")
        return False
    checks_ok = all(value is True for value in embedded.values())
    if run.get("ok") != checks_ok:
        findings.append("run.json ok must equal all embedded checks")
        return False
    if not checks_ok:
        findings.append("run.json integrity checks must all pass")
        return False
    return True


def _review_instructions(base: str, findings: list[str]) -> bool:
    path = os.path.join(base, "review.md")
    try:
        with open(path, encoding="utf-8") as f:
            actual = f.read()
    except OSError as exc:
        findings.append(f"review.md is not readable: {exc}")
        return False
    if actual != REVIEW_INSTRUCTIONS:
        findings.append("review.md does not match cleanroom instructions")
        return False
    return True


def _load_json(path: str, label: str, findings: list[str]) -> Mapping | None:
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(f"{label} is not readable JSON: {exc}")
        return None
    if not isinstance(payload, Mapping):
        findings.append(f"{label} must be a JSON object")
        return None
    return payload


def _verifier_boundary(run: Mapping | None, findings: list[str]) -> bool:
    if run is None:
        return False
    verifier = run.get("verifier")
    if not isinstance(verifier, Mapping):
        findings.append("run.json is missing verifier boundary metadata")
        return False
    ok = True
    if verifier.get("mode") != "cleanroom":
        findings.append("verifier mode must be cleanroom")
        ok = False
    if verifier.get("inputs") != ALLOWED_INPUTS:
        findings.append("verifier inputs must be spec.json, run.json, and report.md only")
        ok = False
    if verifier.get("excluded") != EXCLUDED_CONTEXT:
        findings.append(
            "verifier excluded context must name worker context, reasoning trace, and intermediate steps"
        )
        ok = False
    text = str(verifier.get("checkability", "")).lower()
    if not all(term in text for term in ("original spec", "artifact", "not checkable yet")):
        findings.append("verifier checkability rule must be explicit")
        ok = False
    return ok


def _spec_matches_run(spec: Mapping | None, run: Mapping | None, findings: list[str]) -> bool:
    if spec is None or run is None:
        return False
    thesis = run.get("thesis")
    assessment = run.get("assessment")
    if not isinstance(thesis, Mapping) or not isinstance(assessment, Mapping):
        findings.append("run.json must carry thesis and assessment objects")
        return False
    ok = same(spec, thesis, "id", findings, "spec thesis id")
    ok = same(spec, thesis, "title", findings, "spec thesis title") and ok
    ok = same(spec, thesis, "seal", findings, "spec thesis seal") and ok
    ok = same(spec, thesis, "disposition", findings, "spec thesis disposition") and ok
    ok = same_cross(spec, "id", assessment, "thesis_id", findings, "assessment thesis id") and ok
    ok = same_cross(spec, "seal", assessment, "thesis_seal", findings,
                    "assessment thesis seal") and ok
    if assessment.get("claims") != len(spec.get("claims", [])):
        findings.append("assessment claim count does not match spec.json claims")
        ok = False
    if claim_refs(spec.get("claims")) != claim_refs(thesis.get("claims")):
        findings.append("run thesis claim references do not match spec.json claims")
        ok = False
    return ok


def _report_matches_run(
    base: str, spec: Mapping | None, run: Mapping | None, findings: list[str],
) -> bool:
    rendered = expected_report(spec, run, findings)
    if rendered is None:
        return False
    report_path = os.path.join(base, "report.md")
    try:
        with open(report_path, encoding="utf-8") as f:
            actual = f.read()
    except OSError as exc:
        findings.append(f"report.md is not readable: {exc}")
        return False
    if actual != rendered:
        findings.append("report.md does not match run.json assessment artifact")
        return False
    return True


def _print_human(result: dict) -> None:
    status = "PASS" if result["ok"] else "FAIL"
    print(f"cleanroom bundle {status}: {result['bundle']}")
    for key, value in result["checks"].items():
        print(f"  {key}: {value}")
    for finding in result["findings"]:
        print(f"  finding: {finding}", file=sys.stderr)
