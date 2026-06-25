"""The witnessed assessment: fold a thesis's per-claim verdicts into a re-checkable record.

``assess`` computes a verdict per claim (pure, from each claim's measurement), counts the outcomes,
and seals them into an Assessment with its own seal over the record. The seal recomputes from disk
via ``Assessment.from_dict`` and ``verify_assessment``, so a reader confirms both that the verdicts
are these and that they were not altered. The clock is injected, so the record replays.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping

from crucible.thesis import Thesis
from crucible.verdict import (
    DRIFT,
    MATCH,
    UNVERIFIABLE,
    Measurement,
    Verdict,
    verdict_for,
)

_VFIELDS = ("claim_id", "claim_sha256", "status", "deviation", "tolerance", "method")


def verdict_seal(verdicts: Iterable[Verdict]) -> str:
    """A deterministic fingerprint over the verdicts, recomputable from the record. Folds each
    verdict's claim binding, status, and the measurement inputs (deviation, tolerance, method), so
    changing a status or a measurement breaks the seal. Order independent (the verdicts are sorted)."""
    objs = [{k: getattr(v, k) for k in _VFIELDS} for v in verdicts]
    objs.sort(key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False))
    canon = json.dumps(objs, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _record_fields(started_at: float, thesis_id: str, thesis_seal: str, claims: int, match: int,
                   drift: int, unverifiable: int, vseal: str, stored: dict | None) -> dict:
    return {
        "started_at": started_at, "thesis_id": thesis_id, "thesis_seal": thesis_seal,
        "claims": claims, "match": match, "drift": drift, "unverifiable": unverifiable,
        "verdict_seal": vseal, "stored": stored,
    }


def _seal_record(fields: dict) -> str:
    return hashlib.sha256(
        json.dumps(fields, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class Assessment:
    """A witnessed assessment of one thesis: when it ran, the thesis seal, the verdict counts, the
    seal over the verdicts, and a seal over the whole record."""

    started_at: float
    thesis_id: str
    thesis_seal: str
    claims: int
    match: int
    drift: int
    unverifiable: int
    verdict_seal: str
    stored: dict | None
    seal: str

    def to_dict(self) -> dict:
        fields = _record_fields(self.started_at, self.thesis_id, self.thesis_seal, self.claims,
                                self.match, self.drift, self.unverifiable, self.verdict_seal, self.stored)
        return {**fields, "seal": self.seal}

    @staticmethod
    def from_dict(d: Mapping) -> "Assessment":
        return Assessment(d["started_at"], d["thesis_id"], d["thesis_seal"], d["claims"],
                          d["match"], d["drift"], d["unverifiable"], d["verdict_seal"],
                          d.get("stored"), d["seal"])


def verify_assessment(a: Assessment) -> bool:
    """Recompute the record's seal from its fields and confirm it matches (the record is unaltered).
    Works on an Assessment reconstructed from disk via ``from_dict`` too."""
    fields = _record_fields(a.started_at, a.thesis_id, a.thesis_seal, a.claims, a.match, a.drift,
                            a.unverifiable, a.verdict_seal, a.stored)
    return _seal_record(fields) == a.seal


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
    """Assess a thesis: compute a verdict per claim and fold the outcomes into a witnessed record.

    ``measurements`` maps a claim id to its Measurement (or is an iterable of Measurements keyed by
    their ``claim_id``). A claim with no measurement is UNVERIFIABLE. If ``registry`` is given, the
    record is appended to its assessment history. Returns ``(assessment, verdicts)``.
    """
    by_id = _index_measurements(measurements)
    started = float(clock())
    verdicts = [verdict_for(c, by_id.get(c.id)) for c in thesis.claims]
    counts = _count(verdicts)
    vseal = verdict_seal(verdicts)
    fields = _record_fields(started, thesis.id, thesis.seal, len(thesis.claims),
                            counts[MATCH], counts[DRIFT], counts[UNVERIFIABLE], vseal, None)
    record = Assessment(started, thesis.id, thesis.seal, len(thesis.claims), counts[MATCH],
                        counts[DRIFT], counts[UNVERIFIABLE], vseal, None, _seal_record(fields))
    if registry is not None:
        registry.add_assessment(record.to_dict())
    return record, verdicts
