from __future__ import annotations

import json
import sys
import time
from typing import Any

from crucible import __version__
from crucible.assess import assess
from crucible.commands import _load_measurements, _read_json, _thesis_from_data, _verdict_dict
from crucible.flagship import doctor_payload, status_payload
from crucible.recheck_cmd import recheck_payload

MCP_PROTOCOL_VERSION = "2025-06-18"


def _ok(mid: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _err(mid: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def _text_result(text: str, *, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _tool_defs() -> list[dict]:
    return [
        {
            "name": "crucible.status",
            "description": "Emit Crucible's Project Telos operator-spine status envelope.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "crucible.doctor",
            "description": "Check Crucible's operator-spine readiness envelope.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "crucible.assess",
            "description": "Assess falsifiable claims against optional measurements and emit witnessed verdicts.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "thesis": {"type": "string", "description": "path to a thesis JSON file"},
                    "measurements": {
                        "type": "string",
                        "description": "optional path to a measurements JSON file",
                    },
                },
                "required": ["thesis"],
            },
        },
        {
            "name": "crucible.recheck",
            "description": "Inspect or replay oracle-level measurement descriptors from a Crucible registry.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "dir": {"type": "string", "description": "path to a Crucible registry directory"},
                    "index": {
                        "type": ["integer", "string"],
                        "description": "assessment index to inspect, default -1 for the latest",
                    },
                    "pack": {
                        "type": "string",
                        "description": "optional JSON replay pack with reproduced measurements",
                    },
                },
                "required": ["dir"],
            },
        },
    ]


def _assess_from_files(thesis_path: str, measurements_path: str | None) -> dict:
    thesis = _thesis_from_data(_read_json(thesis_path), clock=time.time)
    measurements = _load_measurements(thesis, measurements_path)
    assessment, verdicts = assess(thesis, measurements, clock=time.time)
    return {
        "assessment": assessment.to_dict(),
        "verdicts": [_verdict_dict(verdict) for verdict in verdicts],
    }


def call_tool(name: str, args: dict) -> str:
    if name == "crucible.status":
        return json.dumps(status_payload(), indent=2, sort_keys=True)
    if name == "crucible.doctor":
        return json.dumps(doctor_payload(), indent=2, sort_keys=True)
    if name == "crucible.assess":
        thesis = args.get("thesis")
        if not isinstance(thesis, str) or not thesis:
            raise ValueError("crucible.assess requires a non-empty thesis path")
        measurements = args.get("measurements")
        if measurements is not None and not isinstance(measurements, str):
            raise ValueError("measurements must be a path string when provided")
        return json.dumps(_assess_from_files(thesis, measurements), indent=2, ensure_ascii=False)
    if name == "crucible.recheck":
        registry_dir = args.get("dir")
        if not isinstance(registry_dir, str) or not registry_dir:
            raise ValueError("crucible.recheck requires a non-empty registry dir")
        index_value = args.get("index", -1)
        try:
            index = int(index_value)
        except (TypeError, ValueError) as exc:
            raise ValueError("index must be an integer") from exc
        pack = args.get("pack")
        if pack is not None and not isinstance(pack, str):
            raise ValueError("pack must be a path string when provided")
        return json.dumps(recheck_payload(registry_dir, index=index, pack=pack), indent=2, ensure_ascii=False)
    raise ValueError(f"unknown tool: {name}")


def handle_request(req: dict) -> dict | None:
    method = req.get("method")
    mid = req.get("id")

    if "id" not in req:
        return None
    if method == "initialize":
        return _ok(mid, {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "crucible", "version": __version__},
        })
    if method == "ping":
        return _ok(mid, {})
    if method == "tools/list":
        return _ok(mid, {"tools": _tool_defs()})
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        if not isinstance(name, str) or name not in {tool["name"] for tool in _tool_defs()}:
            return _err(mid, -32602, f"unknown tool: {name!r}")
        try:
            text = call_tool(name, params.get("arguments") or {})
            return _ok(mid, _text_result(text))
        except Exception as exc:
            return _ok(mid, _text_result(f"error: {exc}", is_error=True))
    return _err(mid, -32601, f"method not found: {method}")


def serve(stdin=None, stdout=None) -> int:
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            stdout.write(json.dumps(_err(None, -32700, "parse error")) + "\n")
            stdout.flush()
            continue
        response = handle_request(request)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()
    return 0
