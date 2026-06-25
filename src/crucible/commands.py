"""The command implementations behind the CLI surface (split from ``cli`` so neither module grows
past the size budget). Each command returns a process exit code: 0 on success, 1 on failure or a
registry integrity issue.
"""
from __future__ import annotations

import json
import os
import sys
import time

from crucible.assess import Assessment, assess, recheck_assessment, verify_assessment
from crucible.claim import make_claim
from crucible.measure import MetricSpec, TableMeasure, measure_thesis
from crucible.registry import Registry
from crucible.steelman import NullSteelman, Refutation, steelman_thesis
from crucible.thesis import PUBLISHABLE, Thesis, make_thesis
from crucible.verdict import Measurement, Verdict

_INPUT_ERRORS = (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError)


def _read_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _thesis_from_data(data: dict, *, clock) -> Thesis:
    raw = data.get("claims") or []
    if not raw:
        raise ValueError("thesis JSON needs a non-empty 'claims' list")
    claims = [make_claim(c["text"], c.get("falsification", ""), id=c.get("id")) for c in raw]
    return make_thesis(data.get("title", ""), claims, clock=clock, id=data.get("id"),
                       disposition=data.get("disposition", PUBLISHABLE))


def _as_float_or_none(x: object) -> float | None:
    if x is None:
        return None
    try:
        return float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None  # a non-numeric deviation is unmeasurable, so the verdict is UNVERIFIABLE


def _as_float(x: object, default: float) -> float:
    try:
        return float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default  # a non-numeric tolerance becomes 0.0, which verdict_for renders UNVERIFIABLE


def _load_measurements(thesis: Thesis, path: str | None) -> list[Measurement]:
    if not path:
        return []
    data = _read_json(path)
    by_id = {c.id: c for c in thesis.claims}
    by_text = {c.text: c for c in thesis.claims}
    out: list[Measurement] = []
    for m in data.get("measurements", []):
        ref = m.get("claim", "")
        claim = by_id.get(ref) or by_text.get(ref)
        if claim is None:
            raise ValueError(f"measurement references unknown claim {ref!r}")
        out.append(Measurement(claim.id, claim.sha256, _as_float_or_none(m.get("deviation")),
                               _as_float(m.get("tolerance"), 0.0), m.get("method", "manual"),
                               time.time(), tuple(m.get("evidence", ()))))
    return out


def _resolve_thesis(thesis_arg: str, registry: str | None) -> Thesis:
    if os.path.exists(thesis_arg):
        return _thesis_from_data(_read_json(thesis_arg), clock=time.time)
    if registry:
        t = Registry(registry).get_thesis(thesis_arg)
        if t is None:
            raise ValueError(f"no thesis {thesis_arg!r} in registry {registry}")
        return t
    raise ValueError(f"thesis {thesis_arg!r} is not a file and no --registry was given")


def _verdict_dict(v: Verdict) -> dict:
    return {"claim_id": v.claim_id, "claim_sha256": v.claim_sha256, "status": v.status,
            "deviation": v.deviation, "tolerance": v.tolerance, "margin": v.margin,
            "method": v.method, "grounds": v.grounds}


def _recheck_last(registry_dir: str) -> dict | None:
    """Reload the most recent assessment and its thesis from disk and re-derive its verdicts, so the
    CLI reports a real re-check, not a recompute of an in-memory record."""
    reg = Registry(registry_dir)
    records = list(reg.assessments())
    if not records:
        return None
    last = Assessment.from_dict(records[-1])
    try:
        thesis = reg.get_thesis(last.thesis_id)
    except _INPUT_ERRORS:
        thesis = None
    if thesis is None:
        return {"seals_ok": verify_assessment(last), "thesis_ok": False, "verdicts_rederive": False}
    return recheck_assessment(thesis, last)


def cmd_register(args) -> int:
    try:
        thesis = _thesis_from_data(_read_json(args.thesis), clock=time.time)
    except _INPUT_ERRORS as exc:
        print(f"register failed: {exc}", file=sys.stderr)
        return 1
    stored = Registry(args.registry).register(thesis) if args.registry else None
    if args.json:
        print(json.dumps({"thesis": Registry._thesis_row(thesis), "stored": stored},
                         indent=2, ensure_ascii=False))
        return 0
    where = f" to {args.registry}" if args.registry else ""
    extra = f" ({stored['added']} new, {stored['deduped']} deduped)" if stored else ""
    print(f'registered thesis {thesis.id} "{thesis.title}": {len(thesis.claims)} claim(s){extra}{where}')
    return 0


def cmd_assess(args) -> int:
    try:
        thesis = _resolve_thesis(args.thesis, args.registry)
        measurements = _load_measurements(thesis, args.measurements)
    except _INPUT_ERRORS as exc:
        print(f"assess failed: {exc}", file=sys.stderr)
        return 1
    registry = Registry(args.registry) if args.registry else None
    assessment, verdicts = assess(thesis, measurements, clock=time.time, registry=registry)
    if args.json:
        print(json.dumps({"assessment": assessment.to_dict(),
                          "verdicts": [_verdict_dict(v) for v in verdicts]}, indent=2, ensure_ascii=False))
        return 0
    print(f'assessed thesis {assessment.thesis_id} "{thesis.title}": {assessment.claims} claim(s)')
    print(f"  MATCH {assessment.match}  DRIFT {assessment.drift}  UNVERIFIABLE {assessment.unverifiable}")
    for v in verdicts:
        print(f"  {v.claim_id:<16} {v.status:<12} {v.grounds}")
    print(f"assessment seal: {assessment.seal[:16]}... | self-consistent: {verify_assessment(assessment)}")
    if args.registry:
        check = _recheck_last(args.registry)
        if check is not None:
            print(f"re-derived from disk: {all(check.values())}  {check}")
        print(f"recorded to {args.registry}")
    return 0


def _refutation_dict(r: Refutation) -> dict:
    return {"claim_id": r.claim_id, "claim_sha256": r.claim_sha256, "challenge": r.challenge,
            "measurable": r.measurable, "source": r.source}


def cmd_steelman(args) -> int:
    try:
        thesis = _resolve_thesis(args.thesis, args.registry)
    except _INPUT_ERRORS as exc:
        print(f"steelman failed: {exc}", file=sys.stderr)
        return 1
    refutations = steelman_thesis(NullSteelman(), thesis)
    if args.json:
        print(json.dumps({"thesis_id": thesis.id,
                          "refutations": [_refutation_dict(r) for r in refutations]},
                         indent=2, ensure_ascii=False))
        return 0
    print(f'steelmanned thesis {thesis.id} "{thesis.title}": {len(refutations)} refutation(s) from null')
    for r in refutations:
        test = r.measurable or "(no test: the claim is unfalsifiable)"
        print(f"  {r.claim_id:<16} {r.challenge}")
        print(f"  {'':<16} -> measure: {test}")
    return 0


def _load_substrate(thesis: Thesis, path: str) -> tuple[dict, dict]:
    """Load a measure substrate JSON: ``{specs: {claim: {predicted, tolerance, observe, metric}},
    substrate: {key: value}}``. Specs are resolved against the thesis by claim id or exact text.
    Returns ``(specs_by_claim_id, substrate)``."""
    data = _read_json(path)
    by_id = {c.id: c for c in thesis.claims}
    by_text = {c.text: c for c in thesis.claims}
    specs: dict[str, MetricSpec] = {}
    for ref, s in (data.get("specs") or {}).items():
        claim = by_id.get(ref) or by_text.get(ref)
        if claim is None:
            raise ValueError(f"spec references unknown claim {ref!r}")
        specs[claim.id] = MetricSpec(float(s["predicted"]), _as_float(s.get("tolerance"), 0.0),
                                     s.get("observe", ""), s.get("metric", "abs"))
    substrate = {k: float(v) for k, v in (data.get("substrate") or {}).items()}
    return specs, substrate


def cmd_measure(args) -> int:
    try:
        thesis = _resolve_thesis(args.thesis, args.registry)
        specs, substrate = _load_substrate(thesis, args.substrate)
    except _INPUT_ERRORS as exc:
        print(f"measure failed: {exc}", file=sys.stderr)
        return 1
    measurements = measure_thesis(TableMeasure(specs, substrate), thesis)
    registry = Registry(args.registry) if args.registry else None
    assessment, verdicts = assess(thesis, measurements, clock=time.time, registry=registry)
    if args.json:
        print(json.dumps({"assessment": assessment.to_dict(),
                          "verdicts": [_verdict_dict(v) for v in verdicts]}, indent=2, ensure_ascii=False))
        return 0
    print(f'measured thesis {assessment.thesis_id} "{thesis.title}" against the table oracle: '
          f"{assessment.claims} claim(s)")
    print(f"  MATCH {assessment.match}  DRIFT {assessment.drift}  UNVERIFIABLE {assessment.unverifiable}")
    for v in verdicts:
        print(f"  {v.claim_id:<16} {v.status:<12} {v.grounds}")
    print(f"assessment seal: {assessment.seal[:16]}... | self-consistent: {verify_assessment(assessment)}")
    if args.registry:
        print(f"recorded to {args.registry}")
    return 0
