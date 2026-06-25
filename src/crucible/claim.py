"""A Claim: the atomic receipted unit of judgment, fingerprinted by its content.

A claim is an assertion together with the observation that would refute it. Its sha256 binds both,
so a tampered claim is caught by re-hashing, and a verdict can bind to an exact claim. A claim with
no falsification condition makes no testable prediction, so it can only ever be judged UNVERIFIABLE.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


def content_hash(text: str) -> str:
    """The sha256 of a piece of text, as 64 hex characters. Pure and deterministic."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def claim_body(text: str, falsification: str) -> str:
    """The canonical serialization of a claim's content (named-key JSON, sorted keys).

    This is the body that is content-addressed in the registry; its sha256 is the claim's receipt.
    Both the hash and the stored body derive from this one function, so they can never drift.
    """
    return json.dumps({"text": text, "falsification": falsification}, sort_keys=True, ensure_ascii=False)


def claim_hash(text: str, falsification: str) -> str:
    """The content hash binding a claim's assertion and its falsification condition."""
    return content_hash(claim_body(text, falsification))


@dataclass(frozen=True, slots=True)
class Claim:
    """An assertion (``text``) with the observation that would refute it (``falsification``), bound
    by a content hash (``sha256``) and named by an ``id`` (the first 16 hex of the hash by default)."""

    id: str
    text: str
    falsification: str
    sha256: str

    def verify(self) -> bool:
        """Re-hash the content and confirm it still matches the receipt."""
        return claim_hash(self.text, self.falsification) == self.sha256


def make_claim(text: str, falsification: str = "", *, id: str | None = None) -> Claim:
    """Build a claim, computing its content hash. ``text`` must be non-empty.

    The id defaults to the first 16 hex of the content hash. An empty ``falsification`` is allowed
    but the claim then makes no testable prediction, so its verdict can only ever be UNVERIFIABLE.
    """
    t = text.strip()
    if not t:
        raise ValueError("a claim needs non-empty text")
    f = falsification.strip()
    sha = claim_hash(t, f)
    return Claim(id=id or sha[:16], text=t, falsification=f, sha256=sha)
