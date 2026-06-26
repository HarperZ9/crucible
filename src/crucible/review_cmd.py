"""CLI command for validating cleanroom review bundles."""
from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping

REQUIRED_FILES = ("spec.json", "run.json", "report.md", "review.md")
ALLOWED_INPUTS = ["spec.json", "run.json", "report.md"]
EXCLUDED_CONTEXT = ["worker context", "reasoning trace", "intermediate steps"]


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
        "spec_matches_run": False,
    }
    if checks["required_files"]:
        spec = _load_json(os.path.join(base, "spec.json"), "spec.json", findings)
        run = _load_json(os.path.join(base, "run.json"), "run.json", findings)
        checks["verifier_boundary"] = _verifier_boundary(run, findings)
        checks["spec_matches_run"] = _spec_matches_run(spec, run, findings)
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
    excluded = verifier.get("excluded")
    if excluded != EXCLUDED_CONTEXT:
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
    ok = _same(spec, thesis, "id", findings, "spec thesis id")
    ok = _same(spec, thesis, "title", findings, "spec thesis title") and ok
    ok = _same(spec, thesis, "seal", findings, "spec thesis seal") and ok
    ok = _same(spec, thesis, "disposition", findings, "spec thesis disposition") and ok
    ok = _same_cross(spec, "id", assessment, "thesis_id", findings, "assessment thesis id") and ok
    ok = _same_cross(spec, "seal", assessment, "thesis_seal", findings, "assessment thesis seal") and ok
    if assessment.get("claims") != len(spec.get("claims", [])):
        findings.append("assessment claim count does not match spec.json claims")
        ok = False
    if _claim_refs(spec.get("claims")) != _claim_refs(thesis.get("claims")):
        findings.append("run thesis claim references do not match spec.json claims")
        ok = False
    return ok


def _same(left: Mapping, right: Mapping, key: str, findings: list[str], label: str) -> bool:
    return _same_cross(left, key, right, key, findings, label)


def _same_cross(
    left: Mapping,
    lk: str,
    right: Mapping,
    rk: str,
    findings: list[str],
    label: str,
) -> bool:
    if left.get(lk) == right.get(rk):
        return True
    findings.append(f"{label} mismatch")
    return False


def _claim_refs(rows: object) -> list[tuple[object, object]]:
    if not isinstance(rows, list):
        return []
    refs = []
    for row in rows:
        if isinstance(row, Mapping):
            refs.append((row.get("id"), row.get("sha256")))
    return refs


def _print_human(result: dict) -> None:
    status = "PASS" if result["ok"] else "FAIL"
    print(f"cleanroom bundle {status}: {result['bundle']}")
    for key, value in result["checks"].items():
        print(f"  {key}: {value}")
    for finding in result["findings"]:
        print(f"  finding: {finding}", file=sys.stderr)
