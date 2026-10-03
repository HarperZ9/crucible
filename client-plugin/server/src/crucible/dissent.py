"""Minority views kept: summaries that report every position, not only the consensus.

When several judges, adversaries or sources weigh in on one claim, a summary
that keeps only the majority hides the view most likely to matter. The
summarizer groups views by position and returns the majority beside every
minority position, each with its sources and count. Nothing is dropped and no
minority is folded into the consensus. ``dissent_survival`` scores any summary,
structured or plain text, on how many planted minority positions survived it.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

SUMMARY_SCHEMA = "crucible.views-summary/1"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def summarize_views(views: Iterable[Mapping[str, object]]) -> dict:
    """Group views by position. Ties for the majority are all reported as tied.

    Each view is ``{"source": str, "position": str, "text": str}``. Positions
    compare case- and space-insensitively; the first spelling seen is kept.
    """
    groups: dict[str, dict] = {}
    order: list[str] = []
    for view in views:
        position = str(view.get("position", "")).strip()
        if not position:
            raise ValueError("every view needs a non-empty position")
        key = _norm(position)
        if key not in groups:
            groups[key] = {"position": position, "count": 0, "sources": [], "texts": []}
            order.append(key)
        group = groups[key]
        group["count"] += 1
        group["sources"].append(str(view.get("source", "")))
        if view.get("text"):
            group["texts"].append(str(view["text"]))
    ranked = sorted(order, key=lambda k: (-groups[k]["count"], order.index(k)))
    if not ranked:
        return {"schema": SUMMARY_SCHEMA, "views": 0, "majority": [], "minorities": []}
    top = groups[ranked[0]]["count"]
    return {
        "schema": SUMMARY_SCHEMA,
        "views": sum(g["count"] for g in groups.values()),
        "majority": [groups[k] for k in ranked if groups[k]["count"] == top],
        "minorities": [groups[k] for k in ranked if groups[k]["count"] < top],
    }


def render_views_markdown(summary: Mapping[str, object]) -> list[str]:
    """Markdown lines: the majority first, then every minority position with its sources."""
    lines: list[str] = []
    for label, key in (("Majority", "majority"), ("Minority", "minorities")):
        groups = summary.get(key, [])
        for group in groups if isinstance(groups, list) else []:
            sources = ", ".join(group["sources"]) or "unnamed"
            lines.append(f"- {label} ({group['count']} of {summary['views']}): "
                         f"{group['position']} [{sources}]")
            lines.extend(f"  - {text}" for text in group["texts"])
    return lines


def dissent_survival(planted: Iterable[str], summary: object) -> dict:
    """Share of planted minority positions still present in ``summary``.

    A structured summary keeps a position when one of its majority or minority
    groups carries it. A text summary keeps it when the position's words all
    appear in the text, case-insensitively.
    """
    wanted = [p for p in planted if str(p).strip()]
    if isinstance(summary, Mapping):
        kept = {_norm(g["position"]) for key in ("majority", "minorities")
                for g in summary.get(key, [])}
        survived = [p for p in wanted if _norm(p) in kept]
    else:
        words = set(re.findall(r"[a-z0-9]+", str(summary).lower()))
        survived = [p for p in wanted if set(re.findall(r"[a-z0-9]+", p.lower())) <= words]
    return {"planted": len(wanted), "survived": len(survived),
            "rate": len(survived) / len(wanted) if wanted else None,
            "lost": [p for p in wanted if p not in survived]}
