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
from crucible.refine_cmd import cmd_refine
from crucible.registry_cmd import cmd_registry, cmd_verdicts
from crucible.report_cmd import cmd_report


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--registry", default=None, metavar="DIR",
                   help="register/record into a content-addressed registry at DIR")
    p.add_argument("--json", action="store_true", help="emit JSON instead of human text")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crucible", description="crucible: accountable judgment of ideas.")
    parser.add_argument("--version", action="version", version=f"crucible {__version__}")
    sub = parser.add_subparsers(dest="command")

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
                              "claim's own falsification; a model edge proposes independent attacks later)")
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

    ref = sub.add_parser("refine",
                         help="refine over rounds of substrate until the thesis is cohesively verified, or report the weakest claim")
    ref.add_argument("config", help="path to a refine config JSON (claims or a thesis, specs, rounds, target_margin, cohesion_bar)")
    ref.add_argument("--thesis", default=None,
                     help="resolve the thesis from a file or a registry id instead of the config's own claims")
    ref.add_argument("--registry", default=None, metavar="DIR", help="resolve a thesis id from a registry at DIR")
    ref.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    ref.set_defaults(func=cmd_refine)

    rgy = sub.add_parser("registry", help="inspect a stored registry: list, verify, stats, search, or prune")
    rgy.add_argument("action", choices=["list", "verify", "stats", "search", "prune"],
                     help="list, verify, summarize, search, or prune claim objects")
    rgy.add_argument("dir", help="the registry directory (created by --registry)")
    rgy.add_argument("query", nargs="?", help="scope text for registry search")
    rgy.add_argument("--status", choices=["publishable", "fenced"], help="filter search by thesis status")
    rgy.add_argument("--verdict", choices=["MATCH", "DRIFT", "UNVERIFIABLE"],
                     help="filter search by latest verdict status")
    rgy.add_argument("--apply", action="store_true", help="apply registry prune deletions")
    rgy.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    rgy.set_defaults(func=cmd_registry)

    vd = sub.add_parser("verdicts", help="list or re-check witnessed assessments in a registry")
    vd.add_argument("dir", help="the registry directory")
    vd.add_argument("--verify", action="store_true",
                    help="re-derive each assessment's verdicts from the thesis and measurements on disk")
    vd.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    vd.set_defaults(func=cmd_verdicts)

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

    return parser


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
