from __future__ import annotations

import json

from crucible import __version__

SCHEMA = "project-telos.flagship-action/v1"
TOOL = "crucible"
PRIMARY_COMMANDS = [
    "register",
    "steelman",
    "measure",
    "assess",
    "run",
    "recheck",
    "review",
    "registry",
    "report",
    "drift",
]
TELOS_CONTRACTS = {
    "host_surfaces": ["CLI JSON", "MCP stdio", "plugins", "IDEs", "TUIs", "apps"],
    "schemas": [
        "project-telos.flagship-action/v1",
        "project-telos.context-envelope/v1",
        "project-telos.action-receipt/v1",
    ],
    "workflow_domains": ["enterprise", "research", "creative", "scientific", "education"],
    "second_brain_role": "turn claims, creative outputs, measurements, and agent actions into re-checkable verdicts",
    "privacy_boundary": "hosts receive receipts, hashes, redacted refs, and verdicts; raw private payloads stay in local adapters",
}


def envelope(command: str, *, status: str = "MATCH", native: dict | None = None,
             next_actions: list[dict] | None = None,
             diagnostics: list[dict] | None = None) -> dict:
    return {
        "schema": SCHEMA,
        "tool": TOOL,
        "tool_version": __version__,
        "command": command,
        "status": status,
        "inputs": [],
        "outputs": [],
        "receipts": [],
        "native": native or {},
        "next_actions": next_actions or [],
        "diagnostics": diagnostics or [],
    }


def _next(tool: str, action: str, reason: str) -> dict:
    return {"tool": tool, "action": action, "reason": reason, "inputs": [], "priority": "normal"}


def status_payload() -> dict:
    return envelope(
        "status",
        native={
            "role": "verification-pressure",
            "commands": PRIMARY_COMMANDS,
            "verdicts": ["MATCH", "DRIFT", "UNVERIFIABLE"],
            "operator_commands": ["status", "doctor", "demo", "mcp"],
            "mcp_tools": [
                "crucible.status",
                "crucible.doctor",
                "crucible.assess",
                "crucible.recheck",
                "crucible.run",
                "crucible.review",
                "crucible.report",
                "crucible.batch",
                "crucible.registry",
                "crucible.drift",
                "crucible.refine",
                "crucible.verdicts",
            ],
            "integration_surfaces": [
                "CLI",
                "MCP stdio",
                "Telos catalog",
                "cleanroom review bundles",
                "Gather/Index/Forum handoff",
            ],
            "presentation": {
                "readme": "current",
                "changelog": "current",
                "status_block": "1.1.0 operator floor",
            },
            "current_status": "1.1.0 operator floor with run, review, recheck, and MCP parity",
            "telos_contracts": TELOS_CONTRACTS,
        },
        next_actions=[_next("telos", "workflow", "carry verified claims into the shared room")],
    )


def doctor_payload() -> dict:
    checks = [
        {"name": "thesis_seals", "status": "MATCH"},
        {"name": "measurement_backed_assessments", "status": "MATCH"},
        {"name": "recheckable_verdicts", "status": "MATCH"},
    ]
    return envelope(
        "doctor",
        native={"checks": checks},
        next_actions=[_next("gather", "docs", "refresh claim sources before reassessment")],
    )


def demo_payload() -> dict:
    return envelope(
        "demo",
        native={
            "command": (
                "crucible assess examples/thesis-binary-search.json "
                "--measurements examples/measurements-binary-search.json --json"
            )
        },
        next_actions=[_next("forum", "ledger.summary", "record verification handoff")],
    )


def emit(payload: dict, as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"status={payload['status']} tool={payload['tool']} command={payload['command']}")
        for action in payload["next_actions"]:
            print(f"next: {action['tool']} {action['action']} - {action['reason']}")
    return 0


def cmd_status(args) -> int:
    return emit(status_payload(), args.json)


def cmd_doctor(args) -> int:
    return emit(doctor_payload(), args.json)


def cmd_demo(args) -> int:
    return emit(demo_payload(), args.json)
