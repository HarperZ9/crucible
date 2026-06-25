from __future__ import annotations

import pytest

from crucible.claim import make_claim
from crucible.gate import export_guard, export_thesis, gate_check
from crucible.thesis import FENCED, PUBLISHABLE, make_thesis


def _thesis(*, title="public theorem", disposition=PUBLISHABLE, claim_text="claim"):
    return make_thesis(
        title,
        (make_claim(claim_text, "counterexample"),),
        clock=lambda: 1.0,
        disposition=disposition,
    )


def test_gate_check_allows_publishable_thesis_without_fenced_markers():
    assert gate_check(_thesis()) == PUBLISHABLE


def test_gate_check_refuses_explicit_fenced_disposition():
    assert gate_check(_thesis(disposition=FENCED)) == FENCED


def test_gate_check_refuses_restricted_markers_in_claim_content():
    thesis = _thesis(claim_text="[RESTRICTED] claim from protected corpus")
    assert gate_check(thesis) == FENCED


def test_export_guard_refuses_fenced_thesis():
    with pytest.raises(PermissionError, match="fenced"):
        export_guard(_thesis(disposition=FENCED))


def test_export_thesis_returns_public_claim_contract_without_runtime_metadata():
    thesis = _thesis()
    exported = export_thesis(thesis)

    assert exported["id"] == thesis.id
    assert exported["title"] == thesis.title
    assert exported["disposition"] == PUBLISHABLE
    assert exported["seal"] == thesis.seal
    assert "registered_at" not in exported
    assert exported["claims"][0]["text"] == "claim"
    assert exported["claims"][0]["sha256"] == thesis.claims[0].sha256
