"""``crucible examples --out DIR``: write the packaged quickstart inputs to a new folder.

The inputs ship inside the wheel (``crucible.examples``), so the README's first run works after
``pip install crucible-bench`` without a clone. The folder must not exist yet: this command never
writes into, or over, anything the caller already has.
"""
from __future__ import annotations

import json
import os
import sys
from importlib import resources


def packaged_inputs() -> dict[str, bytes]:
    """The shipped example inputs, by file name."""
    package = resources.files("crucible.examples")
    return {p.name: p.read_bytes() for p in sorted(package.iterdir(), key=lambda p: p.name)
            if p.name.endswith(".json")}


def cmd_examples(args) -> int:
    out = args.out
    try:
        inputs = packaged_inputs()
        os.makedirs(out)  # raises FileExistsError when the folder is already there
        for name, data in inputs.items():
            with open(os.path.join(out, name), "xb") as f:
                f.write(data)
    except FileExistsError:
        print(f"examples failed: {out} already exists; name a new folder", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"examples failed: {exc.strerror or exc}", file=sys.stderr)
        return 1
    files = sorted(inputs)
    if args.json:
        print(json.dumps({"ok": True, "out": out, "files": files}, indent=2))
    else:
        print(f"wrote {len(files)} example inputs to {out}")
        print(f"next: crucible run {os.path.join(out, 'thesis-binary-search.json')} "
              f"--measurements {os.path.join(out, 'measurements-binary-search.json')} "
              "--registry .crucible-registry")
    return 0
