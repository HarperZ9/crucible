"""Markdown reporting for witnessed assessments.

The report is a readable artifact over the existing sealed record. It does not decide anything new:
it renders the thesis, the assessment counts, the integrity checks, verdicts, evidence, and optional
measurement recheck descriptors so an operator can inspect what was actually witnessed.
"""
from __future__ import annotations

import json
from collections.abc import Mapping

from crucible.assess import Assessment
from crucible.thesis import Thesis


def render_assessment_report(
    thesis: Thesis,
    assessment: Assessment,
    *,
    checks: Mapping[str, object] | None = None,
) -> str:
    """Render a deterministic Markdown report for one assessment."""
    verdicts = tuple(dict(v) for v in assessment.verdicts)
    measurements = tuple(dict(m) for m in assessment.measurements)
    claim_text = {c.id: c.text for c in thesis.claims}
    measurement_by_id = {str(m.get("claim_id", "")): m for m in measurements}
    lines = [
        f"# crucible report: {_md(thesis.title)}",
        "",
        "## Summary",
        "",
        f"- thesis_id: `{thesis.id}`",
        f"- thesis_seal: `{thesis.seal}`",
        f"- assessment_seal: `{assessment.seal}`",
        f"- counts: MATCH {assessment.match} / DRIFT {assessment.drift} / "
        f"UNVERIFIABLE {assessment.unverifiable}",
    ]
    if checks is not None:
        lines.append("- integrity: " + ", ".join(f"{k}={v}" for k, v in checks.items()))
    _append_verdicts(lines, verdicts, claim_text)
    _append_evidence(lines, measurements, claim_text)
    _append_rechecks(lines, measurements, claim_text)
    _append_missing(lines, thesis, measurement_by_id)
    return "\n".join(lines) + "\n"


def _append_verdicts(lines: list[str], verdicts: tuple[dict, ...], claim_text: Mapping[str, str]) -> None:
    lines.extend(["", "## Verdicts", "", "| Claim | Status | Margin | Method | Grounds |",
                  "| --- | --- | ---: | --- | --- |"])
    for row in verdicts:
        cid = str(row.get("claim_id", ""))
        lines.append("| " + " | ".join([
            _md(claim_text.get(cid, cid)),
            _md(row.get("status", "")),
            _number(row.get("margin")),
            _md(row.get("method", "")),
            _md(row.get("grounds", "")),
        ]) + " |")


def _append_evidence(lines: list[str], measurements: tuple[dict, ...], claim_text: Mapping[str, str]) -> None:
    evidence_rows = _evidence_rows(measurements, claim_text)
    if not evidence_rows:
        return
    lines.extend(["", "## Measurement Evidence", "", "| Claim | Method | Evidence |",
                  "| --- | --- | --- |"])
    for claim, method, evidence in evidence_rows:
        lines.append(f"| {_md(claim)} | {_md(method)} | {_md(evidence)} |")


def _append_rechecks(lines: list[str], measurements: tuple[dict, ...], claim_text: Mapping[str, str]) -> None:
    recheck_rows = _recheck_rows(measurements, claim_text)
    if not recheck_rows:
        return
    lines.extend(["", "## Recheck Descriptors", "", "| Claim | Method | Descriptor |",
                  "| --- | --- | --- |"])
    for claim_label, method, descriptor in recheck_rows:
        lines.append(f"| {_md(claim_label)} | {_md(method)} | {_md(descriptor)} |")


def _append_missing(lines: list[str], thesis: Thesis, measurement_by_id: Mapping[str, dict]) -> None:
    missing = [c for c in thesis.claims if c.id not in measurement_by_id]
    if not missing:
        return
    lines.extend(["", "## Unmeasured Claims", ""])
    for missing_claim in missing:
        lines.append(f"- {_md(missing_claim.text)}")


def _evidence_rows(measurements: tuple[dict, ...], claim_text: Mapping[str, str]) -> list[tuple[str, str, str]]:
    rows = []
    for row in measurements:
        evidence = row.get("evidence") or []
        if not isinstance(evidence, list | tuple):
            evidence = [evidence]
        if not evidence:
            continue
        cid = str(row.get("claim_id", ""))
        rows.append((claim_text.get(cid, cid), str(row.get("method", "")),
                     "; ".join(str(item) for item in evidence)))
    return rows


def _recheck_rows(measurements: tuple[dict, ...], claim_text: Mapping[str, str]) -> list[tuple[str, str, str]]:
    rows = []
    for row in measurements:
        recheck = row.get("recheck")
        if not isinstance(recheck, Mapping):
            continue
        cid = str(row.get("claim_id", ""))
        descriptor = json.dumps(recheck, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        rows.append((claim_text.get(cid, cid), str(row.get("method", "")), descriptor))
    return rows


def _md(value: object) -> str:
    return str(value).replace("\n", " ").replace("|", "\\|")


def _number(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)
