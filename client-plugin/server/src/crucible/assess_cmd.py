"""CLI command for a witnessed assessment (split from ``commands`` for the size budget), plus the
shared honesty wiring: pre-assessment ill-posed measurement warnings (typed, non-fatal unless
``--strict``) and per-claim missing-evidence explanations whenever a verdict is UNVERIFIABLE."""
from __future__ import annotations

import json
import sys
import time

from crucible.assess import assess, verify_assessment
from crucible.commands import (
    _INPUT_ERRORS,
    _load_measurements,
    _read_json,
    _recheck_last,
    _resolve_thesis,
    _verdict_dict,
)
from crucible.explain import explain_thesis, explanation_row
from crucible.registry import Registry
from crucible.wellposed import measurement_warnings, warning_row

STRICT_HELP = ("exit 1 when measurement rows are ill-posed (non-positive tolerance, untrusted "
               "deviation, boolean values, unbound or duplicate claim bindings)")


def measurement_warning_rows(thesis, path: str | None) -> list[dict]:
    """Typed warning rows for the raw measurement rows in FILE; [] when there is no file."""
    if not path:
        return []
    return [warning_row(w) for w in measurement_warnings(thesis, _read_json(path))]


def emit_warnings(rows: list[dict]) -> None:
    for row in rows:
        print(f"measurement warning: row {row['row']} claim {row['claim']!r}: "
              f"{row['detail']} [{row['code']}]", file=sys.stderr)


def strict_error(rows: list[dict]) -> ValueError:
    return ValueError(f"strict mode refuses {len(rows)} ill-posed measurement warning(s)")


def explanation_rows(thesis, measurements) -> list[dict]:
    """Typed missing-evidence rows for every UNVERIFIABLE claim in the assessment."""
    return [explanation_row(e) for e in explain_thesis(thesis, measurements)]


def print_evidence_needed(explanations: list[dict]) -> None:
    """The human evidence-request section; prints nothing when every claim verifies."""
    if not explanations:
        return
    print("  evidence needed:")
    for row in explanations:
        print(f"    {row['claim_id']:<16} missing {row['missing']}: {row['needed']}")


def cmd_assess(args) -> int:
    try:
        thesis = _resolve_thesis(args.thesis, args.registry)
        warnings = measurement_warning_rows(thesis, args.measurements)
        emit_warnings(warnings)
        if args.strict and warnings:
            raise strict_error(warnings)
        measurements = _load_measurements(thesis, args.measurements)
    except _INPUT_ERRORS as exc:
        print(f"assess failed: {exc}", file=sys.stderr)
        return 1
    registry = Registry(args.registry) if args.registry else None
    assessment, verdicts = assess(thesis, measurements, clock=time.time, registry=registry)
    explanations = explanation_rows(thesis, measurements)
    if args.json:
        print(json.dumps({"assessment": assessment.to_dict(),
                          "verdicts": [_verdict_dict(v) for v in verdicts],
                          "measurement_warnings": warnings,
                          "explanations": explanations}, indent=2, ensure_ascii=False))
        return 0
    print(f'assessed thesis {assessment.thesis_id} "{thesis.title}": {assessment.claims} claim(s)')
    print(f"  MATCH {assessment.match}  DRIFT {assessment.drift}  UNVERIFIABLE {assessment.unverifiable}")
    for v in verdicts:
        print(f"  {v.claim_id:<16} {v.status:<12} {v.grounds}")
    print_evidence_needed(explanations)
    print(f"assessment seal: {assessment.seal[:16]}... | self-consistent: {verify_assessment(assessment)}")
    if args.registry:
        check = _recheck_last(args.registry)
        if check is not None:
            print(f"re-derived from disk: {all(check.values())}  {check}")
        print(f"recorded to {args.registry}")
    return 0
