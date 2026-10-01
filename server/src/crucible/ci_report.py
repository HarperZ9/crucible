"""Markdown rendering for the CI regression gate.

The summary is a readable artifact over the sealed gate report. It decides nothing new: it renders the
pass/fail line, the movement counts, the regressed rows, and a claims-by-rounds verdict matrix. Every
cell references the re-derivable packet behind it (the assessment seal), so a reviewer can re-check
any row with ``crucible verdicts REGISTRY --verify``. The render is a pure function of the report, so
the summary is byte-for-byte deterministic across runs on the same registry state, which is what a PR
comment needs.
"""
from __future__ import annotations

from crucible.ci_gate import GateReport


def _seal_ref(seal: str | None) -> str:
    """Render a seal as a short re-derivable packet reference, or a dash when there is no packet."""
    return f"`{seal[:12]}`" if seal else "-"


def _cell(status: str | None) -> str:
    return status if status else "absent"


def render_gate_markdown(report: GateReport) -> str:
    """Render a deterministic PR-comment-ready Markdown summary of the gate."""
    status_line = "PASS: no regressions" if report.passed else (
        f"FAIL: {len(report.regressions)} regression(s)"
    )
    lines = [
        "## crucible CI regression gate",
        "",
        f"**{status_line}**",
        "",
        f"- baseline `{report.baseline_seal[:12]}` -> current `{report.current_seal[:12]}`",
        "- movement: " + "  ".join(f"{k} {v}" for k, v in report.summary.items()),
        "",
    ]
    if not report.passed:
        lines.extend(["### What regressed", ""])
        for row in report.regressions:
            lines.append(
                f"- `{row.thesis_id}` / `{row.claim_id}`: "
                f"{_cell(row.baseline_status)} -> {_cell(row.current_status)} "
                f"(packet {_seal_ref(row.current_seal or row.baseline_seal)})"
            )
        lines.append("")
    lines.extend([
        "### Verdict matrix",
        "",
        "| Thesis | Claim | Baseline | Current | Movement | Packet |",
        "| --- | --- | --- | --- | --- | --- |",
    ])
    for row in report.rows:
        lines.append("| " + " | ".join([
            f"`{row.thesis_id}`",
            f"`{row.claim_id}`",
            _cell(row.baseline_status),
            _cell(row.current_status),
            row.movement,
            _seal_ref(row.current_seal or row.baseline_seal),
        ]) + " |")
    lines.append("")
    lines.append(
        "> Each packet reference is an assessment seal. Re-derive it with "
        "`crucible verdicts REGISTRY --verify`."
    )
    return "\n".join(lines) + "\n"
