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
