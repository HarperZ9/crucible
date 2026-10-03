"""MCP tool schemas and annotations for crucible's tools.

Kept apart from ``mcp_tools`` (which dispatches calls) so each file stays small.
"""
from __future__ import annotations


def _obj(properties: dict, required: list[str] | None = None) -> dict:
    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _path(description: str) -> dict:
    return {"type": "string", "description": description}


def _hints(title: str, *, read_only: bool, destructive: bool = False,
           idempotent: bool = False, open_world: bool = False) -> dict:
    return {"title": title, "readOnlyHint": read_only, "destructiveHint": destructive,
            "idempotentHint": idempotent, "openWorldHint": open_world}


# MCP tool annotations. A hint describes the tool to the client and is not a
# permission; launch grants and path confinement do the refusing.
ANNOTATIONS = {
    "crucible.status": _hints("Crucible status", read_only=True, idempotent=True),
    "crucible.doctor": _hints("Crucible readiness check", read_only=True, idempotent=True),
    "crucible.assess": _hints("Assess claims against evidence", read_only=True, idempotent=True),
    "crucible.recheck": _hints("Re-check recorded measurements", read_only=True, idempotent=True),
    "crucible.recheck_template": _hints("Build a replay template", read_only=True, idempotent=True),
    "crucible.run": _hints("Run and record an assessment", read_only=False),
    "crucible.measurement_gate": _hints("Verify a measurement packet", read_only=True,
                                        idempotent=True),
    "crucible.review": _hints("Validate a review bundle", read_only=True, idempotent=True),
    "crucible.report": _hints("Render an assessment report", read_only=False, idempotent=True),
    "crucible.batch": _hints("Assess a batch into a registry", read_only=False),
    "crucible.registry": _hints("List, verify or prune a registry", read_only=False,
                                destructive=True),
    "crucible.drift": _hints("Compare the latest assessments", read_only=True, idempotent=True),
    "crucible.refine": _hints("Run the refine loop", read_only=False),
    "crucible.verdicts": _hints("List or re-check verdicts", read_only=True, idempotent=True),
    "crucible.pairwise": _hints("Pairwise verdicts in both orders", read_only=True, idempotent=True),
    "crucible.decompose": _hints("Measure typed sub-questions", read_only=True, idempotent=True),
    "crucible.views": _hints("Summarize views, minorities kept", read_only=True, idempotent=True),
}


def annotate(tool: dict) -> dict:
    notes = dict(ANNOTATIONS[tool["name"]])
    return {**tool, "title": notes["title"], "annotations": notes}


def tool_defs() -> list[dict]:
    return [annotate(tool) for tool in _TOOLS]


_TOOLS: list[dict] = [
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
            "template": {"type": "boolean",
                         "description": "return a crucible.replay-template/1 object instead of a plan"},
        }, ["dir"]),
    },
    {
        "name": "crucible.recheck_template",
        "description": "Return a crucible.replay-template/1 object for descriptor-bearing rows in a registry assessment.",
        "inputSchema": _obj({
            "dir": _path("path to a Crucible registry directory"),
            "index": {"type": ["integer", "string"], "description": "assessment index, default -1"},
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
        "description": "Check a measurement packet JSON file against an optional criteria JSON file and "
                       "return a verdict for each measurement layer and an overall verdict.",
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
    {
        "name": "crucible.pairwise",
        "description": "Combine pairwise judgments recorded in both orders into A, B, TIE or "
                       "ORDER_DISAGREE per pair, with order-swap consistency and first-slot "
                       "preference rates and their Wilson intervals.",
        "inputSchema": _obj({"file": _path('JSON {"pairs": [{"id", "ab", "ba"}]}')}, ["file"]),
    },
    {
        "name": "crucible.decompose",
        "description": "Measure a claim's typed sub-questions (yesno, number, choice), combine "
                       "them demote-only, and name the single weakest sub-question.",
        "inputSchema": _obj({"file": _path("decomposed claim spec JSON with answers")}, ["file"]),
    },
    {
        "name": "crucible.views",
        "description": "Summarize views by position: the majority and every minority position "
                       "with its sources; optional planted positions are scored for survival.",
        "inputSchema": _obj({"file": _path('JSON {"views": [...], "planted"?: [...]}')}, ["file"]),
    },
]


def tool_names() -> set[str]:
    return {tool["name"] for tool in tool_defs()}
