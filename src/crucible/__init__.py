"""Crucible: an accountable judgment organ.

Register a thesis and emit a re-checkable verdict per claim (MATCH / DRIFT / UNVERIFIABLE), grounded
in a measurement rather than asserted: the verdict recomputes from the record, so a confident
assertion cannot fake it. The steelman and measurement seams and the continuous refine loop are
forthcoming; the verdict spine and the witnessed, re-derivable record ship first. The core is pure
standard library; impure and optional edges live behind Protocol seams with a Null default, so
Crucible stands alone and composes as a peer.
"""
from __future__ import annotations

from crucible.assess import (
    Assessment,
    assess,
    recheck_assessment,
    verdict_seal,
    verify_assessment,
)
from crucible.claim import Claim, claim_body, claim_hash, content_hash, make_claim
from crucible.registry import Registry
from crucible.thesis import (
    FENCED,
    PUBLISHABLE,
    Thesis,
    make_thesis,
    thesis_seal,
    verify_thesis,
)
from crucible.verdict import (
    DRIFT,
    MATCH,
    UNVERIFIABLE,
    Measurement,
    Verdict,
    verdict_for,
)

__version__ = "0.1.0"

__all__ = [
    "Assessment", "Claim", "Measurement", "Registry", "Thesis", "Verdict",
    "DRIFT", "FENCED", "MATCH", "PUBLISHABLE", "UNVERIFIABLE",
    "assess", "claim_body", "claim_hash", "content_hash", "make_claim", "make_thesis",
    "recheck_assessment", "thesis_seal", "verdict_for", "verdict_seal", "verify_assessment",
    "verify_thesis", "__version__",
]
