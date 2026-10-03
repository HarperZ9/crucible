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
from crucible.mcp_schema import (  # noqa: F401
    ANNOTATIONS,
    annotate,
    tool_defs,
    tool_names,
)
from crucible.measurement_gate import verify_measurement_packet
from crucible.measurement_gate_cmd import _criteria
from crucible.recheck_cmd import recheck_payload, replay_template_payload


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


def _optional_bool(args: dict, name: str) -> bool | None:
    value = args.get(name)
    if value is None:
        return None
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean when provided")
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


def _recheck_tool(name: str, args: dict) -> str:
    index_value = args.get("index", -1)
    try:
        index = int(index_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("index must be an integer") from exc
    template = _optional_bool(args, "template")
    if name == "crucible.recheck_template" or template is True:
        if _optional_str(args, "pack") is not None:
            raise ValueError("template cannot be combined with pack")
        payload = replay_template_payload(
            recheck_payload(_require_str(args, "dir"), index=index)
        )
    else:
        payload = recheck_payload(
            _require_str(args, "dir"),
            index=index,
            pack=_optional_str(args, "pack"),
        )
    return json.dumps(payload, indent=2, ensure_ascii=False)


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
    if name in {"crucible.recheck", "crucible.recheck_template"}:
        return _recheck_tool(name, args)
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
    if name in {"crucible.pairwise", "crucible.decompose", "crucible.views"}:
        return _invoke_cli([name.split(".", 1)[1], _require_str(args, "file"), "--json"])
    raise ValueError(f"unknown tool: {name}")
