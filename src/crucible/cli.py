"""The ``crucible`` command: an argument surface over the judgment organ.

``register``, ``assess``, and ``steelman`` work on a thesis (a JSON file, or an id with
``--registry``); ``registry list|verify`` and ``verdicts [--verify]`` inspect a stored registry. Each
subcommand binds a handler from ``crucible.commands`` via ``set_defaults(func=...)``; ``main``
dispatches to it. Output is human text by default, JSON with ``--json``.
"""
from __future__ import annotations

import argparse

from crucible import __version__
from crucible.commands import (
    cmd_assess,
    cmd_register,
    cmd_registry,
    cmd_steelman,
    cmd_verdicts,
)


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--registry", default=None, metavar="DIR",
                   help="register/record into a content-addressed registry at DIR")
    p.add_argument("--json", action="store_true", help="emit JSON instead of human text")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crucible", description="Crucible: accountable judgment of ideas.")
    parser.add_argument("--version", action="version", version=f"crucible {__version__}")
    sub = parser.add_subparsers(dest="command")

    reg = sub.add_parser("register", help="register a thesis (claims + falsification) into a registry")
    reg.add_argument("thesis", help="path to a thesis JSON")
    _add_common(reg)
    reg.set_defaults(func=cmd_register)

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

    rgy = sub.add_parser("registry", help="inspect a stored registry: list or verify")
    rgy.add_argument("action", choices=["list", "verify"], help="list theses or verify stored claims")
    rgy.add_argument("dir", help="the registry directory (created by --registry)")
    rgy.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    rgy.set_defaults(func=cmd_registry)

    vd = sub.add_parser("verdicts", help="list or re-check witnessed assessments in a registry")
    vd.add_argument("dir", help="the registry directory")
    vd.add_argument("--verify", action="store_true",
                    help="re-derive each assessment's verdicts from the thesis and measurements on disk")
    vd.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    vd.set_defaults(func=cmd_verdicts)

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
