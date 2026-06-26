"""The ``refine`` command: drive the refine loop over an ordered list of substrate rounds.

A refine config is a thesis plus per-claim specs plus a list of ``rounds`` (each round a substrate of
observed values). The loop measures the thesis against each round in turn and stops as soon as a round
reaches a cohesively verified thesis (every claim within tolerance and the margins balanced), or, if no
round does, reports the weakest claim. This is the deterministic, file-expressible form of the loop;
the closed-loop ``refine_thesis`` (with a steering callback) is the library API for live discovery.

Read-only: refine reports an outcome, it does not write to a registry (use ``measure`` to witness a
specific round).
"""
from __future__ import annotations

import json
import math
import sys
import time

from crucible.commands import (
    _INPUT_ERRORS,
    _read_json,
    _resolve_thesis,
    _thesis_from_data,
    build_specs,
)
from crucible.measure import TableMeasure
from crucible.refine import refine_thesis


def _rounds(data: dict) -> list[dict]:
    rounds = data.get("rounds")
    if not isinstance(rounds, list) or not rounds:
        raise ValueError("refine config needs a non-empty 'rounds' list of substrates")
    return [{k: float(v) for k, v in r.items()} for r in rounds]


def _threshold(data: dict, key: str) -> float:
    try:
        value = float(data.get(key, 0.0))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a number") from exc
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{key} must be a finite number >= 0")
    return value


def cmd_refine(args) -> int:
    try:
        data = _read_json(args.config)
        thesis = (_resolve_thesis(args.thesis, args.registry) if args.thesis
                  else _thesis_from_data(data, clock=time.time))
        specs = build_specs(thesis, data.get("specs") or {})
        rounds = _rounds(data)
        target = _threshold(data, "target_margin")
        bar = _threshold(data, "cohesion_bar")
    except _INPUT_ERRORS as exc:
        print(f"refine failed: {exc}", file=sys.stderr)
        return 1

    def propose(state):
        idx = 0 if state is None else min(int(state), len(rounds) - 1)
        return TableMeasure(specs, rounds[idx])

    def adjust(_reflection, state):
        return (0 if state is None else int(state)) + 1

    report = refine_thesis(thesis, propose, adjust, target_margin=target, cohesion_bar=bar,
                           max_iter=len(rounds), clock=time.time)
    if args.json:
        print(json.dumps({
            "status": report.status, "iterations": report.iterations,
            "weakest_claim": report.weakest_claim, "cohesions": list(report.cohesions),
            "verdicts": [{"claim_id": v.claim_id, "status": v.status, "grounds": v.grounds}
                         for v in report.verdicts],
        }, indent=2, ensure_ascii=False))
        return 0 if report.status == "correct" else 1
    print(f'refined thesis "{thesis.title}" over {len(rounds)} round(s): {report.status} '
          f"after {report.iterations} iteration(s)")
    print(f"  cohesion trajectory: {[round(c, 4) for c in report.cohesions]}")
    if report.status == "correct":
        print("  reached a cohesively verified thesis (every claim within tolerance, margins balanced)")
    else:
        print(f"  weakest claim: {report.weakest_claim}")
    for v in report.verdicts:
        print(f"  {v.claim_id:<16} {v.status:<12} {v.grounds}")
    return 0 if report.status == "correct" else 1
