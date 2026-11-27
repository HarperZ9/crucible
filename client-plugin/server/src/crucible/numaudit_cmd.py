"""The ``numaudit`` command: recompute stated figures in text files from the inputs beside them."""
from __future__ import annotations

import json
import sys

from crucible.numaudit import audit, word_count

SCHEMA = "crucible.numaudit/1"


def run_numaudit(paths: list[str]) -> dict:
    files, words, findings = [], 0, 0
    for path in paths:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        found = [f.to_dict() for f in audit(text)]
        n = word_count(text)
        files.append({"path": path, "words": n, "findings": found})
        words += n
        findings += len(found)
    flags = sum(1 for f in files for x in f["findings"] if x["severity"] == "flag")
    return {"schema": SCHEMA, "files": files, "words": words, "findings": findings, "flags": flags,
            "flags_per_1000_words": round(1000 * flags / words, 4) if words else None}


def cmd_numaudit(args) -> int:
    try:
        report = run_numaudit(args.paths)
    except OSError as exc:
        print(f"numaudit failed: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for f in report["files"]:
            for x in f["findings"]:
                print(f"{f['path']}: {x['rule']} [{x['severity']}] stated {x['stated']:g}, "
                      f"recomputed {x['recomputed']:g} ({x['tolerance']})")
                print(f"    {x['note']}")
                print(f"    \"{x['excerpt']}\"")
        print(f"{report['words']} words, {report['flags']} flags, "
              f"{report['findings'] - report['flags']} ambiguous, {report['flags_per_1000_words']} flags per 1,000 words")
    return 1 if args.fail_on_flag and report["flags"] else 0
