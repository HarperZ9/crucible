"""Explicit launch-time oracle grant using Crucible's bounded measurement edge.

The approved child is trusted executable code with OS user permissions. It can
write files and access the network; Python audit hooks are not an OS sandbox.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


def launch_command(allow_process: bool, raw: str | None) -> tuple[str, ...] | None:
    if not allow_process and raw is None:
        return None
    if not allow_process or raw is None:
        raise ValueError("--allow-process and --measure-command must be supplied together")
    try:
        command = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("measurement command must be a JSON argv array") from exc
    if not isinstance(command, list) or not command or any(
            not isinstance(part, str) or not part or chr(0) in part for part in command):
        raise ValueError("measurement command must be a non-empty JSON argv array")
    if command[0].replace(chr(92), "/").startswith("//"):
        raise ValueError("measurement executable must be local")
    executable = Path(command[0])
    if not executable.is_absolute() or not executable.is_file():
        raise ValueError("measurement executable must be an existing absolute file")
    return tuple(command)


def definition():
    notes = {"title": "Measure claims with the approved oracle", "readOnlyHint": False,
             "destructiveHint": False, "idempotentHint": False, "openWorldHint": True}
    return {"name": "crucible.benchmark", "title": notes["title"], "annotations": notes,
            "description": "Measure up to 16 local claims using only the oracle approved at server launch. "
                           "Returns witnessed assessment; does not prove oracle correctness.",
            "inputSchema": {"type": "object", "properties": {"thesis": {
                "type": "string", "description": "Workspace-local thesis JSON file"}},
                "required": ["thesis"], "additionalProperties": False}}


def benchmark(thesis_path, root, command):
    from crucible.assess import _measurement_row, assess
    from crucible.commands import _read_json, _thesis_from_data, _verdict_dict
    from crucible.subprocess_edges import SubprocessMeasure

    thesis = _thesis_from_data(_read_json(thesis_path), clock=time.time)
    if len(thesis.claims) > 16:
        raise ValueError("local benchmark supports at most 16 claims per request")
    # No API keys, endpoint configuration, Python hooks or ambient permission
    # variables reach the child. Absolute executable avoids PATH lookup.
    env = {key: value for key, value in os.environ.items()
           if key.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP"}}
    oracle = SubprocessMeasure(command, name="launch-approved-oracle", cwd=str(root),
                               env=env, timeout=10.0, max_output_bytes=65_536)
    measurements = tuple(oracle.measure(claim) for claim in thesis.claims)
    assessment, verdicts = assess(thesis, measurements)
    return json.dumps({"assessment": assessment.to_dict(),
                       "verdicts": [_verdict_dict(v) for v in verdicts],
                       "measurements": [_measurement_row(m) for m in measurements],
                       "limits": "Approved child has OS user permissions; no OS sandbox. "
                                 "A valid receipt does not establish oracle correctness."})
