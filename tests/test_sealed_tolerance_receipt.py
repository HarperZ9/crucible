"""A sealed tolerance is part of the claim's receipt; it must cross every receipt boundary.

The claim's sha256 embeds the sealed tolerance (claim_body). If export, the bundle spec.json, or the
cleanroom review reconstruction drops the tolerance, the reconstructed claim re-hashes without it,
mismatches the stored sha256, and every honestly-sealed thesis becomes unreviewable -- which quietly
pressures authors to leave claims unsealed. These tests pin the tolerance to the export and review
surfaces. Legacy (unsealed) claims must stay byte-identical: no tolerance key when none was sealed.
"""
from __future__ import annotations

from crucible.claim import make_claim
from crucible.gate import export_thesis
from crucible.review_contract import claim_from_spec
from crucible.thesis import make_thesis

CLOCK = lambda: 1000.0  # noqa: E731


def test_export_carries_a_sealed_tolerance_and_review_reconstructs_it():
    claim = make_claim("latency stays under budget", "latency grows", tolerance=0.05)
    thesis = make_thesis("sealed", (claim,), clock=CLOCK)

    row = export_thesis(thesis)["claims"][0]
    assert row["tolerance"] == 0.05

    findings: list[str] = []
    reconstructed = claim_from_spec(row, 0, findings)
    assert findings == []
    assert reconstructed is not None
    assert reconstructed.tolerance == 0.05
    assert reconstructed.verify()  # re-hash with the tolerance matches the sealed sha256


def test_export_omits_the_tolerance_key_for_an_unsealed_claim():
    claim = make_claim("quality stays above floor", "quality drops")
    thesis = make_thesis("legacy", (claim,), clock=CLOCK)

    row = export_thesis(thesis)["claims"][0]
    assert "tolerance" not in row

    findings: list[str] = []
    reconstructed = claim_from_spec(row, 0, findings)
    assert findings == []
    assert reconstructed is not None
    assert reconstructed.tolerance is None
    assert reconstructed.verify()
