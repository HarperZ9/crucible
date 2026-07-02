from __future__ import annotations

import json
import time
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

from crucible.assess import assess
from crucible.assess_cmd import explanation_rows, measurement_warning_rows, strict_error
from crucible.commands import (
    _load_measurements,
    _read_json,
    _thesis_from_data,
    _verdict_dict,
)
from crucible.flagship import doctor_payload, status_payload
from crucible.measurement_gate import verify_measurement_packet
from crucible.measurement_gate_cmd import _criteria
from crucible.recheck_cmd import recheck_payload


def _obj(properties: dict, required: list[str] | None = None) -> dict:
    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _path(description: str) -> dict:
    return {"type": "string", "description": description}


def tool_defs() -> list[dict]:
    return [
        {
            "name": "crucible.status",
            "description": "Emit Crucible's Project Telos operator-spine status envelope.",
            "inputSchema": _obj({}),
        },
        {
            "name": "crucible.doctor",
            "description": "Check Crucible's operator-spine readiness envelope.",
            "inputSchema": _obj({}),
        },
        {
            "name": "crucible.assess",
            "description": "Assess falsifiable claims against optional measurements and emit witnessed "
                           "verdicts, ill-posed measurement warnings, and missing-evidence explanations "
                           "for UNVERIFIABLE claims.",
            "inputSchema": _obj({
                "thesis": _path("path to a thesis JSON file"),
                "measurements": _path("optional path to a measurements JSON file"),
                "strict": {"type": "boolean",
                           "description": "error when measurement rows are ill-posed"},
            }, ["thesis"]),
        },
        {
            "name": "crucible.recheck",
            "description": "Inspect or replay oracle-level measurement descriptors from a Crucible registry.",
            "inputSchema": _obj({
                "dir": _path("path to a Crucible registry directory"),
                "index": {"type": ["integer", "string"], "description": "assessment index, default -1"},
                "pack": _path("optional JSON replay pack with reproduced measurements"),
            }, ["dir"]),
        },
        {
            "name": "crucible.run",
            "description": "Run steelman, measurement, assessment, disk recheck, and optional packet writes.",
            "inputSchema": _obj({
                "thesis": _path("path to a thesis JSON file or registry thesis id"),
                "registry": _path("registry directory to record and re-check the assessment"),
                "measurements": _path("path to measurements JSON; exclusive with substrate"),
                "substrate": _path("path to substrate JSON; exclusive with measurements"),
                "report": _path("optional Markdown report output path"),
                "out": _path("optional JSON run-record output path"),
                "bundle": _path("optional cleanroom review packet directory"),
            }, ["thesis", "registry"]),
        },
        {
            "name": "crucible.measurement_gate",
            "description": "Verify Telos creative/rendering measurement packets against explicit criteria.",
            "inputSchema": _obj({
                "packet": _path("path to a project-telos.measurement-layers/v1 JSON packet"),
                "criteria": _path("optional JSON criteria keyed by measurement layer id"),
            }, ["packet"]),
        },
        {
            "name": "crucible.review",
            "description": "Validate a cleanroom review bundle before verifier handoff.",
            "inputSchema": _obj({"bundle": _path("bundle directory created by crucible.run")}, ["bundle"]),
        },
        {
            "name": "crucible.report",
            "description": "Render a Markdown report for a witnessed assessment in a registry.",
            "inputSchema": _obj({
                "dir": _path("registry directory"),
                "index": {"type": ["integer", "string"], "description": "assessment index, default -1"},
                "out": _path("optional Markdown output path"),
            }, ["dir"]),
        },
        {
            "name": "crucible.batch",
            "description": "Assess a manifest of thesis jobs into a registry.",
            "inputSchema": _obj({
                "manifest": _path("batch manifest JSON"),
                "registry": _path("registry directory"),
                "reports": _path("optional directory for per-job Markdown reports"),
            }, ["manifest", "registry"]),
        },
        {
            "name": "crucible.registry",
            "description": "List, verify, summarize, search, or prune a Crucible registry.",
            "inputSchema": _obj({
                "action": {"type": "string", "enum": ["list", "verify", "stats", "search", "prune"]},
                "dir": _path("registry directory"),
                "query": {"type": "string", "description": "optional search query"},
                "status": {"type": "string", "enum": ["publishable", "fenced"]},
                "verdict": {"type": "string", "enum": ["MATCH", "DRIFT", "UNVERIFIABLE"]},
                "apply": {"type": "boolean", "description": "apply registry prune deletions"},
            }, ["action", "dir"]),
        },
        {
            "name": "crucible.drift",
            "description": "Compare the latest two verified assessments in a registry.",
            "inputSchema": _obj({"dir": _path("registry directory")}, ["dir"]),
        },
        {
            "name": "crucible.refine",
            "description": "Run the deterministic refine loop over a substrate-round config.",
            "inputSchema": _obj({
                "config": _path("refine config JSON"),
                "thesis": _path("optional thesis file or registry id override"),
                "registry": _path("optional registry directory for thesis id resolution"),
            }, ["config"]),
        },
        {
            "name": "crucible.verdicts",
            "description": "List or re-check witnessed assessments in a registry.",
            "inputSchema": _obj({
                "dir": _path("registry directory"),
                "verify": {"type": "boolean", "description": "re-derive verdicts from stored thesis and measurements"},
            }, ["dir"]),
        },
    ]


def tool_names() -> set[str]:
    return {tool["name"] for tool in tool_defs()}


def _require_str(args: dict, name: str) -> str:
    value = args.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _optional_str(args: dict, name: str) -> str | None:
    value = args.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string when provided")
    return value


def _append_optional(argv: list[str], args: dict, name: str, flag: str | None = None) -> None:
    value = _optional_str(args, name)
    if value is not None:
        argv.extend([flag or f"--{name}", value])


def _invoke_cli(argv: list[str]) -> str:
    from crucible.cli import main

    out = StringIO()
    err = StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            code = main(argv)
    except SystemExit as exc:
        raw_code = exc.code if isinstance(exc.code, int) else 1
        code = raw_code or 0
    text = out.getvalue().strip()
    errors = err.getvalue().strip()
    if code != 0 and not text:
        raise ValueError(errors or f"crucible {' '.join(argv)} exited {code}")
    return text or json.dumps({"ok": code == 0, "stderr": errors}, indent=2)


def _assess_from_files(thesis_path: str, measurements_path: str | None, *, strict: bool = False) -> dict:
    thesis = _thesis_from_data(_read_json(thesis_path), clock=time.time)
    warnings = measurement_warning_rows(thesis, measurements_path)
    if strict and warnings:
        raise strict_error(warnings)
    measurements = _load_measurements(thesis, measurements_path)
    assessment, verdicts = assess(thesis, measurements, clock=time.time)
    return {
        "assessment": assessment.to_dict(),
        "verdicts": [_verdict_dict(verdict) for verdict in verdicts],
        "measurement_warnings": warnings,
        "explanations": explanation_rows(thesis, measurements),
    }


def _run_tool(args: dict) -> str:
    measurements = _optional_str(args, "measurements")
    substrate = _optional_str(args, "substrate")
    if bool(measurements) == bool(substrate):
        raise ValueError("crucible.run needs exactly one of measurements or substrate")
    argv = ["run", _require_str(args, "thesis"), "--registry", _require_str(args, "registry"), "--json"]
    if measurements:
        argv.extend(["--measurements", measurements])
    if substrate:
        argv.extend(["--substrate", substrate])
    _append_optional(argv, args, "report")
    _append_optional(argv, args, "out")
    _append_optional(argv, args, "bundle")
    return _invoke_cli(argv)


def _measurement_gate_tool(args: dict) -> str:
    packet = _read_json(_require_str(args, "packet"))
    criteria = _criteria(_optional_str(args, "criteria"))
    return json.dumps(verify_measurement_packet(packet, criteria=criteria), indent=2, ensure_ascii=False)


def _registry_tool(args: dict) -> str:
    action = _require_str(args, "action")
    if action not in {"list", "verify", "stats", "search", "prune"}:
        raise ValueError(f"unsupported registry action: {action}")
    argv = ["registry", action, _require_str(args, "dir")]
    query = _optional_str(args, "query")
    if query is not None:
        argv.append(query)
    _append_optional(argv, args, "status")
    _append_optional(argv, args, "verdict")
    if args.get("apply") is True:
        argv.append("--apply")
    argv.append("--json")
    return _invoke_cli(argv)


def call_tool(name: str, args: dict) -> str:
    if name == "crucible.status":
        return json.dumps(status_payload(), indent=2, sort_keys=True)
    if name == "crucible.doctor":
        return json.dumps(doctor_payload(), indent=2, sort_keys=True)
    if name == "crucible.assess":
        thesis = _require_str(args, "thesis")
        measurements = _optional_str(args, "measurements")
        payload = _assess_from_files(thesis, measurements, strict=args.get("strict") is True)
        return json.dumps(payload, indent=2, ensure_ascii=False)
    if name == "crucible.recheck":
        index_value = args.get("index", -1)
        try:
            index = int(index_value)
        except (TypeError, ValueError) as exc:
            raise ValueError("index must be an integer") from exc
        return json.dumps(
            recheck_payload(_require_str(args, "dir"), index=index, pack=_optional_str(args, "pack")),
            indent=2,
            ensure_ascii=False,
        )
    if name == "crucible.run":
        return _run_tool(args)
    if name == "crucible.measurement_gate":
        return _measurement_gate_tool(args)
    if name == "crucible.review":
        return _invoke_cli(["review", _require_str(args, "bundle"), "--json"])
    if name == "crucible.report":
        argv = ["report", _require_str(args, "dir")]
        if "index" in args:
            argv.extend(["--index", str(args["index"])])
        _append_optional(argv, args, "out")
        return _invoke_cli(argv)
    if name == "crucible.batch":
        argv = ["batch", _require_str(args, "manifest"), "--registry", _require_str(args, "registry"), "--json"]
        _append_optional(argv, args, "reports")
        return _invoke_cli(argv)
    if name == "crucible.registry":
        return _registry_tool(args)
    if name == "crucible.drift":
        return _invoke_cli(["drift", _require_str(args, "dir"), "--json"])
    if name == "crucible.refine":
        argv = ["refine", _require_str(args, "config"), "--json"]
        _append_optional(argv, args, "thesis")
        _append_optional(argv, args, "registry")
        return _invoke_cli(argv)
    if name == "crucible.verdicts":
        argv = ["verdicts", _require_str(args, "dir"), "--json"]
        if args.get("verify") is True:
            argv.append("--verify")
        return _invoke_cli(argv)
    raise ValueError(f"unknown tool: {name}")
