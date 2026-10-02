"""The ``ci`` command: a native CI regression gate over a registry's witnessed verdicts.

``crucible ci REGISTRY --write-baseline FILE`` captures the current verified-latest verdict per
(thesis, claim) as a sealed baseline. ``crucible ci REGISTRY --baseline FILE`` re-derives the current
verdicts, compares them against the baseline, prints a PR-comment-ready Markdown summary (or JSON with
``--json``), and exits nonzero if any claim regressed (MATCH -> DRIFT, a new UNVERIFIABLE, or a
baselined claim that lost its verified standing). The current snapshot is built from the same
``verified-latest`` reading the registry stats use, so the gate only ever compares standings that
re-derive from the record.
"""
from __future__ import annotations

import json
import sys

from crucible.ci_gate import (
    GateReport,
    Snapshot,
    cells_from_latest,
    gate,
    make_snapshot,
)
from crucible.ci_report import render_gate_markdown
from crucible.registry import Registry
from crucible.registry_ops import _verified_latest_by_thesis

_INPUT_ERRORS = (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError)


def cmd_ci(args) -> int:
    reg = Registry(args.dir)
    try:
        current = _current_snapshot(reg)
    except _INPUT_ERRORS as exc:
        print(f"ci failed: {exc}", file=sys.stderr)
        return 1
    if args.write_baseline:
        return _write_baseline(current, args.write_baseline)
    if not args.baseline:
        print("ci failed: pass --baseline FILE to gate, or --write-baseline FILE to capture one",
              file=sys.stderr)
        return 1
    try:
        baseline = _load_baseline(args.baseline)
    except _INPUT_ERRORS as exc:
        print(f"ci failed: {exc}", file=sys.stderr)
        return 1
    report = gate(baseline, current)
    return _emit(report, args)


def _current_snapshot(reg: Registry) -> Snapshot:
    latest, _invalid = _verified_latest_by_thesis(reg, list(reg.assessments()))
    return make_snapshot(cells_from_latest(latest))


def _write_baseline(current: Snapshot, path: str) -> int:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(current.to_dict(), f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    print(f"wrote baseline of {len(current.cells)} verdict cell(s) to {path} "
          f"(seal {current.seal[:12]}...)")
    return 0


def _load_baseline(path: str) -> Snapshot:
    with open(path, encoding="utf-8") as f:
        return Snapshot.from_dict(json.load(f))


def _emit(report: GateReport, args) -> int:
    code = 0 if report.passed else 1
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(render_gate_markdown(report))
        print(f"wrote gate summary to {args.out}")
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return code
    if not args.out:
        print(render_gate_markdown(report), end="")
    if code:
        drifted = ", ".join(f"{r.thesis_id}/{r.claim_id}" for r in report.regressions)
        print(f"ci gate failed: {len(report.regressions)} regression(s): {drifted}", file=sys.stderr)
    return code
