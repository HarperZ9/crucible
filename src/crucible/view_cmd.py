"""The ``view`` command: render a registry into one offline HTML page.

Returns a process exit code: 0 when the page (or the pack, with ``--json``) was produced, 1 when
the directory is not a registry or cannot be read. A page is still produced for a registry that
fails its integrity check, because showing the failed rows is the purpose of the page; use
``crucible registry verify`` for an exit code that gates on integrity.
"""
from __future__ import annotations

import json
import os
import sys

from crucible.registry import Registry
from crucible.view import build_view, render_view_html

_INPUT_ERRORS = (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError)


def cmd_view(args) -> int:
    try:
        if not os.path.isfile(os.path.join(args.dir, "theses.jsonl")):
            raise ValueError(f"no registry at {args.dir} (it has no theses.jsonl)")
        pack = build_view(Registry(args.dir))
        text = (json.dumps(pack, indent=2, ensure_ascii=False) if args.json
                else render_view_html(pack))
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(text)
    except _INPUT_ERRORS as exc:
        print(f"view failed: {exc}", file=sys.stderr)
        return 1
    if not args.out:
        print(text)
        return 0
    c = pack["counts"]
    print(f"registry view -> {args.out}  "
          f"({c['theses']} theses, {c['claims']} claims, {c['assessments']} assessments). "
          f"Open it and edit a claim to watch its check fail.", file=sys.stderr)
    return 0
