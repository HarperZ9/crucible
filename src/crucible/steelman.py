"""The steelman seam: independent adversaries propose the strongest refutation of a claim.

Adversaries PROPOSE the test that would settle a claim; they do not decide. A Refutation names the
challenge and the test, and the measurement step (P3) runs a sound oracle to settle it (that is where
the verdict is decided). This is the conjecture-and-attack half of discovery: propose candidate
invariants, laws, or counterexamples, then let a sound oracle judge them.

The default ``NullSteelman`` stands alone and invents nothing: it surfaces the claim's own stated
falsification as the standing test, or flags a claim that states no falsification as unrefutable. A
model edge (a real independent refuter, proposing attacks the claim did not anticipate) plugs in
through the ``Steelman`` protocol without the core importing it.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Protocol

from crucible.claim import Claim
from crucible.thesis import Thesis


@dataclass(frozen=True, slots=True)
class Refutation:
    """A proposed attack on a claim and the test that would settle it. A proposal, not a verdict.

    ``measurable`` is the test in human and model facing terms: it names what the measurement step
    should run, but it does not itself decide (the sound oracle does, in P3). A structured oracle
    descriptor may be added here at the Measure seam without breaking this shape. ``source`` is the
    name of the steelman that produced the refutation, stamped by ``steelman_thesis``, not
    self-reported, so the label is the producer's.
    """

    claim_id: str
    claim_sha256: str
    challenge: str       # the proposed refutation or attack
    measurable: str      # the test that would settle it, named for the measurement step; "" if none
    source: str          # the producing steelman's name ("null" for the default)


class Steelman(Protocol):
    """The seam where a claim meets its adversary, the optional model edge. ``refute`` proposes zero
    or more refutations of a claim; it never decides the claim (the measurement does). The default is
    the deterministic ``NullSteelman``, so crucible stands alone; a model plugs in through this shape."""

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

    The ``source`` of each refutation is stamped here from the steelman's own ``name``, so the label
    is the producer's and cannot be misreported inside ``refute`` (mechanical honesty, the way a
    synthesis is stamped by its producer, not its caller). Each refutation's ``measurable`` names the
    test the measurement step should run.
    """
    out: list[Refutation] = []
    for c in thesis.claims:
        for r in steelman.refute(c):
            out.append(dataclasses.replace(r, source=steelman.name))
    return out
