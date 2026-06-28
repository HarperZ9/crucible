"""CLI command for verifying Telos creative measurement packets."""
from __future__ import annotations

import json
import sys

from crucible.commands import _INPUT_ERRORS, _read_json
from crucible.measurement_gate import verify_measurement_packet


def cmd_measurement_gate(args) -> int:
    try:
        packet = _read_json(args.packet)
        criteria = _criteria(args.criteria)
        result = verify_measurement_packet(packet, criteria=criteria)
    except _INPUT_ERRORS as exc:
        print(f"measurement-gate failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    print(
        "measurement-gate "
        f"{result['verification_verdict']} decision={result['decision_outcome']} "
        f"MATCH {result['summary']['MATCH']} DRIFT {result['summary']['DRIFT']} "
        f"UNVERIFIABLE {result['summary']['UNVERIFIABLE']}"
    )
    for row in result["rows"]:
        failure = f" {row['failure_code']}" if row["failure_code"] else ""
        print(f"  {row['layer_id']:<32} {row['verification_verdict']}{failure}")
    return 0


def _criteria(path: str | None) -> dict:
    if not path:
        return {}
    data = _read_json(path)
    if "criteria" in data:
        data = data["criteria"]
    if not isinstance(data, dict):
        raise ValueError("criteria must be a JSON object")
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            raise ValueError("criteria entries must map layer ids to objects")
    return data
