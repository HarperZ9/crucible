"""CLI command for one complete steelman -> measure -> assess -> report run."""
from __future__ import annotations

import json
import os
import sys
import time

from crucible.assess import assess
from crucible.commands import (
    _load_measurements,
    _load_substrate,
    _recheck_last,
    _refutation_dict,
    _resolve_thesis,
    _verdict_dict,
)
from crucible.measure import TableMeasure, measure_thesis
from crucible.registry import Registry
from crucible.report import render_assessment_report
from crucible.steelman import NullSteelman, steelman_thesis

_INPUT_ERRORS = (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError)


def cmd_run(args) -> int:
    try:
        record = _run_once(args)
    except _INPUT_ERRORS as exc:
        print(f"run failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(record, indent=2, ensure_ascii=False))
        return 0
    _print_human(record)
    return 0


def _run_once(args) -> dict:
    if not args.registry:
        raise ValueError("run needs --registry so the witnessed assessment can be re-checked from disk")
    if bool(args.measurements) == bool(args.substrate):
        raise ValueError("run needs exactly one of --measurements or --substrate")
    paths = _output_paths(args)
    thesis = _resolve_thesis(args.thesis, args.registry)
    refutations = steelman_thesis(NullSteelman(), thesis)
    measurements = _measurements(thesis, args)
    assessment, verdicts = assess(thesis, measurements, clock=time.time, registry=Registry(args.registry))
    checks = _recheck_last(args.registry)
    if checks is None:
        raise ValueError(f"no assessment was recorded in registry {args.registry}")
    record = {
        "ok": all(checks.values()),
        "thesis": Registry._thesis_row(thesis),
        "refutations": [_refutation_dict(r) for r in refutations],
        "assessment": assessment.to_dict(),
        "verdicts": [_verdict_dict(v) for v in verdicts],
        "checks": checks,
        "report": paths["report"],
        "record": paths["record"],
        "bundle": paths["bundle"],
        "spec": paths["spec"],
        "review": paths["review"],
        "verifier": _verifier_contract(paths["bundle"]),
    }
    _write_outputs(paths, thesis, assessment, checks, record)
    return record


def _output_paths(args) -> dict[str, str | None]:
    if args.bundle and (args.report or args.out):
        raise ValueError("--bundle cannot be combined with --report or --out")
    if not args.bundle:
        return {"report": args.report, "record": args.out, "bundle": None, "spec": None, "review": None}
    if os.path.exists(args.bundle):
        raise FileExistsError(f"run bundle already exists: {args.bundle}")
    return {
        "report": os.path.join(args.bundle, "report.md"),
        "record": os.path.join(args.bundle, "run.json"),
        "bundle": args.bundle,
        "spec": os.path.join(args.bundle, "spec.json"),
        "review": os.path.join(args.bundle, "review.md"),
    }


def _write_outputs(paths: dict[str, str | None], thesis, assessment, checks: dict, record: dict) -> None:
    bundle = paths["bundle"]
    spec = paths["spec"]
    review = paths["review"]
    report = paths["report"]
    record_path = paths["record"]
    if bundle:
        os.makedirs(bundle)
    if spec:
        _write_spec(spec, thesis)
    if review:
        _write_review(review)
    if report:
        _write_report(report, thesis, assessment, checks)
    if record_path:
        _write_json(record_path, record)


def _measurements(thesis, args):
    if args.measurements:
        return _load_measurements(thesis, args.measurements)
    specs, substrate = _load_substrate(thesis, args.substrate)
    return measure_thesis(TableMeasure(specs, substrate), thesis)


def _verifier_contract(bundle: str | None) -> dict:
    return {
        "mode": "cleanroom",
        "inputs": ["spec.json", "run.json", "report.md"] if bundle else [],
        "excluded": ["worker context", "reasoning trace", "intermediate steps"],
        "checkability": (
            "If success cannot be evaluated from the original spec and the artifact, "
            "the spec is not checkable yet."
        ),
    }


def _write_spec(path: str, thesis) -> str:
    payload = {
        "id": thesis.id,
        "title": thesis.title,
        "disposition": thesis.disposition,
        "seal": thesis.seal,
        "claims": [
            {"id": c.id, "text": c.text, "falsification": c.falsification, "sha256": c.sha256}
            for c in thesis.claims
        ],
    }
    _write_json(path, payload)
    return path


def _write_review(path: str) -> str:
    lines = [
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
    ]
    with open(path, "x", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def _write_report(path: str, thesis, assessment, checks: dict) -> str:
    report = render_assessment_report(thesis, assessment, checks=checks)
    with open(path, "x", encoding="utf-8") as f:
        f.write(report)
    return path


def _write_json(path: str, record: dict) -> None:
    with open(path, "x", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _print_human(record: dict) -> None:
    a = record["assessment"]
    print(f'ran thesis {a["thesis_id"]}: {a["claims"]} claim(s)')
    print(f"  steelman refutations: {len(record['refutations'])}")
    print(f"  MATCH {a['match']}  DRIFT {a['drift']}  UNVERIFIABLE {a['unverifiable']}")
    print(f"  assessment seal: {a['seal'][:16]}...")
    print(f"  re-derived from disk: {all(record['checks'].values())}  {record['checks']}")
    if record["report"]:
        print(f"  report: {record['report']}")
