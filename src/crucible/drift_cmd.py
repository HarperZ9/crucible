"""The ``drift`` command: compare witnessed assessments in a registry."""
from __future__ import annotations

import json
import sys

from crucible.assess import Assessment, recheck_assessment
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
    verified = _verified_assessments(reg, records)
    if len(verified) < 2:
        print("drift failed: registry needs at least two verified assessments", file=sys.stderr)
        return 1
    previous = verified[-2]
    current = verified[-1]
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


def _verified_assessments(reg: Registry, records: list[dict]) -> list[Assessment]:
    out: list[Assessment] = []
    for record in records:
        try:
            assessment = Assessment.from_dict(record)
            _require_integrity(reg, assessment)
        except _INPUT_ERRORS:
            continue
        out.append(assessment)
    return out


def _require_integrity(reg: Registry, assessment: Assessment) -> None:
    thesis = reg.get_thesis(assessment.thesis_id)
    if thesis is None:
        raise ValueError(f"assessment integrity failed: missing thesis {assessment.thesis_id!r}")
    checks = recheck_assessment(thesis, assessment)
    if not all(checks.values()):
        raise ValueError(f"assessment integrity failed for {assessment.seal}: {checks}")
