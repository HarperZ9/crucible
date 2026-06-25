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
from crucible.measure import (
    Measure,
    MetricSpec,
    NullMeasure,
    TableMeasure,
    measure_thesis,
)
from crucible.registry import Registry
from crucible.steelman import NullSteelman, Refutation, Steelman, steelman_thesis
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

__version__ = "0.3.0"

__all__ = [
    "Assessment", "Claim", "Measure", "Measurement", "MetricSpec", "NullMeasure", "NullSteelman",
    "Refutation", "Registry", "Steelman", "TableMeasure", "Thesis", "Verdict",
    "DRIFT", "FENCED", "MATCH", "PUBLISHABLE", "UNVERIFIABLE",
    "assess", "claim_body", "claim_hash", "content_hash", "make_claim", "make_thesis",
    "measure_thesis", "recheck_assessment", "steelman_thesis", "thesis_seal", "verdict_for",
    "verdict_seal", "verify_assessment", "verify_thesis", "__version__",
]
