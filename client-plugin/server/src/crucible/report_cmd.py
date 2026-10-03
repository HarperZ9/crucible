"""CLI command for rendering a witnessed assessment report."""
from __future__ import annotations

import json
import sys

from crucible.assess import Assessment, recheck_assessment
from crucible.registry import Registry
from crucible.report import render_assessment_report

_INPUT_ERRORS = (OSError, ValueError, KeyError, TypeError, IndexError)


def _views(path: str | None) -> dict | None:
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("views file must map claim ids to lists of views")
    return data


def cmd_report(args) -> int:
    reg = Registry(args.dir)
    try:
        records = list(reg.assessments())
        if not records:
            raise ValueError(f"no assessments in registry {args.dir}")
        index = int(args.index)
        record = records[index]
        assessment = Assessment.from_dict(record)
        thesis = reg.get_thesis(assessment.thesis_id)
        if thesis is None:
            raise ValueError(f"no thesis {assessment.thesis_id!r} in registry {args.dir}")
        report = render_assessment_report(
            thesis,
            assessment,
            checks=recheck_assessment(thesis, assessment),
            views=_views(getattr(args, "views", None)),
        )
        if args.out:
            with open(args.out, "x", encoding="utf-8") as f:
                f.write(report)
            print(f"wrote report to {args.out}")
            return 0
        print(report, end="")
        return 0
    except _INPUT_ERRORS as exc:
        print(f"report failed: {exc}", file=sys.stderr)
        return 1
