"""The steelman seam: adversaries propose; they do not decide. The Null default invents nothing."""
from __future__ import annotations

from crucible.claim import make_claim
from crucible.steelman import NullSteelman, Refutation, steelman_thesis
from crucible.thesis import make_thesis

CLOCK = lambda: 1000.0  # noqa: E731


def test_null_steelman_surfaces_the_stated_falsification_as_the_test():
    c = make_claim("the constant is 12.526", "a measurement outside 12.526 plus or minus 0.1")
    refutations = NullSteelman().refute(c)
    assert len(refutations) == 1
    r = refutations[0]
    assert isinstance(r, Refutation)
    assert r.measurable == c.falsification  # the proposed test is exactly the claim's falsification
    assert r.source == "null"
    assert r.claim_id == c.id and r.claim_sha256 == c.sha256


def test_null_steelman_flags_an_unfalsifiable_claim():
    c = make_claim("beauty is the highest value")  # no falsification condition
    r = NullSteelman().refute(c)[0]
    assert r.measurable == ""  # nothing would settle it
    assert "no falsification" in r.challenge


def test_null_steelman_invents_no_independent_attack():
    # The Null default only restates the claim's own falsification; it does not conjure a new attack.
    c = make_claim("p implies q", "an instance where p holds and q fails")
    r = NullSteelman().refute(c)[0]
    assert c.falsification in r.challenge


def test_steelman_thesis_proposes_one_test_per_claim_in_order():
    t = make_thesis("t", [make_claim("a", "ra"), make_claim("b", "rb"), make_claim("c", "rc")], clock=CLOCK)
    refutations = steelman_thesis(NullSteelman(), t)
    assert [r.claim_id for r in refutations] == [c.id for c in t.claims]
    assert all(r.source == "null" for r in refutations)
