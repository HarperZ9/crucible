"""The command implementations behind the CLI surface (split from ``cli`` so neither module grows
past the size budget). Each command returns a process exit code: 0 on success, 1 on failure or a
registry integrity issue.
"""
from __future__ import annotations

import json
import os
import sys
import time

from crucible.assess import assess, verify_assessment
from crucible.claim import make_claim
from crucible.registry import MATCH, Registry
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
                               float(m.get("tolerance", 0.0)), m.get("method", "manual"),
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
                          "verdicts": [_verdict_dict(v) for v in verdicts]},
                         indent=2, ensure_ascii=False))
        return 0
    print(f'assessed thesis {assessment.thesis_id} "{thesis.title}": {assessment.claims} claim(s)')
    print(f"  MATCH {assessment.match}  DRIFT {assessment.drift}  UNVERIFIABLE {assessment.unverifiable}")
    for v in verdicts:
        print(f"  {v.claim_id:<16} {v.status:<12} {v.grounds}")
    print(f"assessment seal: {assessment.seal[:16]}... | verified: {verify_assessment(assessment)}")
    if args.registry:
        print(f"recorded to {args.registry}")
    return 0


def cmd_registry(args) -> int:
    reg = Registry(args.dir)
    try:
        if args.action == "list":
            return _registry_list(reg, args.json)
        return _registry_verify(reg, args.json)
    except _INPUT_ERRORS as exc:
        print(f"registry {args.action} failed: {exc}", file=sys.stderr)
        return 1


def _registry_list(reg: Registry, as_json: bool) -> int:
    rows = list(reg.theses())
    if as_json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0
    print(f"{len(rows)} thesis(es)")
    for r in rows:
        n = len(r.get("claims", []))
        print(f"  {r.get('id', ''):<16} {n:>3} claim(s)  {r.get('disposition', ''):<11} "
              f"{r.get('title', '')[:50]}")
    return 0


def _registry_verify(reg: Registry, as_json: bool) -> int:
    results = reg.verify()
    bad = [r for r in results if r["status"] != MATCH]
    if as_json:
        print(json.dumps({"results": results, "ok": not bad}, indent=2, ensure_ascii=False))
        return 0 if not bad else 1
    print(f"verified {len(results)} claim(s): {len(results) - len(bad)} MATCH, {len(bad)} not")
    for r in bad:
        print(f"  {r['thesis_id']:<16} {r['claim_id']:<16} {r['status']}")
    return 0 if not bad else 1
