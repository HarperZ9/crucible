"""The ``drift`` command: compare witnessed assessments in a registry."""
from __future__ import annotations

import json
import sys

from crucible.assess import Assessment
from crucible.drift import drift_track
from crucible.registry import Registry

_INPUT_ERRORS = (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError)


def cmd_drift(args) -> int:
    reg = Registry(args.dir)
    try:
        records = list(reg.assessments())
    except _INPUT_ERRORS as exc:
        print(f"drift failed: {exc}", file=sys.stderr)
        return 1
    if len(records) < 2:
        print("drift failed: registry needs at least two assessments", file=sys.stderr)
        return 1
    previous = Assessment.from_dict(records[-2])
    current = Assessment.from_dict(records[-1])
    try:
        report = drift_track(previous, current)
    except ValueError as exc:
        print(f"drift failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return 0
    print(f"drift from {report.previous_seal[:12]}... to {report.current_seal[:12]}...")
    print("  " + "  ".join(f"{k} {v}" for k, v in report.summary.items()))
    for row in report.rows:
        before = row.previous_status or "absent"
        after = row.current_status or "absent"
        delta = "" if row.margin_delta is None else f"  delta {row.margin_delta:g}"
        print(f"  {row.claim_id:<16} {row.status:<9} {before} -> {after}{delta}")
    return 0
