"""Claims: the content hash is the receipt, and re-hashing catches tampering."""
from __future__ import annotations

import pytest

from crucible.claim import claim_body, claim_hash, content_hash, make_claim


def test_content_hash_is_deterministic_sha256_hex():
    h = content_hash("hello")
    assert h == content_hash("hello")
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)


def test_claim_body_is_canonical_named_key_json():
    # Sorted keys, so the mapping from claim to bytes is unambiguous regardless of argument order.
    assert claim_body("a", "b") == '{"falsification": "b", "text": "a"}'


def test_claim_hash_binds_text_and_falsification():
    assert claim_hash("a", "b") != claim_hash("a", "c")
    assert claim_hash("a", "b") != claim_hash("x", "b")
    assert claim_hash("a", "b") == content_hash(claim_body("a", "b"))


def test_make_claim_computes_hash_and_default_id():
    c = make_claim("the sky is blue", "a photo showing a non-blue clear daytime sky")
    assert c.sha256 == claim_hash(c.text, c.falsification)
    assert c.id == c.sha256[:16]
    assert c.verify()


def test_make_claim_strips_and_rejects_empty_text():
    c = make_claim("  spaced  ", "  refute  ")
    assert c.text == "spaced" and c.falsification == "refute"
    with pytest.raises(ValueError):
        make_claim("   ")


def test_tampered_claim_fails_verify():
    import dataclasses

    c = make_claim("two plus two is four", "an arithmetic check returning a different sum")
    tampered = dataclasses.replace(c, text="two plus two is five")
    assert not tampered.verify()


def test_explicit_id_is_kept():
    c = make_claim("x", "y", id="my-id")
    assert c.id == "my-id" and c.verify()


def test_sealed_tolerance_folds_into_the_hash():
    # The number that decides MATCH/DRIFT is part of the sealed claim, so widening it later breaks
    # the receipt instead of rescuing the verdict.
    with_tol = make_claim("k5 interval holds", "pass@5 outside [0.595, 0.737]", tolerance=0.071)
    without = make_claim("k5 interval holds", "pass@5 outside [0.595, 0.737]")
    assert with_tol.tolerance == 0.071
    assert with_tol.sha256 != without.sha256
    assert with_tol.verify()
    assert claim_body("a", "b", 0.05) != claim_body("a", "b", 0.06)


def test_legacy_claim_body_is_byte_identical_without_tolerance():
    # Existing sealed claims and registries keep their hashes: the tolerance key only exists when sealed.
    assert claim_body("a", "b") == '{"falsification": "b", "text": "a"}'
    assert claim_hash("a", "b") == content_hash('{"falsification": "b", "text": "a"}')


def test_sealed_tolerance_must_be_a_positive_finite_number():
    with pytest.raises(ValueError):
        make_claim("x", "y", tolerance=0.0)
    with pytest.raises(ValueError):
        make_claim("x", "y", tolerance=-0.1)
    with pytest.raises(ValueError):
        make_claim("x", "y", tolerance=float("nan"))
