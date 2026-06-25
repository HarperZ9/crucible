"""Crucible: an accountable judgment organ.

Register a thesis, steelman it, measure it against a substrate, and emit a re-checkable verdict per
claim (MATCH / DRIFT / UNVERIFIABLE). The verdict is grounded in the measurement, not a judge's
say-so, and recomputes from the record. The core is pure standard library; impure and optional edges
live behind Protocol seams with a Null default, so Crucible stands alone and composes as a peer.
"""
from __future__ import annotations

from crucible.assess import Assessment, assess, verdict_seal, verify_assessment
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
    "thesis_seal", "verdict_for", "verdict_seal", "verify_assessment", "verify_thesis",
    "__version__",
]
