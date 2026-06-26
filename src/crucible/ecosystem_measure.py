"""Peer-product interop for Gather digests and index verifications.

This module consumes the sibling products through their JSON contracts, not their internals. Gather
digests prove that an evidence receipt existed in a sealed run; index verification records prove that
a structural claim reproduces against a supplied graph pack. Both become normal crucible
``Measurement`` objects, so ``verdict_for`` remains the only verdict spine.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Mapping, Sequence

from crucible.claim import Claim
from crucible.verdict import Measurement

MATCH = "MATCH"
REFUTED = "REFUTED"
DRIFT = "DRIFT"
UNVERIFIABLE = "UNVERIFIABLE"

GATHER_FIELDS = ("kind", "id", "title", "source", "ref", "method", "sha256")
INDEX_VERIFICATION_SCHEMA = "index.verification/1"


def canonical_sha(obj: object) -> str:
    """index's canonical SHA-256: compact sorted JSON, then SHA-256."""
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def verify_gather_digest(digest: object) -> dict:
    """Recompute a Gather digest's seal from its receipts."""
    ok, clean, seal, reason = _gather_digest_parts(digest)
    if not ok:
        return {"ok": False, "matches": False, "reason": reason}
    assert clean is not None and seal is not None
    computed = _gather_seal(clean)
    if computed != seal:
        return {"ok": False, "matches": False, "reason": "seal mismatch"}
    return {"ok": True, "matches": True, "receipts": len(clean), "seal": seal}


def receipt_matches(receipt: Mapping, selector: Mapping) -> bool:
    """Return True when every receipt selector field matches this Gather receipt."""
    fields = [k for k in GATHER_FIELDS + ("derived_from",) if k in selector]
    if not fields:
        return False
    for key in fields:
        expected = selector[key]
        actual = receipt.get(key)
        if key == "derived_from":
            if list(actual or []) != list(expected or []):
                return False
        elif actual != expected:
            return False
    return True


class GatherDigestMeasure:
    """Measure a claim by asking whether a verified Gather digest contains a receipt.

    ``digests`` maps names to Gather digest JSON objects. ``selectors`` maps a crucible claim id or
    exact claim text to receipt fields, with optional ``digest`` naming which digest to search. A
    verified digest with a matching receipt yields deviation 0.0; a verified digest without the
    receipt yields 2.0; malformed or missing digests fail closed as unmeasurable.
    """

    name = "gather"

    def __init__(
        self,
        digests: Mapping[str, Mapping],
        selectors: Mapping[str, Mapping],
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._digests = dict(digests)
        self._selectors = dict(selectors)
        self._clock = clock

    def measure(self, claim: Claim) -> Measurement:
        selector = self._selectors.get(claim.id) or self._selectors.get(claim.text)
        if selector is None:
            return self._measurement(claim, None, ("no Gather selector for claim",))
        digest_key = _digest_key(selector, self._digests)
        if digest_key is None:
            return self._measurement(claim, None, ("no Gather digest selected for claim",))
        digest = self._digests.get(digest_key)
        if digest is None:
            return self._measurement(claim, None, (f"Gather digest {digest_key} is missing",))
        ok, receipts, seal, reason = _gather_digest_parts(digest)
        if not ok or receipts is None or seal is None:
            return self._measurement(claim, None, (str(reason),))
        computed = _gather_seal(receipts)
        if computed != seal:
            return self._measurement(claim, None, ("seal mismatch",))
        found = any(receipt_matches(r, selector) for r in receipts)
        evidence = (f"digest {digest_key} verified seal {seal[:16]}...",)
        if found:
            return self._measurement(claim, 0.0, evidence + ("receipt selector matched",))
        return self._measurement(claim, 2.0, evidence + ("receipt selector did not match",))

    def _measurement(self, claim: Claim, deviation: float | None,
                     evidence: tuple[str, ...]) -> Measurement:
        return Measurement(claim.id, claim.sha256, deviation, 1.0, "gather:digest",
                           float(self._clock()), evidence)


def verify_index_verification(verification: object, packs: Mapping[str, Mapping]) -> dict:
    """Replay an ``index.verification/1`` record against the supplied graph pack."""
    if not isinstance(verification, Mapping):
        return {"ok": False, "matches": False, "reason": "not an index verification"}
    if verification.get("schema") != INDEX_VERIFICATION_SCHEMA:
        return {"ok": False, "matches": False, "reason": "not an index verification"}
    claim = verification.get("claim")
    if not isinstance(claim, Mapping):
        return {"ok": False, "matches": False, "reason": "verification claim is missing"}
    content_sha = verification.get("content_sha256")
    if not isinstance(content_sha, str):
        return {"ok": False, "matches": False, "reason": "content_sha256 is missing"}
    pack = packs.get(content_sha)
    if pack is None:
        return {"ok": False, "matches": False, "reason": f"no index pack for {content_sha!r}"}
    if canonical_sha(pack) != content_sha:
        return {"ok": False, "matches": False, "reason": "index pack hash mismatch"}
    reproduced = _index_verdict(_verify_index_claim(pack, claim)["verdict"])
    carried = _index_verdict(verification.get("verdict"))
    return {"ok": True, "reproduced": reproduced, "carried": carried, "matches": reproduced == carried}


class IndexMeasure:
    """Measure claims by replaying index verification records against supplied graph packs."""

    name = "index"

    def __init__(
        self,
        verifications: Mapping[str, Mapping],
        packs: Mapping[str, Mapping],
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._verifications = dict(verifications)
        self._packs = dict(packs)
        self._clock = clock

    def measure(self, claim: Claim) -> Measurement:
        verification = self._verifications.get(claim.id) or self._verifications.get(claim.text)
        if verification is None:
            return self._measurement(claim, None, ("no index verification for claim",))
        result = verify_index_verification(verification, self._packs)
        if not result.get("ok"):
            return self._measurement(claim, None, (str(result.get("reason", "")),))
        reproduced = str(result["reproduced"])
        evidence = (
            f"index verification reproduced {reproduced}",
            f"carried {result['carried']}; matches {result['matches']}",
        )
        if reproduced == MATCH and result.get("matches"):
            return self._measurement(claim, 0.0, evidence)
        if reproduced in (REFUTED, DRIFT):
            return self._measurement(claim, 2.0, evidence)
        return self._measurement(claim, None, evidence)

    def _measurement(self, claim: Claim, deviation: float | None,
                     evidence: tuple[str, ...]) -> Measurement:
        return Measurement(claim.id, claim.sha256, deviation, 1.0, "index:verification",
                           float(self._clock()), evidence)


def _gather_digest_parts(digest: object) -> tuple[bool, list[dict] | None, str | None, str]:
    if not isinstance(digest, Mapping):
        return False, None, None, "not a Gather digest"
    raw_receipts = digest.get("receipts")
    seal = digest.get("seal")
    if not isinstance(raw_receipts, Sequence) or isinstance(raw_receipts, (str, bytes)):
        return False, None, None, "digest receipts are missing"
    if not isinstance(seal, str) or len(seal) != 64:
        return False, None, None, "digest seal is missing"
    clean: list[dict] = []
    for n, receipt in enumerate(raw_receipts, 1):
        if not isinstance(receipt, Mapping):
            return False, None, None, f"receipt {n} is not an object"
        missing = [k for k in GATHER_FIELDS if k not in receipt]
        if missing:
            return False, None, None, f"receipt {n} missing required field(s) {missing}"
        clean.append({**{k: receipt[k] for k in GATHER_FIELDS},
                      "derived_from": list(receipt.get("derived_from") or [])})
    return True, clean, seal, ""


def _gather_seal(receipts: list[dict]) -> str:
    objs = [
        {
            "sha256": r["sha256"], "kind": r["kind"], "id": r["id"], "title": r["title"],
            "source": r["source"], "ref": r["ref"], "method": r["method"],
            "derived_from": list(r.get("derived_from") or []),
        }
        for r in receipts
    ]
    objs.sort(key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False))
    canon = json.dumps(objs, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _digest_key(selector: Mapping, digests: Mapping[str, Mapping]) -> str | None:
    key = selector.get("digest")
    if isinstance(key, str):
        return key
    if len(digests) == 1:
        return next(iter(digests))
    return None


def _index_verdict(value: object) -> str:
    text = str(value).upper()
    return text if text in (MATCH, REFUTED, DRIFT, UNVERIFIABLE) else UNVERIFIABLE


def _index_names(pack: Mapping) -> set[str]:
    roles = pack.get("roles")
    names = set(roles.keys()) if isinstance(roles, Mapping) else set()
    relations = pack.get("relations") or []
    if isinstance(relations, Sequence) and not isinstance(relations, (str, bytes)):
        for rel in relations:
            if isinstance(rel, Mapping):
                if rel.get("from"):
                    names.add(str(rel["from"]))
                if rel.get("to"):
                    names.add(str(rel["to"]))
    return names


def _verify_index_claim(pack: Mapping, claim: Mapping) -> dict:
    kind = claim.get("kind")
    names = _index_names(pack)
    if kind == "exists":
        name = claim.get("name")
        if name in names:
            return {"verdict": MATCH}
        return {"verdict": REFUTED}
    if kind == "depends":
        frm, to = claim.get("from"), claim.get("to")
        if frm not in names or to not in names:
            return {"verdict": UNVERIFIABLE}
        relations = pack.get("relations") or []
        if isinstance(relations, Sequence) and not isinstance(relations, (str, bytes)):
            for rel in relations:
                if (isinstance(rel, Mapping) and not rel.get("external")
                        and rel.get("from") == frm and rel.get("to") == to):
                    return {"verdict": MATCH}
        return {"verdict": REFUTED}
    return {"verdict": UNVERIFIABLE}
