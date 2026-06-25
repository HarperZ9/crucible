"""Drift tracking across witnessed assessments.

crucible's continuous loop needs to say what moved between rounds without re-judging the thesis by
vibe. ``drift_track`` compares two stored assessments and classifies each claim by the recorded
verdict margins: held, improved, regressed, or moved. Numeric margins decide direction; unrankable
transitions, such as UNVERIFIABLE to MATCH, are reported as moved rather than silently upgraded.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from crucible.assess import Assessment

HELD = "held"
MOVED = "moved"
IMPROVED = "improved"
REGRESSED = "regressed"


@dataclass(frozen=True, slots=True)
class DriftRow:
    claim_id: str
    previous_status: str | None
    current_status: str | None
    previous_margin: float | None
    current_margin: float | None
    margin_delta: float | None
    status: str

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "previous_status": self.previous_status,
            "current_status": self.current_status,
            "previous_margin": self.previous_margin,
            "current_margin": self.current_margin,
            "margin_delta": self.margin_delta,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class DriftReport:
    previous_seal: str
    current_seal: str
    rows: tuple[DriftRow, ...]
    summary: dict[str, int]

    def to_dict(self) -> dict:
        return {
            "previous_seal": self.previous_seal,
            "current_seal": self.current_seal,
            "summary": dict(self.summary),
            "rows": [r.to_dict() for r in self.rows],
        }


def _by_claim(a: Assessment) -> dict[str, Mapping]:
    return {str(v.get("claim_id", "")): v for v in a.verdicts if v.get("claim_id")}


def _margin(row: Mapping | None) -> float | None:
    value = None if row is None else row.get("margin")
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _status(row: Mapping | None) -> str | None:
    value = None if row is None else row.get("status")
    return value if isinstance(value, str) else None


def _classify(prev: Mapping | None, curr: Mapping | None) -> tuple[str, float | None]:
    pmargin, cmargin = _margin(prev), _margin(curr)
    if pmargin is not None and cmargin is not None:
        delta = round(cmargin - pmargin, 12)
        if delta > 0:
            return IMPROVED, delta
        if delta < 0:
            return REGRESSED, delta
        return HELD, delta
    if _status(prev) == _status(curr):
        return HELD, None
    return MOVED, None


def drift_track(previous: Assessment, current: Assessment) -> DriftReport:
    """Compare two assessments and classify per-claim movement.

    The comparison is deliberately mechanical: if both rounds have numeric margins, the margin delta
    decides improvement or regression. If a margin is absent on either side, the row is ``moved``
    unless the status is unchanged, in which case it is ``held``. That avoids reading a new
    measurement as a proven improvement when the previous round was UNVERIFIABLE.
    """
    if previous.thesis_id != current.thesis_id:
        raise ValueError("drift tracking requires two assessments of the same thesis")
    prev, curr = _by_claim(previous), _by_claim(current)
    rows: list[DriftRow] = []
    counts = {HELD: 0, MOVED: 0, IMPROVED: 0, REGRESSED: 0}
    for cid in sorted(set(prev) | set(curr)):
        p, c = prev.get(cid), curr.get(cid)
        status, delta = _classify(p, c)
        counts[status] += 1
        rows.append(DriftRow(cid, _status(p), _status(c), _margin(p), _margin(c), delta, status))
    return DriftReport(previous.seal, current.seal, tuple(rows), counts)
