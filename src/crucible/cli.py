"""The ``crucible`` command: an argument surface over the judgment organ.

``register``, ``assess``, and ``steelman`` work on a thesis (a JSON file, or an id with
``--registry``); ``registry list|verify|stats|search|prune`` and ``verdicts [--verify]`` inspect a
stored registry. Each subcommand binds a handler from ``crucible.commands`` via
``set_defaults(func=...)``; ``main`` dispatches to it. Output is human text by default, JSON with
``--json``.
"""
from __future__ import annotations

import argparse

from crucible import __version__
from crucible.batch_cmd import cmd_batch
from crucible.commands import (
    cmd_assess,
    cmd_export,
    cmd_measure,
    cmd_register,
    cmd_steelman,
)
from crucible.drift_cmd import cmd_drift
from crucible.flagship import cmd_demo, cmd_doctor, cmd_status
from crucible.mcp import serve as serve_mcp
from crucible.measurement_gate_cmd import cmd_measurement_gate
from crucible.recheck_cmd import cmd_recheck
from crucible.refine_cmd import cmd_refine
from crucible.registry_cmd import cmd_registry, cmd_verdicts
from crucible.report_cmd import cmd_report
from crucible.review_cmd import cmd_review
from crucible.run_cmd import cmd_run


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--registry", default=None, metavar="DIR",
                   help="register/record into a content-addressed registry at DIR")
    p.add_argument("--json", action="store_true", help="emit JSON instead of human text")


def _add_flagship_commands(sub) -> None:
    status = sub.add_parser("status", help="emit Crucible's Project Telos operator-spine status")
    status.add_argument("--json", action="store_true", help="emit a Project Telos action envelope")
    status.set_defaults(func=cmd_status)

    doctor = sub.add_parser("doctor", help="check Crucible's operator-spine readiness")
    doctor.add_argument("--json", action="store_true", help="emit a Project Telos action envelope")
    doctor.set_defaults(func=cmd_doctor)

    demo = sub.add_parser("demo", help="show Crucible's operator-spine demo command")
    demo.add_argument("--json", action="store_true", help="emit a Project Telos action envelope")
    demo.set_defaults(func=cmd_demo)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crucible", description="crucible: accountable judgment of ideas.")
    parser.add_argument("--version", action="version", version=f"crucible {__version__}")
    sub = parser.add_subparsers(dest="command")
    _add_flagship_commands(sub)
    _add_core_commands(sub)
    _add_refine_command(sub)
    _add_registry_commands(sub)
    _add_recheck_command(sub)
    _add_review_command(sub)
    _add_artifact_commands(sub)
    mcp = sub.add_parser("mcp", help="serve Crucible tools over MCP stdio")
    mcp.set_defaults(func=lambda _args: serve_mcp())
    return parser


def _add_core_commands(sub) -> None:
    reg = sub.add_parser("register", help="register a thesis (claims + falsification) into a registry")
    reg.add_argument("thesis", help="path to a thesis JSON")
    _add_common(reg)
    reg.set_defaults(func=cmd_register)

    exp = sub.add_parser("export", help="publication-gated export of a thesis contract")
    exp.add_argument("thesis", help="path to a thesis JSON, or a thesis id when --registry is given")
    exp.add_argument("--registry", default=None, metavar="DIR", help="resolve a thesis id from a registry at DIR")
    exp.set_defaults(func=cmd_export)

    ass = sub.add_parser("assess", help="compute and witness a verdict per claim (MATCH/DRIFT/UNVERIFIABLE)")
    ass.add_argument("thesis", help="path to a thesis JSON, or a thesis id when --registry is given")
    ass.add_argument("--measurements", default=None, metavar="FILE",
                     help="path to a measurements JSON; a claim with no measurement is UNVERIFIABLE")
    _add_common(ass)
    ass.set_defaults(func=cmd_assess)

    stl = sub.add_parser("steelman",
                         help="propose the test that would settle each claim (the null default restates the "
                              "claim's own falsification; custom edges plug in through the API)")
    stl.add_argument("thesis", help="path to a thesis JSON, or a thesis id when --registry is given")
    stl.add_argument("--registry", default=None, metavar="DIR", help="resolve a thesis id from a registry at DIR")
    stl.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    stl.set_defaults(func=cmd_steelman)

    mea = sub.add_parser("measure",
                         help="measure each claim against a substrate oracle, then witness the verdicts")
    mea.add_argument("thesis", help="path to a thesis JSON, or a thesis id when --registry is given")
    mea.add_argument("--substrate", required=True, metavar="FILE",
                     help="path to a substrate JSON: per-claim specs (predicted, tolerance, observe) plus observed values")
    _add_common(mea)
    mea.set_defaults(func=cmd_measure)

    run = sub.add_parser("run", help="run a complete steelman, measurement, witnessed assessment, and optional report")
    run.add_argument("thesis", help="path to a thesis JSON, or a thesis id when --registry is given")
    run.add_argument("--measurements", default=None, metavar="FILE",
                     help="path to a measurements JSON; exclusive with --substrate")
    run.add_argument("--substrate", default=None, metavar="FILE",
                     help="path to a substrate JSON; exclusive with --measurements")
    run.add_argument("--registry", default=None, metavar="DIR",
                     help="record and re-check the witnessed assessment in registry DIR")
    run.add_argument("--report", default=None, metavar="FILE",
                     help="write a Markdown report for this run")
    run.add_argument("--out", default=None, metavar="FILE",
                     help="write the JSON run record to FILE")
    run.add_argument("--bundle", default=None, metavar="DIR",
                     help="create DIR with spec.json, run.json, report.md, and review.md")
    run.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    run.set_defaults(func=cmd_run)

    gate = sub.add_parser("measurement-gate", help="verify a Telos creative measurement packet")
    gate.add_argument("packet", help="path to a project-telos.measurement-layers/v1 JSON packet")
    gate.add_argument("--criteria", default=None, metavar="FILE",
                      help="optional JSON criteria keyed by measurement layer id")
    gate.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    gate.set_defaults(func=cmd_measurement_gate)


def _add_refine_command(sub) -> None:
    ref = sub.add_parser("refine",
                         help="refine over rounds of substrate until the thesis is cohesively verified, or report the weakest claim")
    ref.add_argument("config", help="path to a refine config JSON (claims or a thesis, specs, rounds, target_margin, cohesion_bar)")
    ref.add_argument("--thesis", default=None,
                     help="resolve the thesis from a file or a registry id instead of the config's own claims")
    ref.add_argument("--registry", default=None, metavar="DIR", help="resolve a thesis id from a registry at DIR")
    ref.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    ref.set_defaults(func=cmd_refine)


def _add_registry_commands(sub) -> None:
    rgy = sub.add_parser("registry", help="inspect a stored registry: list, verify, stats, search, or prune")
    rgy.add_argument("action", choices=["list", "verify", "stats", "search", "prune"],
                     help="list, verify, summarize, search, or prune claim objects")
    rgy.add_argument("dir", help="the registry directory (created by --registry)")
    rgy.add_argument("query", nargs="?", help="scope text for registry search")
    rgy.add_argument("--status", choices=["publishable", "fenced"], help="filter search by thesis status")
    rgy.add_argument("--verdict", choices=["MATCH", "DRIFT", "UNVERIFIABLE"],
                     help="filter search by latest verdict status")
    rgy.add_argument("--apply", action="store_true", help="apply registry prune deletions")
    rgy.add_argument("--require-witnessed-match", action="store_true",
                     help="stats exits 1 when any latest MATCH rests on a measurement "
                          "with no recheck descriptor")
    rgy.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    rgy.set_defaults(func=cmd_registry)

    vd = sub.add_parser("verdicts", help="list or re-check witnessed assessments in a registry")
    vd.add_argument("dir", help="the registry directory")
    vd.add_argument("--verify", action="store_true",
                    help="re-derive each assessment's verdicts from the thesis and measurements on disk")
    vd.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    vd.set_defaults(func=cmd_verdicts)


def _add_recheck_command(sub) -> None:
    rc = sub.add_parser("recheck", help="inspect or replay oracle-level measurement descriptors")
    rc.add_argument("dir", help="the registry directory")
    rc.add_argument("--index", default="-1",
                    help="assessment index to inspect, default -1 for the latest")
    rc.add_argument("--pack", default=None, metavar="FILE",
                    help="JSON replay pack with reproduced measurements for descriptor-bearing rows")
    rc.add_argument("--template", default=None, metavar="FILE",
                    help="write a replay pack template for descriptor-bearing rows")
    rc.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    rc.set_defaults(func=cmd_recheck)


def _add_review_command(sub) -> None:
    rev = sub.add_parser("review", help="validate a cleanroom review bundle before verifier handoff")
    rev.add_argument("bundle", help="bundle directory created by crucible run --bundle")
    rev.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    rev.set_defaults(func=cmd_review)

def _add_artifact_commands(sub) -> None:
    rpt = sub.add_parser("report", help="render a Markdown report for a witnessed assessment")
    rpt.add_argument("dir", help="the registry directory")
    rpt.add_argument("--index", default="-1",
                     help="assessment index to render, default -1 for the latest")
    rpt.add_argument("--out", default=None, metavar="FILE",
                     help="write the Markdown report to FILE instead of stdout")
    rpt.set_defaults(func=cmd_report)

    bat = sub.add_parser("batch", help="assess a manifest of thesis jobs into a registry")
    bat.add_argument("manifest", help="path to a batch manifest JSON")
    bat.add_argument("--registry", required=True, metavar="DIR",
                     help="record batch assessments into registry DIR")
    bat.add_argument("--reports", default=None, metavar="DIR",
                     help="write one Markdown report per job")
    bat.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    bat.set_defaults(func=cmd_batch)

    dr = sub.add_parser("drift", help="compare the latest two witnessed assessments in a registry")
    dr.add_argument("dir", help="the registry directory")
    dr.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    dr.set_defaults(func=cmd_drift)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 1
    return func(args)


if __name__ == "__main__":
    raise SystemExit(main())
