"""A Claim: the atomic receipted unit of judgment, fingerprinted by its content.

A claim is an assertion together with the observation that would refute it. Its sha256 binds both,
so a tampered claim is caught by re-hashing, and a verdict can bind to an exact claim. A claim with
no falsification condition makes no testable prediction, so it can only ever be judged UNVERIFIABLE.

A claim MAY also seal the numeric ``tolerance`` that will decide MATCH/DRIFT. When it does, the
deciding number is part of the receipt: a measurement adjudicated under any other tolerance is
refused (fail-closed UNVERIFIABLE), so a verdict cannot be rescued by widening the tolerance after
the seal. Claims without a sealed tolerance keep their exact legacy hashes.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass


def content_hash(text: str) -> str:
    """The sha256 of a piece of text, as 64 hex characters. Pure and deterministic."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def claim_body(text: str, falsification: str, tolerance: float | None = None) -> str:
    """The canonical serialization of a claim's content (named-key JSON, sorted keys).

    This is the body that is content-addressed in the registry; its sha256 is the claim's receipt.
    Both the hash and the stored body derive from this one function, so they can never drift.
    The tolerance key exists only when a tolerance is sealed, so legacy bodies are byte-identical.
    """
    obj: dict[str, object] = {"text": text, "falsification": falsification}
    if tolerance is not None:
        obj["tolerance"] = tolerance
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def claim_hash(text: str, falsification: str, tolerance: float | None = None) -> str:
    """The content hash binding a claim's assertion, its falsification condition, and, when
    sealed, the tolerance that will decide its verdict."""
    return content_hash(claim_body(text, falsification, tolerance))


def claim_row(claim: "Claim") -> dict:
    """The canonical export/spec serialization of a claim's receipt: id, text, falsification, sha256,
    and the sealed tolerance WHEN sealed. The tolerance key is present only when a tolerance was
    sealed, mirroring claim_body, so a stranger who reconstructs the claim re-hashes the same body
    and the receipt verifies; unsealed claims stay byte-identical to their legacy rows."""
    row: dict[str, str | float] = {
        "id": claim.id,
        "text": claim.text,
        "falsification": claim.falsification,
        "sha256": claim.sha256,
    }
    if claim.tolerance is not None:
        row["tolerance"] = claim.tolerance
    return row


@dataclass(frozen=True, slots=True)
class Claim:
    """An assertion (``text``) with the observation that would refute it (``falsification``), bound
    by a content hash (``sha256``) and named by an ``id`` (the first 16 hex of the hash by default).
    ``tolerance``, when sealed, is the exact number that must decide this claim's verdict."""

    id: str
    text: str
    falsification: str
    sha256: str
    tolerance: float | None = None

    def verify(self) -> bool:
        """Re-hash the content and confirm it still matches the receipt."""
        return claim_hash(self.text, self.falsification, self.tolerance) == self.sha256


def make_claim(text: str, falsification: str = "", *, tolerance: float | None = None,
               id: str | None = None) -> Claim:
    """Build a claim, computing its content hash. ``text`` must be non-empty.

    The id defaults to the first 16 hex of the content hash. An empty ``falsification`` is allowed
    but the claim then makes no testable prediction, so its verdict can only ever be UNVERIFIABLE.
    ``tolerance``, when given, must be a positive finite number; it is folded into the seal and
    becomes the only tolerance a measurement may use against this claim.
    """
    t = text.strip()
    if not t:
        raise ValueError("a claim needs non-empty text")
    tol: float | None = None
    if tolerance is not None:
        if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
            raise ValueError("a sealed tolerance must be a number")
        tol = float(tolerance)
        if not math.isfinite(tol) or tol <= 0:
            raise ValueError("a sealed tolerance must be positive and finite")
    f = falsification.strip()
    sha = claim_hash(t, f, tol)
    return Claim(id=id or sha[:16], text=t, falsification=f, sha256=sha, tolerance=tol)
