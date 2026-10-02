"""The CI regression gate: compare a registry's verdicts against a baseline and fail on regression.

crucible's continuous loop needs a native gate that a pull request can trust: capture a baseline of
the current verified-latest verdict per (thesis, claim), then on a later commit re-derive the current
verdicts and report only what MOVED. A claim moving MATCH -> DRIFT, or becoming UNVERIFIABLE, or
dropping out of the verified-latest set, is a regression. The gate is pure over two snapshots, so the
verdict of the gate itself recomputes from the record and cannot be asserted.

A baseline is a snapshot, not a second verdict path. Each cell references the assessment seal it was
read from, so a reviewer can re-derive the packet behind any claim in the summary with
``crucible verdicts REGISTRY --verify``. The gate never upgrades a claim silently: it only reports
movement it can read from the recorded verdict status, and it fails closed when a baselined claim can
no longer be verified.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from crucible.verdict import DRIFT, MATCH, UNVERIFIABLE

BASELINE_KIND = "crucible.ci-baseline/v1"

# The verdict standing ordered from strongest to weakest. A move to a lower rank is a regression; a
# move to a higher rank is an improvement. UNVERIFIABLE is weakest: an axis that cannot be measured is
# never read as holding (the same fail-closed order the verdict spine enforces).
_RANK = {MATCH: 2, DRIFT: 1, UNVERIFIABLE: 0}

# Row movement classes.
HELD = "held"
IMPROVED = "improved"
REGRESSED = "regressed"
NEW = "new"
DROPPED = "dropped"

# A baselined claim that can no longer be verified drops out of the current snapshot. It is fail-closed
# as a regression: a claim that used to have a witnessed standing and now has none is not "held".
_REGRESSION_CLASSES = frozenset({REGRESSED, DROPPED})


@dataclass(frozen=True, slots=True)
class Cell:
    """One (thesis, claim) verdict cell in a snapshot: the recorded status and the assessment seal it
    was read from, so the cell references a re-derivable packet rather than a bare status."""

    thesis_id: str
    claim_id: str
    status: str
    assessment_seal: str

    def to_dict(self) -> dict:
        return {
            "thesis_id": self.thesis_id,
            "claim_id": self.claim_id,
            "status": self.status,
            "assessment_seal": self.assessment_seal,
        }

    @staticmethod
    def from_dict(d: Mapping) -> "Cell":
        return Cell(
            str(d["thesis_id"]),
            str(d["claim_id"]),
            str(d["status"]),
            str(d.get("assessment_seal", "")),
        )


@dataclass(frozen=True, slots=True)
class Snapshot:
    """A set of verdict cells with a deterministic seal over them. The seal folds the sorted cells, so
    it is order independent and recomputes from the stored cells: a baseline file cannot be edited
    without breaking its seal."""

    cells: tuple[Cell, ...]
    seal: str

    def to_dict(self) -> dict:
        return {"kind": BASELINE_KIND, "cells": [c.to_dict() for c in self.cells], "seal": self.seal}

    @staticmethod
    def from_dict(d: Mapping) -> "Snapshot":
        kind = d.get("kind")
        if kind != BASELINE_KIND:
            raise ValueError(f"not a {BASELINE_KIND} snapshot: kind={kind!r}")
        rows = d.get("cells")
        if not isinstance(rows, (list, tuple)):
            raise ValueError("snapshot cells must be a list")
        cells = tuple(Cell.from_dict(r) for r in rows)
        seal = str(d.get("seal", ""))
        recomputed = snapshot_seal(cells)
        if seal != recomputed:
            raise ValueError("snapshot seal does not match its cells (baseline may be tampered)")
        return Snapshot(cells, seal)


def snapshot_seal(cells: Iterable[Cell]) -> str:
    """A deterministic fingerprint over a snapshot's cells, order independent and recomputable.

    The seal binds every cell's thesis id, claim id, status, and the assessment seal it was read from,
    so an edited baseline (a downgraded status, a swapped seal) is caught on load.
    """
    objs = [c.to_dict() for c in cells]
    objs.sort(key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False))
    canon = json.dumps(objs, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def make_snapshot(cells: Iterable[Cell]) -> Snapshot:
    """Build a sealed snapshot from cells, sorting them so the snapshot is over the SET of cells."""
    ordered = tuple(sorted(cells, key=lambda c: (c.thesis_id, c.claim_id)))
    return Snapshot(ordered, snapshot_seal(ordered))


@dataclass(frozen=True, slots=True)
class GateRow:
    """One (thesis, claim) row in the gate report: the baseline and current status and the movement
    class. ``current_seal`` references the current assessment packet; ``baseline_seal`` references the
    packet the baseline was captured from, so both sides of the comparison are re-derivable."""

    thesis_id: str
    claim_id: str
    baseline_status: str | None
    current_status: str | None
    baseline_seal: str | None
    current_seal: str | None
    movement: str

    @property
    def is_regression(self) -> bool:
        return self.movement in _REGRESSION_CLASSES

    def to_dict(self) -> dict:
        return {
            "thesis_id": self.thesis_id,
            "claim_id": self.claim_id,
            "baseline_status": self.baseline_status,
            "current_status": self.current_status,
            "baseline_seal": self.baseline_seal,
            "current_seal": self.current_seal,
            "movement": self.movement,
            "is_regression": self.is_regression,
        }


@dataclass(frozen=True, slots=True)
class GateReport:
    """The gate verdict over a baseline and a current snapshot: every compared row, the movement
    counts, the list of regressed rows, and whether the gate passes. ``passed`` is False if and only
    if there is at least one regression, so the process exit code follows the report."""

    baseline_seal: str
    current_seal: str
    rows: tuple[GateRow, ...]
    summary: dict[str, int]

    @property
    def regressions(self) -> tuple[GateRow, ...]:
        return tuple(r for r in self.rows if r.is_regression)

    @property
    def passed(self) -> bool:
        return not self.regressions

    def to_dict(self) -> dict:
        return {
            "baseline_seal": self.baseline_seal,
            "current_seal": self.current_seal,
            "passed": self.passed,
            "summary": dict(self.summary),
            "regressions": [r.to_dict() for r in self.regressions],
            "rows": [r.to_dict() for r in self.rows],
        }


def _index(snapshot: Snapshot) -> dict[tuple[str, str], Cell]:
    return {(c.thesis_id, c.claim_id): c for c in snapshot.cells}


def _classify(baseline: Cell | None, current: Cell | None) -> str:
    """Classify a single cell's movement from baseline to current.

    A claim absent from the baseline is ``new``. A claim in the baseline but absent from the current
    verified-latest snapshot is ``dropped`` (fail-closed: it lost its witnessed standing). Otherwise
    the recorded statuses are ranked: a lower rank is ``regressed``, a higher rank ``improved``, an
    equal rank ``held``. New UNVERIFIABLE therefore registers as a regression whenever it replaces a
    MATCH or DRIFT, and a dropped claim never reads as held.
    """
    if baseline is None:
        return NEW
    if current is None:
        return DROPPED
    br = _RANK.get(baseline.status, -1)
    cr = _RANK.get(current.status, -1)
    if cr < br:
        return REGRESSED
    if cr > br:
        return IMPROVED
    return HELD


def gate(baseline: Snapshot, current: Snapshot) -> GateReport:
    """Compare a baseline snapshot against the current snapshot and report per-claim movement.

    The comparison is mechanical and pure: rank the recorded statuses and report what moved. The gate
    fails (``passed`` False) exactly when a claim regressed or dropped out of the verified-latest set.
    A newly appearing claim or an improvement never fails the gate: the gate guards against loss of a
    witnessed standing, it does not require monotonic growth.
    """
    b, c = _index(baseline), _index(current)
    counts = {HELD: 0, IMPROVED: 0, REGRESSED: 0, NEW: 0, DROPPED: 0}
    rows: list[GateRow] = []
    for key in sorted(set(b) | set(c)):
        bc, cc = b.get(key), c.get(key)
        movement = _classify(bc, cc)
        counts[movement] += 1
        rows.append(GateRow(
            thesis_id=key[0],
            claim_id=key[1],
            baseline_status=bc.status if bc else None,
            current_status=cc.status if cc else None,
            baseline_seal=bc.assessment_seal if bc else None,
            current_seal=cc.assessment_seal if cc else None,
            movement=movement,
        ))
    return GateReport(baseline.seal, current.seal, tuple(rows), counts)


_VALID_STATUSES = frozenset({MATCH, DRIFT, UNVERIFIABLE})


def cells_from_latest(latest: Mapping[str, Mapping]) -> tuple[Cell, ...]:
    """Read verdict cells from a mapping of thesis id -> verified-latest assessment record.

    Only rows whose status is a real verdict (MATCH / DRIFT / UNVERIFIABLE) become cells; a row with a
    missing or unknown status is skipped rather than guessed, so the snapshot never invents a standing.
    The assessment seal on each cell is the record's own seal, the re-derivable packet reference.
    """
    cells: list[Cell] = []
    for thesis_id, record in latest.items():
        seal = str(record.get("seal", ""))
        rows = record.get("verdicts")
        if not isinstance(rows, (list, tuple)):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            status = row.get("status")
            claim_id = row.get("claim_id")
            if status not in _VALID_STATUSES or not isinstance(claim_id, str) or not claim_id:
                continue
            cells.append(Cell(str(thesis_id), claim_id, str(status), seal))
    return tuple(cells)
