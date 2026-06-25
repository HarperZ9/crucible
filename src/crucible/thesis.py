"""A Thesis: a set of claims with a re-checkable seal over them.

The seal folds in the title, the disposition, and each claim's id and content hash. The claims are
sorted, so the seal is over the SET of claims: swapping a claim's content or relabelling its id
breaks it; reordering does not, because a thesis is a set. The disposition is sealed, so a fenced
thesis cannot be relabelled publishable without breaking the seal. The registration time is metadata
and is not sealed.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Callable

from crucible.claim import Claim

PUBLISHABLE = "publishable"
FENCED = "fenced"


def thesis_seal(title: str, disposition: str, claims: tuple[Claim, ...]) -> str:
    """A deterministic fingerprint over a thesis, recomputable from the record.

    Folds in the title, the disposition (so a fenced thesis cannot be relabelled publishable
    undetected), and each claim's id and content hash. The claims are sorted, so the seal is over the
    set: swapping a claim's content or relabelling its id breaks the seal; reordering does not.
    """
    objs = [{"id": c.id, "sha256": c.sha256} for c in claims]
    objs.sort(key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False))
    payload = {"title": title, "disposition": disposition, "claims": objs}
    canon = json.dumps(payload, sort_keys=True, ensure_ascii=False)
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
    seal, so identical thesis content yields the same id. The disposition must be publishable or fenced.
    """
    t = title.strip()
    if not t:
        raise ValueError("a thesis needs a non-empty title")
    cs = tuple(claims)
    if not cs:
        raise ValueError("a thesis needs at least one claim")
    if disposition not in (PUBLISHABLE, FENCED):
        raise ValueError(f"disposition must be {PUBLISHABLE!r} or {FENCED!r}, got {disposition!r}")
    seal = thesis_seal(t, disposition, cs)
    return Thesis(id=id or seal[:16], title=t, claims=cs, registered_at=float(clock()),
                  disposition=disposition, seal=seal)


def verify_thesis(t: Thesis) -> bool:
    """Recompute the seal and verify each claim: the thesis is these claims, with this title and
    disposition, unaltered. Catches a body edit (a claim no longer hashes), a claim swap or
    relabelling, and a flipped disposition. It cannot detect a fully consistent re-forge (every field
    and the seal rewritten together): the seal proves integrity, not authorship."""
    return thesis_seal(t.title, t.disposition, t.claims) == t.seal and all(c.verify() for c in t.claims)
