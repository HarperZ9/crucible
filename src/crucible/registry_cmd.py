"""The registry-inspecting commands (split from ``commands`` so neither module grows past the size
budget): ``registry list|verify`` and ``verdicts [--verify]``. Each returns a process exit code: 0 on
success, 1 on failure or an integrity issue.
"""
from __future__ import annotations

import json
import sys

from crucible.assess import Assessment, recheck_assessment, verify_assessment
from crucible.registry import MATCH, Registry

_INPUT_ERRORS = (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError)


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
    bodies = reg.verify()
    seals = reg.verify_seals()
    bad_b = [r for r in bodies if r["status"] != MATCH]
    bad_s = [r for r in seals if r["status"] != MATCH]
    ok = not bad_b and not bad_s
    if as_json:
        print(json.dumps({"bodies": bodies, "seals": seals, "ok": ok}, indent=2, ensure_ascii=False))
        return 0 if ok else 1
    print(f"bodies: {len(bodies) - len(bad_b)}/{len(bodies)} MATCH; "
          f"theses: {len(seals) - len(bad_s)}/{len(seals)} seal MATCH")
    for r in bad_b:
        print(f"  body  {r['thesis_id']:<16} {r['claim_id']:<16} {r['status']}")
    for r in bad_s:
        print(f"  seal  {r['thesis_id']:<16} {r['status']}")
    return 0 if ok else 1


def cmd_verdicts(args) -> int:
    reg = Registry(args.dir)
    try:
        records = list(reg.assessments())
    except _INPUT_ERRORS as exc:
        print(f"verdicts failed: {exc}", file=sys.stderr)
        return 1
    if args.verify:
        return _verdicts_verify(reg, records, args.json)
    return _verdicts_list(records, args.json)


def _verdicts_list(records: list[dict], as_json: bool) -> int:
    if as_json:
        print(json.dumps(records, indent=2, ensure_ascii=False))
        return 0
    print(f"{len(records)} assessment(s)")
    for d in records:
        print(f"  {d.get('thesis_id', ''):<16} MATCH {d.get('match', 0)} DRIFT {d.get('drift', 0)} "
              f"UNVERIFIABLE {d.get('unverifiable', 0)}  seal {str(d.get('seal', ''))[:12]}...")
    return 0


def _verdicts_verify(reg: Registry, records: list[dict], as_json: bool) -> int:
    results = []
    for d in records:
        a = Assessment.from_dict(d)
        try:
            thesis = reg.get_thesis(a.thesis_id)
        except _INPUT_ERRORS:
            thesis = None
        checks = (recheck_assessment(thesis, a) if thesis is not None
                  else {"seals_ok": verify_assessment(a), "thesis_ok": False, "verdicts_rederive": False})
        results.append({"thesis_id": a.thesis_id, "seal": a.seal, "ok": all(checks.values()), **checks})
    bad = [r for r in results if not r["ok"]]
    if as_json:
        print(json.dumps({"results": results, "ok": not bad}, indent=2, ensure_ascii=False))
        return 0 if not bad else 1
    print(f"re-checked {len(results)} assessment(s): {len(results) - len(bad)} ok, {len(bad)} not")
    for r in results:
        print(f"  {r['thesis_id']:<16} ok={r['ok']}  seals={r['seals_ok']} "
              f"thesis={r['thesis_ok']} rederive={r['verdicts_rederive']}")
    return 0 if not bad else 1
