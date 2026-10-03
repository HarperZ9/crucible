"""CLI commands for pairwise judging, decomposed claims and minority-preserving summaries.

`crucible pairwise FILE` combines recorded both-order slot answers into verdicts
and the order-consistency report. `crucible decompose FILE` measures a claim's
typed sub-questions and names the weakest. `crucible views FILE` summarizes
views by position, keeping every minority.
"""
from __future__ import annotations

import json
import sys

from crucible.decompose import from_spec, measure_decomposed
from crucible.dissent import dissent_survival, render_views_markdown, summarize_views
from crucible.pairwise import combine, pairwise_report, slot_answer

_ERRORS = (OSError, ValueError, KeyError, TypeError)


def _load(path: str) -> object:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _emit(payload: dict, as_json: bool, lines: list[str]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False) if as_json else "\n".join(lines))


def pairwise_payload(data: dict) -> dict:
    rows = []
    for pair in data["pairs"]:
        result = combine(slot_answer({"prefer": pair.get("ab")}), slot_answer({"prefer": pair.get("ba")}))
        rows.append((pair.get("id"), result))
    return {"pairs": [{"id": pid, **r.to_dict()} for pid, r in rows],
            "report": pairwise_report(r for _, r in rows)}


def cmd_pairwise(args) -> int:
    try:
        payload = pairwise_payload(_load(args.file))  # type: ignore[arg-type]
    except _ERRORS as exc:
        print(f"pairwise failed: {exc}", file=sys.stderr)
        return 1
    rep = payload["report"]
    _emit(payload, args.json, [
        f"pairs={rep['pairs']} usable={rep['usable_pairs']} verdicts={rep['verdicts']}",
        f"order consistency={rep['order_consistency']} wilson95={rep['order_consistency_wilson95']}",
        f"first-slot rate={rep['first_slot_rate']} wilson95={rep['first_slot_wilson95']}"])
    return 0


def cmd_decompose(args) -> int:
    try:
        dc, answers = from_spec(_load(args.file))  # type: ignore[arg-type]
        payload = measure_decomposed(dc, answers)
    except _ERRORS as exc:
        print(f"decompose failed: {exc}", file=sys.stderr)
        return 1
    lines = [f"verdict={payload['verdict']} weakest={payload['weakest']['id']}: "
             f"{payload['weakest']['text']}"]
    lines += [f"  {s['id']}: {s['status']} ({s['grounds']})" for s in payload["sub_verdicts"]]
    _emit(payload, args.json, lines)
    return 0


def cmd_views(args) -> int:
    try:
        data = _load(args.file)
        views = data["views"] if isinstance(data, dict) else data
        summary = summarize_views(views)  # type: ignore[arg-type]
        if isinstance(data, dict) and data.get("planted"):
            summary["survival"] = dissent_survival(data["planted"], summary)
    except _ERRORS as exc:
        print(f"views failed: {exc}", file=sys.stderr)
        return 1
    _emit(summary, args.json, render_views_markdown(summary))
    return 0


def add_judging_commands(sub) -> None:
    pw = sub.add_parser("pairwise", help="combine both-order pairwise judgments into verdicts and "
                                         "an order-consistency report")
    pw.add_argument("file", help='JSON: {"pairs": [{"id", "ab", "ba"}]}, slot answers first/second/tie')
    pw.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    pw.set_defaults(func=cmd_pairwise)
    dc = sub.add_parser("decompose", help="measure a claim's typed sub-questions and name the weakest")
    dc.add_argument("file", help='JSON: {"claim", "falsification", "questions": [...], "answers": {...}}')
    dc.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    dc.set_defaults(func=cmd_decompose)
    vw = sub.add_parser("views", help="summarize views by position, keeping every minority")
    vw.add_argument("file", help='JSON: {"views": [{"source", "position", "text"}], "planted"?: [...]}')
    vw.add_argument("--json", action="store_true", help="emit JSON instead of Markdown")
    vw.set_defaults(func=cmd_views)
