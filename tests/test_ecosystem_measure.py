from __future__ import annotations

import hashlib
import json

from crucible.claim import make_claim
from crucible.ecosystem_measure import (
    GatherDigestMeasure,
    IndexMeasure,
    canonical_sha,
    verify_gather_digest,
    verify_index_verification,
)
from crucible.verdict import DRIFT, MATCH, UNVERIFIABLE, verdict_for

CLOCK = lambda: 2000.0  # noqa: E731


def _gather_seal(receipts: list[dict]) -> str:
    objs = [
        {
            "sha256": r["sha256"],
            "kind": r["kind"],
            "id": r["id"],
            "title": r["title"],
            "source": r["source"],
            "ref": r["ref"],
            "method": r["method"],
            "derived_from": list(r.get("derived_from") or []),
        }
        for r in receipts
    ]
    objs.sort(key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False))
    canon = json.dumps(objs, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _receipt(**overrides):
    row = {
        "kind": "paper",
        "id": "paper-1",
        "title": "Telos abstract math note",
        "source": "arxiv",
        "ref": "https://example.test/paper",
        "method": "http-get",
        "sha256": "a" * 64,
        "derived_from": [],
    }
    row.update(overrides)
    return row


def _digest(receipts: list[dict]):
    return {"receipts": receipts, "seal": _gather_seal(receipts)}


def _pack(relations=(), roles=None):
    return {"relations": list(relations), "roles": roles or {"api": [], "core": []}}


def _index_verification(pack: dict, claim: dict, verdict: str):
    return {
        "schema": "index.verification/1",
        "tool_version": "2.0.0",
        "claim": claim,
        "verdict": verdict,
        "evidence": None,
        "detail": "carried by index",
        "content_sha256": canonical_sha(pack),
        "recheck": "index verify --root . --json",
    }


def test_canonical_sha_uses_unescaped_unicode_canonical_json():
    pack = {"roles": {"π": []}, "relations": [{"from": "π", "to": "core"}]}
    canon = json.dumps(pack, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    assert canonical_sha(pack) == hashlib.sha256(canon.encode("utf-8")).hexdigest()


def test_verify_gather_digest_recomputes_seal_and_rejects_tampering():
    digest = _digest([_receipt()])

    assert verify_gather_digest(digest) == {
        "ok": True,
        "matches": True,
        "receipts": 1,
        "seal": digest["seal"],
    }

    bad = {"receipts": [{**digest["receipts"][0], "title": "renamed"}], "seal": digest["seal"]}
    result = verify_gather_digest(bad)

    assert result["ok"] is False
    assert result["matches"] is False
    assert "seal" in result["reason"]


def test_gather_digest_measure_maps_present_missing_and_invalid_receipts():
    claim = make_claim("the paper receipt is present", "a verified Gather digest contains paper-1")
    digest = _digest([_receipt()])
    selector = {"digest": "run-1", "id": "paper-1", "sha256": "a" * 64}
    match = GatherDigestMeasure({"run-1": digest}, {claim.id: selector}, clock=CLOCK).measure(claim)
    missing = GatherDigestMeasure({"run-1": digest}, {claim.id: {**selector, "id": "paper-2"}},
                                  clock=CLOCK).measure(claim)
    invalid = GatherDigestMeasure({"run-1": {"receipts": digest["receipts"], "seal": "0" * 64}},
                                  {claim.id: selector}, clock=CLOCK).measure(claim)

    assert match.method == "gather:digest"
    assert match.deviation == 0.0
    assert match.measured_at == 2000.0
    assert "digest run-1 verified" in match.evidence[0]
    assert verdict_for(claim, match).status == MATCH
    assert verdict_for(claim, missing).status == DRIFT
    assert invalid.deviation is None
    assert verdict_for(claim, invalid).status == UNVERIFIABLE


def test_verify_index_verification_replays_pack_claim_and_catches_forgery():
    pack = _pack([{"from": "api", "to": "core", "external": False,
                   "signals": [{"file": "api/main.py", "line": 3}]}])
    claim = {"kind": "depends", "from": "api", "to": "core"}
    verification = _index_verification(pack, claim, "MATCH")

    assert verify_index_verification(verification, {canonical_sha(pack): pack}) == {
        "ok": True,
        "reproduced": "MATCH",
        "carried": "MATCH",
        "matches": True,
    }

    forged = {**verification, "verdict": "UNVERIFIABLE"}
    result = verify_index_verification(forged, {canonical_sha(pack): pack})

    assert result["ok"] is True
    assert result["reproduced"] == "MATCH"
    assert result["matches"] is False


def test_index_measure_maps_index_verdicts_into_crucible_verdicts():
    pack = _pack()
    pack_sha = canonical_sha(pack)
    match_claim = make_claim("api exists", "index says api exists")
    refuted_claim = make_claim("ghost exists", "index says ghost exists")
    unknown_claim = make_claim("something unknowable", "index cannot evaluate it")
    verifications = {
        match_claim.id: _index_verification(pack, {"kind": "exists", "name": "api"}, "MATCH"),
        refuted_claim.id: _index_verification(pack, {"kind": "exists", "name": "ghost"}, "REFUTED"),
        unknown_claim.id: _index_verification(pack, {"kind": "mystery"}, "UNVERIFIABLE"),
    }
    measure = IndexMeasure(verifications, {pack_sha: pack}, clock=CLOCK)

    match = measure.measure(match_claim)
    refuted = measure.measure(refuted_claim)
    unknown = measure.measure(unknown_claim)
    missing_pack = IndexMeasure({match_claim.id: verifications[match_claim.id]}, {}, clock=CLOCK)

    assert match.method == "index:verification"
    assert match.deviation == 0.0
    assert match.measured_at == 2000.0
    assert verdict_for(match_claim, match).status == MATCH
    assert verdict_for(refuted_claim, refuted).status == DRIFT
    assert verdict_for(unknown_claim, unknown).status == UNVERIFIABLE
    assert missing_pack.measure(match_claim).deviation is None
