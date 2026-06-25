"""The steelman seam: independent adversaries propose the strongest refutation of a claim.

Adversaries PROPOSE what to test; they do not decide. A Refutation carries the challenge and the
measurable test that would settle it, and that test feeds the measurement step, where the verdict is
actually decided. This is the conjecture-and-attack half of discovery: propose candidate invariants,
laws, or counterexamples, then let a sound oracle judge them.

The default ``NullSteelman`` stands alone and invents nothing: it surfaces the claim's own stated
falsification as the standing test, or flags a claim that states no falsification as unrefutable. A
model edge (a real independent refuter, proposing attacks the claim did not anticipate) plugs in
through the ``Steelman`` protocol without the core importing it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from crucible.claim import Claim
from crucible.thesis import Thesis


@dataclass(frozen=True, slots=True)
class Refutation:
    """A proposed attack on a claim and the test that would settle it. A proposal, not a verdict."""

    claim_id: str
    claim_sha256: str
    challenge: str       # the proposed refutation or attack
    measurable: str      # the test that would settle it (feeds the measurement step); "" if none
    source: str          # "null" or the name of the model edge that proposed it


class Steelman(Protocol):
    """The seam where a claim meets its adversary, the optional model edge. ``refute`` proposes zero
    or more refutations of a claim; it never decides the claim (the measurement does). The default is
    the deterministic ``NullSteelman``, so Crucible stands alone; a model plugs in through this shape."""

    name: str

    def refute(self, claim: Claim) -> tuple[Refutation, ...]: ...


class NullSteelman:
    """The standing default: deterministic, invents nothing. It restates the claim's own falsification
    condition as the standing test, or flags an unfalsifiable claim. Real independent refutation (a
    model proposing attacks the claim did not anticipate) requires a model on the Steelman seam."""

    name = "null"

    def refute(self, claim: Claim) -> tuple[Refutation, ...]:
        if not claim.falsification:
            return (Refutation(claim.id, claim.sha256,
                               "the claim states no falsification condition, so it cannot be refuted",
                               "", self.name),)
        return (Refutation(claim.id, claim.sha256,
                           f"test the stated falsification: {claim.falsification}",
                           claim.falsification, self.name),)


def steelman_thesis(steelman: Steelman, thesis: Thesis) -> list[Refutation]:
    """Run a steelman over every claim in a thesis, returning all proposed refutations in claim order.
    Each refutation's ``measurable`` is what the measurement step should test."""
    out: list[Refutation] = []
    for c in thesis.claims:
        out.extend(steelman.refute(c))
    return out
