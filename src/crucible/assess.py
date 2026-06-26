"""The witnessed assessment: fold a thesis's per-claim verdicts into a re-checkable record.

``assess`` computes a verdict per claim (pure, from each claim's measurement) and seals the verdicts,
the measurements, and the record. The verdicts and the measurements are persisted with the record, so
the guarantee is real, not a fingerprint of discarded data:

- ``verify_assessment`` recomputes every seal from the stored arrays (the verdict seal from the stored
  verdicts, the measurement seal from the stored measurements, the record seal from the fields that
  bind both). It is not a tautology: editing a verdict, a measurement, or a count is caught.
- ``recheck_assessment`` goes further, re-deriving each verdict from the thesis and the stored
  measurements via ``verdict_for`` and confirming the stored verdicts are exactly what the pure
  function yields. A verdict that was asserted rather than computed is exposed even if its seals are
  internally consistent. This is the differentiator, made checkable from disk.

The clock is injected, so the record replays.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from crucible.thesis import Thesis, verify_thesis
from crucible.verdict import (
    DRIFT,
    MATCH,
    UNVERIFIABLE,
    Measurement,
    Verdict,
    verdict_for,
)

_VSEAL_FIELDS = ("claim_id", "claim_sha256", "status", "deviation", "tolerance", "margin", "method", "grounds")
_MSEAL_FIELDS = ("claim_id", "claim_sha256", "deviation", "tolerance", "method", "evidence")
_MSEAL_RECHECK_FIELDS = _MSEAL_FIELDS + ("recheck",)

MeasurementReplayer = Callable[[Mapping[str, object]], Measurement | Mapping[str, object]]


def _verdict_row(v: Verdict) -> dict:
    return {"claim_id": v.claim_id, "claim_sha256": v.claim_sha256, "status": v.status,
            "deviation": v.deviation, "tolerance": v.tolerance, "margin": v.margin,
            "method": v.method, "grounds": v.grounds}


def _measurement_row(m: Measurement) -> dict:
    row: dict[str, object] = {
        "claim_id": m.claim_id, "claim_sha256": m.claim_sha256, "deviation": m.deviation,
        "tolerance": m.tolerance, "method": m.method, "evidence": list(m.evidence),
    }
    if m.recheck is not None:
        row["recheck"] = _jsonable(m.recheck)
    return row


def _jsonable(value: object) -> object:
    return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=False))


def _seal_rows(rows: Iterable[Mapping], fields: tuple[str, ...]) -> str:
    """A deterministic fingerprint over rows, folding only the named fields. Order independent (the
    rows are sorted by their canonical form) and recomputable from the stored rows."""
    objs = [{k: r.get(k) for k in fields} for r in rows]
    objs.sort(key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False))
    canon = json.dumps(objs, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _measurement_seal(rows: Iterable[Mapping]) -> str:
    rows = tuple(rows)
    fields = _MSEAL_RECHECK_FIELDS if any("recheck" in r for r in rows) else _MSEAL_FIELDS
    return _seal_rows(rows, fields)


def verdict_seal(verdicts: Iterable[Verdict]) -> str:
    """The seal over a set of verdicts, including the rendered margin and grounds. Order independent."""
    return _seal_rows([_verdict_row(v) for v in verdicts], _VSEAL_FIELDS)


def _record_fields(started_at: float, thesis_id: str, thesis_seal: str, claims: int, match: int,
                   drift: int, unverifiable: int, vseal: str, mseal: str, stored: dict | None) -> dict:
    return {
        "started_at": started_at, "thesis_id": thesis_id, "thesis_seal": thesis_seal,
        "claims": claims, "match": match, "drift": drift, "unverifiable": unverifiable,
        "verdict_seal": vseal, "measurement_seal": mseal, "stored": stored,
    }


def _seal_record(fields: dict) -> str:
    return hashlib.sha256(
        json.dumps(fields, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class Assessment:
    """A witnessed assessment of one thesis: the verdict counts, the seals over the verdicts and the
    measurements, the verdicts and measurements themselves (so the seals have a preimage on disk), and
    a seal over the whole record."""

    started_at: float
    thesis_id: str
    thesis_seal: str
    claims: int
    match: int
    drift: int
    unverifiable: int
    verdict_seal: str
    measurement_seal: str
    verdicts: tuple[dict, ...]
    measurements: tuple[dict, ...]
    stored: dict | None
    seal: str

    def to_dict(self) -> dict:
        fields = _record_fields(self.started_at, self.thesis_id, self.thesis_seal, self.claims,
                                self.match, self.drift, self.unverifiable, self.verdict_seal,
                                self.measurement_seal, self.stored)
        return {**fields, "verdicts": list(self.verdicts),
                "measurements": list(self.measurements), "seal": self.seal}

    @staticmethod
    def from_dict(d: Mapping) -> "Assessment":
        return Assessment(
            d["started_at"], d["thesis_id"], d["thesis_seal"], d["claims"], d["match"], d["drift"],
            d["unverifiable"], d["verdict_seal"], d["measurement_seal"],
            _rows(d.get("verdicts", ()), "verdicts"), _rows(d.get("measurements", ()), "measurements"),
            d.get("stored"), d["seal"],
        )


def verify_assessment(a: Assessment) -> bool:
    """Recompute every seal from the stored data and confirm they match. Not a tautology: it folds the
    actual stored verdicts and measurements, so editing a verdict, a measurement, or a count is caught.
    To also confirm the verdicts FOLLOW from the measurements, use ``recheck_assessment``."""
    if not _counts_match(a, a.verdicts):
        return False
    if _seal_rows(a.verdicts, _VSEAL_FIELDS) != a.verdict_seal:
        return False
    if _measurement_seal(a.measurements) != a.measurement_seal:
        return False
    fields = _record_fields(a.started_at, a.thesis_id, a.thesis_seal, a.claims, a.match, a.drift,
                            a.unverifiable, a.verdict_seal, a.measurement_seal, a.stored)
    return _seal_record(fields) == a.seal


def _counts_match(a: Assessment, rows: Iterable[Mapping]) -> bool:
    counts = {MATCH: 0, DRIFT: 0, UNVERIFIABLE: 0}
    total = 0
    for row in rows:
        total += 1
        status = row.get("status")
        if status not in counts:
            return False
        counts[status] += 1
    return (
        a.claims == total
        and a.match == counts[MATCH]
        and a.drift == counts[DRIFT]
        and a.unverifiable == counts[UNVERIFIABLE]
    )


def _rows(value: object, field: str) -> tuple[dict, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"assessment {field} must be a list of objects")
    out = []
    for index, row in enumerate(value, 1):
        if not isinstance(row, Mapping):
            raise ValueError(f"assessment {field} row {index} must be an object")
        out.append(dict(row))
    return tuple(out)


def _measurement_from_row(r: Mapping) -> Measurement:
    return Measurement(r["claim_id"], r["claim_sha256"], r.get("deviation"), r.get("tolerance", 0.0),
                       r.get("method", ""), 0.0, tuple(r.get("evidence", ())),
                       r.get("recheck") if isinstance(r.get("recheck"), Mapping) else None)


def _replayed_row(value: Measurement | Mapping[str, object]) -> dict:
    return _measurement_row(value) if isinstance(value, Measurement) else dict(value)


def _measurement_inputs_match(stored: Mapping, replayed: Mapping) -> bool:
    return _seal_rows((stored,), _MSEAL_FIELDS) == _seal_rows((replayed,), _MSEAL_FIELDS)


def recheck_measurements(a: Assessment, replayers: Mapping[str, MeasurementReplayer]) -> dict:
    """Re-run measurements that carry a ``recheck`` descriptor.

    Rows without a descriptor are legacy/offline measurements and are skipped, preserving old
    assessment compatibility. A descriptor names its replay function by ``oracle``; the replayed
    measurement must reproduce the stored claim binding, deviation, tolerance, method, and evidence.
    """
    result = {"ok": True, "checked": 0, "skipped": 0, "missing": 0, "mismatched": 0, "failed": 0}
    for row in a.measurements:
        recheck = row.get("recheck")
        if not isinstance(recheck, Mapping):
            result["skipped"] += 1
            continue
        oracle = recheck.get("oracle")
        replay = replayers.get(oracle) if isinstance(oracle, str) else None
        if replay is None:
            result["missing"] += 1
            continue
        result["checked"] += 1
        try:
            if not _measurement_inputs_match(row, _replayed_row(replay(recheck))):
                result["mismatched"] += 1
        except Exception:  # noqa: BLE001 - a replay edge is impure; failure is reported, not raised.
            result["failed"] += 1
    result["ok"] = result["missing"] == result["mismatched"] == result["failed"] == 0
    return result


def recheck_assessment(
    thesis: Thesis,
    a: Assessment,
    *,
    measurement_replayers: Mapping[str, MeasurementReplayer] | None = None,
) -> dict:
    """The strong re-derivation check, from the thesis and the stored measurements. Re-runs
    ``verdict_for`` per claim and confirms the stored verdicts are exactly what the pure function
    yields, so a stored verdict cannot have been asserted. Returns the three sub-checks; all True
    means the assessment is intact AND its verdicts genuinely follow from the measurements."""
    by_id = {m.claim_id: m for m in (_measurement_from_row(r) for r in a.measurements)}
    rederived = [verdict_for(c, by_id.get(c.id)) for c in thesis.claims]
    rederived_rows = [_verdict_row(v) for v in rederived]
    rederived_seal = verdict_seal(rederived)
    stored_rederived = _seal_rows(a.verdicts, _VSEAL_FIELDS) == rederived_seal
    result = {
        "seals_ok": verify_assessment(a),
        "thesis_ok": verify_thesis(thesis) and thesis.seal == a.thesis_seal,
        "verdicts_rederive": (
            stored_rederived
            and a.verdict_seal == rederived_seal
            and _counts_match(a, rederived_rows)
        ),
    }
    if measurement_replayers is not None:
        result["measurements_rerun"] = recheck_measurements(a, measurement_replayers)["ok"]
    return result


def _index_measurements(
    measurements: Mapping[str, Measurement] | Iterable[Measurement] | None,
) -> dict[str, Measurement]:
    if measurements is None:
        return {}
    if isinstance(measurements, Mapping):
        return dict(measurements)
    return {m.claim_id: m for m in measurements}


def _count(verdicts: Iterable[Verdict]) -> dict:
    out = {MATCH: 0, DRIFT: 0, UNVERIFIABLE: 0}
    for v in verdicts:
        out[v.status] = out.get(v.status, 0) + 1
    return out


def assess(
    thesis: Thesis,
    measurements: Mapping[str, Measurement] | Iterable[Measurement] | None = None,
    *,
    clock: Callable[[], float] = time.time,
    registry=None,
) -> tuple[Assessment, list[Verdict]]:
    """Assess a thesis: compute a verdict per claim and fold the outcomes, the verdicts, and the
    measurements into a witnessed, re-derivable record.

    ``measurements`` maps a claim id to its Measurement (or is an iterable keyed by ``claim_id``). A
    claim with no measurement is UNVERIFIABLE. If ``registry`` is given, the record is appended to its
    assessment history. Returns ``(assessment, verdicts)``.
    """
    by_id = _index_measurements(measurements)
    started = float(clock())
    verdicts = [verdict_for(c, by_id.get(c.id)) for c in thesis.claims]
    counts = _count(verdicts)
    vrows = tuple(_verdict_row(v) for v in verdicts)
    mrows = tuple(_measurement_row(m) for m in by_id.values())
    vseal = _seal_rows(vrows, _VSEAL_FIELDS)
    mseal = _measurement_seal(mrows)
    fields = _record_fields(started, thesis.id, thesis.seal, len(thesis.claims),
                            counts[MATCH], counts[DRIFT], counts[UNVERIFIABLE], vseal, mseal, None)
    record = Assessment(started, thesis.id, thesis.seal, len(thesis.claims), counts[MATCH],
                        counts[DRIFT], counts[UNVERIFIABLE], vseal, mseal, vrows, mrows, None,
                        _seal_record(fields))
    if registry is not None:
        registry.register(thesis)  # idempotent; ensures the thesis is on disk so the verdicts re-derive
        registry.add_assessment(record.to_dict())
    return record, verdicts
