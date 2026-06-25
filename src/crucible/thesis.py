"""A Thesis: a set of claims with a re-checkable seal over them.

The seal is order independent (the claims are sorted) but covers each claim's id and content hash,
so swapping, reordering, or relabelling a claim breaks it exactly as tampering with content does. A
thesis carries a disposition (publishable or fenced) that the publication gate reads at the export
edge.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Callable

from crucible.claim import Claim

PUBLISHABLE = "publishable"
FENCED = "fenced"


def thesis_seal(claims: tuple[Claim, ...]) -> str:
    """A deterministic fingerprint over a thesis's claims, recomputable from the record.

    The claims are sorted by their canonical form, so the seal depends on the set, not the order in
    which they were supplied. Each claim is folded in by its id and content hash.
    """
    objs = [{"id": c.id, "sha256": c.sha256} for c in claims]
    objs.sort(key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False))
    canon = json.dumps(objs, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Thesis:
    """A titled set of claims, registered at a time, with a disposition and a re-checkable seal."""

    id: str
    title: str
    claims: tuple[Claim, ...]
    registered_at: float
    disposition: str
    seal: str


def make_thesis(
    title: str,
    claims: tuple[Claim, ...] | list[Claim],
    *,
    clock: Callable[[], float],
    id: str | None = None,
    disposition: str = PUBLISHABLE,
) -> Thesis:
    """Register a thesis from its claims, computing its seal and stamping the registration time.

    The clock is injected, so a registration replays. The id defaults to the first 16 hex of the
    seal. The disposition must be publishable or fenced.
    """
    t = title.strip()
    if not t:
        raise ValueError("a thesis needs a non-empty title")
    cs = tuple(claims)
    if not cs:
        raise ValueError("a thesis needs at least one claim")
    if disposition not in (PUBLISHABLE, FENCED):
        raise ValueError(f"disposition must be {PUBLISHABLE!r} or {FENCED!r}, got {disposition!r}")
    seal = thesis_seal(cs)
    return Thesis(
        id=id or seal[:16],
        title=t,
        claims=cs,
        registered_at=float(clock()),
        disposition=disposition,
        seal=seal,
    )


def verify_thesis(t: Thesis) -> bool:
    """Recompute the seal and verify each claim: the thesis is these claims, unaltered."""
    return thesis_seal(t.claims) == t.seal and all(c.verify() for c in t.claims)
