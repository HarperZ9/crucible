"""CLI command for oracle-level measurement recheck descriptors."""
from __future__ import annotations

import json
import sys
from collections.abc import Mapping

from crucible.assess import Assessment, recheck_assessment, recheck_measurements
from crucible.registry import Registry

_INPUT_ERRORS = (OSError, ValueError, KeyError, TypeError, IndexError, json.JSONDecodeError)


def cmd_recheck(args) -> int:
    try:
        if args.pack and args.template:
            raise ValueError("--template cannot be combined with --pack")
        payload = recheck_payload(args.dir, index=int(args.index), pack=args.pack)
        if args.template:
            _write_template(args.template, payload)
            print(f"wrote replay template to {args.template}")
            return 0
        if args.pack:
            if args.json:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                _print_replay(payload)
            return 0 if payload["ok"] else 1
        _emit_plan(payload, args.json)
        return 0
    except _INPUT_ERRORS as exc:
        print(f"recheck failed: {exc}", file=sys.stderr)
        return 1


def recheck_payload(registry_dir: str, *, index: int = -1, pack: str | None = None) -> dict:
    reg = Registry(registry_dir)
    assessment = _assessment_at(reg, int(index))
    thesis = reg.get_thesis(assessment.thesis_id)
    if thesis is None:
        raise ValueError(f"no thesis {assessment.thesis_id!r} in registry {registry_dir}")
    plan = recheck_plan(thesis, assessment)
    if pack is None:
        return plan
    replayers = _load_replay_pack(pack, plan["assessment"])
    checks = recheck_assessment(thesis, assessment)
    replay = recheck_measurements(assessment, replayers)
    checks["measurements_rerun"] = replay["ok"]
    return {"ok": all(checks.values()), "checks": checks, "replay": replay, "plan": plan}


def recheck_plan(thesis, assessment: Assessment) -> dict:
    claim_text = {c.id: c.text for c in thesis.claims}
    verdict_status = {str(v.get("claim_id", "")): v.get("status") for v in assessment.verdicts}
    descriptors = []
    skipped = 0
    for row in assessment.measurements:
        recheck = row.get("recheck")
        if not isinstance(recheck, Mapping):
            skipped += 1
            continue
        claim_id = str(row.get("claim_id", ""))
        descriptors.append({
            "claim_id": claim_id,
            "claim_sha256": row.get("claim_sha256", ""),
            "claim_text": claim_text.get(claim_id, claim_id),
            "status": verdict_status.get(claim_id, ""),
            "method": row.get("method", ""),
            "oracle": recheck.get("oracle", ""),
            "recheck": dict(recheck),
            "expected_measurement": _measurement_fields(row),
        })
    return {
        "assessment": {
            "thesis_id": assessment.thesis_id,
            "assessment_seal": assessment.seal,
            "measurement_seal": assessment.measurement_seal,
        },
        "summary": {"descriptors": len(descriptors), "skipped": skipped},
        "descriptors": descriptors,
    }


def _assessment_at(reg: Registry, index: int) -> Assessment:
    records = list(reg.assessments())
    if not records:
        raise ValueError("no assessments in registry")
    return Assessment.from_dict(records[index])


def _write_template(path: str, plan: dict) -> None:
    payload = {
        "assessment": plan["assessment"],
        "instructions": (
            "Fill each measurement object with the reproduced measurement row for its recheck "
            "descriptor, then pass this file to crucible recheck --pack."
        ),
        "replays": [_template_row(row) for row in plan["descriptors"]],
    }
    with open(path, "x", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _template_row(row: dict) -> dict:
    expected = row["expected_measurement"]
    return {
        "claim": {
            "id": row["claim_id"],
            "sha256": row["claim_sha256"],
            "text": row["claim_text"],
            "status": row["status"],
        },
        "recheck": row["recheck"],
        "expected_measurement": expected,
        "measurement": _blank_measurement(expected),
    }


def _measurement_fields(row: Mapping[str, object]) -> dict:
    return {
        "claim_id": row.get("claim_id", ""),
        "claim_sha256": row.get("claim_sha256", ""),
        "deviation": row.get("deviation"),
        "tolerance": row.get("tolerance"),
        "method": row.get("method", ""),
        "measured_at": row.get("measured_at"),
        "evidence": _evidence(row.get("evidence")),
    }


def _blank_measurement(expected: Mapping[str, object]) -> dict:
    return {
        "claim_id": expected.get("claim_id", ""),
        "claim_sha256": expected.get("claim_sha256", ""),
        "deviation": None,
        "tolerance": expected.get("tolerance"),
        "method": expected.get("method", ""),
        "measured_at": None,
        "evidence": [],
    }


def _evidence(value: object) -> list:
    if isinstance(value, list | tuple):
        return list(value)
    return [] if value in (None, "") else [value]




def _emit_plan(plan: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return
    summary = plan["summary"]
    seal = plan["assessment"]["assessment_seal"][:12]
    print(f"oracle recheck plan for {seal}...: {summary['descriptors']} descriptor(s), "
          f"{summary['skipped']} skipped")
    for row in plan["descriptors"]:
        print(f"  {row['claim_id']:<16} {row['oracle']} {row['method']} {row['status']}")


def _print_replay(result: dict) -> None:
    replay = result["replay"]
    status = "passed" if result["ok"] else "failed"
    print(f"oracle replay {status}: checked {replay['checked']}, skipped {replay['skipped']}, "
          f"missing {replay['missing']}, mismatched {replay['mismatched']}, failed {replay['failed']}")


def _load_replay_pack(path: str, expected_assessment: Mapping[str, object] | None = None) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("replay pack must be a JSON object")
    if expected_assessment is not None and "assessment" in data:
        _check_assessment_binding(data["assessment"], expected_assessment)
    rows = data.get("replays")
    if not isinstance(rows, list):
        raise ValueError("replay pack needs a 'replays' list")
    by_oracle: dict[str, dict[str, dict]] = {}
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f"replay row {index} must be an object")
        recheck = row.get("recheck")
        measurement = row.get("measurement")
        if not isinstance(recheck, dict) or not isinstance(measurement, dict):
            raise ValueError(f"replay row {index} needs object recheck and measurement")
        oracle = recheck.get("oracle")
        if not isinstance(oracle, str) or not oracle:
            raise ValueError(f"replay row {index} recheck needs a non-empty oracle")
        by_oracle.setdefault(oracle, {})[_canon(recheck)] = measurement
    return {oracle: _pack_replayer(rows_by_key) for oracle, rows_by_key in by_oracle.items()}


def _check_assessment_binding(value: object, expected: Mapping[str, object]) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("replay pack assessment must be an object")
    for key in ("thesis_id", "assessment_seal", "measurement_seal"):
        if value.get(key) != expected.get(key):
            raise ValueError(f"assessment binding mismatch for {key}")


def _pack_replayer(rows_by_key: Mapping[str, dict]):
    def replay(recheck: Mapping[str, object]) -> dict:
        return rows_by_key[_canon(recheck)]

    return replay


def _canon(value: Mapping[str, object]) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
