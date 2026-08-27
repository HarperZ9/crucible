#!/usr/bin/env python3
"""verify_seals.py -- a zero-dependency, standalone verifier for a crucible assessment artifact.
Pure Python stdlib, no crucible import. A stranger holding only the assessment JSON re-derives its
seals offline:

    python verify_seals.py assessment.json

It re-computes the three content-hash seals over the artifact's OWN canonical rows -- the verdict
seal (over the verdict rows), the measurement seal (over the measurement rows), and the record seal
(over the sealed record fields) -- plus the count cross-check, then compares each to the value the
artifact carries. A flipped byte in any sealed row, or a doctored count, snaps a seal. Prints one
line and exits 0 = MATCH, 1 = DRIFT (a seal or count mismatch), 2 = UNVERIFIABLE (artifact missing,
unreadable, or not a crucible assessment).

Scope (honest null): this file re-derives the seal integrity of the record only. The claim-body
content_hash that Registry.verify checks needs the registry object store (the claim bodies are not in
the assessment artifact), and the re-scoring recheck needs the crucible package to re-run verdict_for;
neither is re-derivable from the artifact alone, so neither is claimed here.
"""
import hashlib
import json
import sys

MATCH = "MATCH"
DRIFT = "DRIFT"
UNVERIFIABLE = "UNVERIFIABLE"

_VSEAL = ("claim_id", "claim_sha256", "status", "deviation", "tolerance", "margin", "method",
          "grounds", "disposition")
_MSEAL = ("claim_id", "claim_sha256", "deviation", "tolerance", "method", "measured_at", "evidence")
_MSEAL_RECHECK = _MSEAL + ("recheck",)
_STATUSES = (MATCH, DRIFT, UNVERIFIABLE)
_REQUIRED = frozenset((
    "started_at", "thesis_id", "thesis_seal", "claims", "match", "drift", "unverifiable",
    "verdict_seal", "measurement_seal", "seal",
))


def _seal_rows(rows, fields):
    """The seal crucible folds over a set of rows: keep only the named fields, sort by canonical form
    (order independent), then sha256 the canonical JSON. Byte-for-byte the crucible computation."""
    objs = [{k: r.get(k) for k in fields} for r in rows]
    objs.sort(key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False))
    canon = json.dumps(objs, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _measurement_seal(rows):
    fields = _MSEAL_RECHECK if any("recheck" in r for r in rows) else _MSEAL
    return _seal_rows(rows, fields)


def _record_fields(a):
    return {
        "started_at": a["started_at"], "thesis_id": a["thesis_id"], "thesis_seal": a["thesis_seal"],
        "claims": a["claims"], "match": a["match"], "drift": a["drift"],
        "unverifiable": a["unverifiable"], "verdict_seal": a["verdict_seal"],
        "measurement_seal": a["measurement_seal"], "disposition": a.get("disposition", "publishable"),
        "stored": a.get("stored"),
    }


def _record_seal(a):
    canon = json.dumps(_record_fields(a), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _counts_ok(a, verdicts):
    counts = {s: 0 for s in _STATUSES}
    total = 0
    for row in verdicts:
        total += 1
        status = row.get("status")
        if status not in counts:
            return False
        counts[status] += 1
    return (a.get("claims") == total and a.get("match") == counts[MATCH]
            and a.get("drift") == counts[DRIFT] and a.get("unverifiable") == counts[UNVERIFIABLE])


def verify_seals(a):
    """Re-derive the three seals and the counts from the artifact's own rows; return (label, detail)."""
    verdicts = a.get("verdicts") or []
    measurements = a.get("measurements") or []
    if not _counts_ok(a, verdicts):
        return DRIFT, "verdict counts do not match the sealed record"
    if _seal_rows(verdicts, _VSEAL) != a.get("verdict_seal"):
        return DRIFT, "verdict_seal does not re-derive from the stored verdict rows"
    if _measurement_seal(measurements) != a.get("measurement_seal"):
        return DRIFT, "measurement_seal does not re-derive from the stored measurement rows"
    if _record_seal(a) != a.get("seal"):
        return DRIFT, "record seal does not re-derive from the sealed fields"
    return MATCH, "verdict, measurement, and record seals all re-derive"


def _load(path):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    if isinstance(doc, dict) and isinstance(doc.get("assessment"), dict):
        doc = doc["assessment"]  # unwrap the `assess --json` envelope
    return doc


def main(argv):
    if not argv:
        print("usage: python verify_seals.py <assessment.json>", file=sys.stderr)
        return 2
    try:
        a = _load(argv[0])
    except FileNotFoundError:
        print(f"{UNVERIFIABLE}  artifact not found: {argv[0]}")
        return 2
    except (OSError, ValueError) as exc:
        print(f"{UNVERIFIABLE}  artifact unreadable: {exc}")
        return 2
    if not isinstance(a, dict) or not _REQUIRED.issubset(a):
        print(f"{UNVERIFIABLE}  not a crucible assessment artifact (missing sealed fields)")
        return 2
    label, detail = verify_seals(a)
    print(f"{label}  {detail}")
    return {MATCH: 0, DRIFT: 1}.get(label, 2)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
