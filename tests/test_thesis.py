"""Theses: the seal binds the exact set of claims, order independent, tamper evident."""
from __future__ import annotations

import dataclasses

import pytest

from crucible.claim import make_claim
from crucible.thesis import FENCED, PUBLISHABLE, make_thesis, thesis_seal, verify_thesis

CLOCK = lambda: 1000.0  # noqa: E731 (a fixed injected clock for deterministic tests)


def _claims():
    return [
        make_claim("claim one", "refutation one"),
        make_claim("claim two", "refutation two"),
    ]


def test_make_thesis_seals_and_verifies():
    t = make_thesis("A thesis", _claims(), clock=CLOCK)
    assert t.registered_at == 1000.0
    assert t.disposition == PUBLISHABLE
    assert t.id == t.seal[:16]
    assert verify_thesis(t)


def test_seal_is_order_independent():
    cs = _claims()
    a = make_thesis("t", cs, clock=CLOCK)
    b = make_thesis("t", list(reversed(cs)), clock=CLOCK)
    assert a.seal == b.seal


def test_seal_changes_when_a_claim_changes():
    a = make_thesis("t", _claims(), clock=CLOCK)
    b = make_thesis("t", [make_claim("claim one", "refutation one"),
                          make_claim("claim two CHANGED", "refutation two")], clock=CLOCK)
    assert a.seal != b.seal


def test_tampered_claim_breaks_verify():
    t = make_thesis("t", _claims(), clock=CLOCK)
    bad_claim = dataclasses.replace(t.claims[0], text="rewritten")
    tampered = dataclasses.replace(t, claims=(bad_claim, t.claims[1]))
    assert not verify_thesis(tampered)


def test_dropped_claim_breaks_seal_recheck():
    t = make_thesis("t", _claims(), clock=CLOCK)
    tampered = dataclasses.replace(t, claims=(t.claims[0],))
    assert thesis_seal(tampered.title, tampered.disposition, tampered.claims) != tampered.seal
    assert not verify_thesis(tampered)


def test_flipped_disposition_breaks_seal():
    t = make_thesis("t", _claims(), clock=CLOCK, disposition=PUBLISHABLE)
    relabelled = dataclasses.replace(t, disposition=FENCED)
    assert not verify_thesis(relabelled)  # the disposition is sealed; the publication gate can trust it


def test_relabelled_title_breaks_seal():
    t = make_thesis("t", _claims(), clock=CLOCK)
    assert not verify_thesis(dataclasses.replace(t, title="a different title"))


def test_empty_title_and_empty_claims_rejected():
    with pytest.raises(ValueError):
        make_thesis("  ", _claims(), clock=CLOCK)
    with pytest.raises(ValueError):
        make_thesis("t", [], clock=CLOCK)


def test_fenced_disposition_allowed_bad_rejected():
    t = make_thesis("t", _claims(), clock=CLOCK, disposition=FENCED)
    assert t.disposition == FENCED
    with pytest.raises(ValueError):
        make_thesis("t", _claims(), clock=CLOCK, disposition="secret")
