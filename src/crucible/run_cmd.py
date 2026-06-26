"""CLI command for one complete steelman -> measure -> assess -> report run."""
from __future__ import annotations

import json
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
    thesis = _resolve_thesis(args.thesis, args.registry)
    refutations = steelman_thesis(NullSteelman(), thesis)
    measurements = _measurements(thesis, args)
    assessment, verdicts = assess(thesis, measurements, clock=time.time, registry=Registry(args.registry))
    checks = _recheck_last(args.registry)
    if checks is None:
        raise ValueError(f"no assessment was recorded in registry {args.registry}")
    report = _write_report(args.report, thesis, assessment, checks) if args.report else None
    record = {
        "ok": all(checks.values()),
        "thesis": Registry._thesis_row(thesis),
        "refutations": [_refutation_dict(r) for r in refutations],
        "assessment": assessment.to_dict(),
        "verdicts": [_verdict_dict(v) for v in verdicts],
        "checks": checks,
        "report": report,
    }
    if args.out:
        _write_json(args.out, record)
    return record


def _measurements(thesis, args):
    if args.measurements:
        return _load_measurements(thesis, args.measurements)
    specs, substrate = _load_substrate(thesis, args.substrate)
    return measure_thesis(TableMeasure(specs, substrate), thesis)


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
