"""The ``import`` command: convert a promptfoo suite into a Crucible thesis.

It emits the thesis JSON shape that ``crucible register`` and ``crucible assess`` read, so a
migration is three commands:

    crucible import promptfooconfig.yaml --out thesis.json
    crucible register thesis.json --registry ./reg
    crucible assess thesis.json --registry ./reg --measurements results.json

Returns a process exit code: 0 on success, 1 when the config cannot be read, cannot be imported
in full, or the output cannot be written.
"""
from __future__ import annotations

import json
import sys
import time

from crucible.import_promptfoo import PromptfooParseError, import_promptfoo
from crucible.thesis import Thesis


def thesis_to_json(thesis: Thesis) -> dict:
    """Serialize a thesis into the register/assess input shape (round-trips)."""
    return {
        "title": thesis.title,
        "disposition": thesis.disposition,
        "claims": [{"id": c.id, "text": c.text, "falsification": c.falsification}
                   for c in thesis.claims],
        "source": "promptfoo-import",
        "seal": thesis.seal,
    }


def cmd_import(args) -> int:
    is_json = {"json": True, "yaml": False}.get(args.format)
    try:
        thesis = import_promptfoo(_read(args.config), is_json=is_json, clock=time.time)
    except (OSError, UnicodeDecodeError, PromptfooParseError) as exc:
        print(f"import failed: {exc}", file=sys.stderr)
        return 1
    out = thesis_to_json(thesis)
    payload = json.dumps(out, indent=2, ensure_ascii=False)
    if not args.out:
        print(payload)
        return 0
    try:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(payload)
    except OSError as exc:
        print(f"import failed: cannot write {args.out}: {exc}", file=sys.stderr)
        return 1
    print(f"imported {len(out['claims'])} claim(s) -> {args.out}  "
          f"(thesis {thesis.id}, seal {thesis.seal[:12]}). "
          f"Next: crucible register {args.out} --registry DIR", file=sys.stderr)
    return 0


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8-sig") as f:
        return f.read()
