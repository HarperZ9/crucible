"""crucible: an accountable judgment organ.

Register a thesis and emit a re-checkable verdict per claim (MATCH / DRIFT / UNVERIFIABLE), grounded
in a measurement rather than asserted: the verdict recomputes from the record, so a confident
assertion cannot fake it. A thesis is steelmanned (adversaries propose the test), measured against a
sound oracle (the measurement decides), and refined toward a cohesively verified standing or an honest
weakest axis. The core is pure standard library; impure and optional edges live behind Protocol seams
with a Null default, so crucible stands alone and composes as a peer.
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
from crucible.drift import (
    DriftReport,
    DriftRow,
    drift_track,
)
from crucible.gate import export_guard, export_thesis, gate_check
from crucible.measure import (
    Measure,
    MetricSpec,
    NullMeasure,
    TableMeasure,
    measure_thesis,
)
from crucible.refine import (
    GradedCriterion,
    RefineOutcome,
    RefineReport,
    Reflection,
    cohesion,
    refine,
    refine_thesis,
)
from crucible.registry import Registry
from crucible.registry_ops import prune_objects, registry_stats, search_theses
from crucible.steelman import NullSteelman, Refutation, Steelman, steelman_thesis
from crucible.subprocess_edges import SubprocessMeasure, SubprocessSteelman
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

__version__ = "0.9.0"

__all__ = [
    "Assessment", "Claim", "DriftReport", "DriftRow", "GradedCriterion", "Measure", "Measurement",
    "MetricSpec", "NullMeasure", "NullSteelman", "RefineOutcome", "RefineReport", "Reflection",
    "Refutation", "Registry", "Steelman", "SubprocessMeasure", "SubprocessSteelman", "TableMeasure",
    "Thesis", "Verdict",
    "DRIFT", "FENCED", "MATCH", "PUBLISHABLE", "UNVERIFIABLE",
    "assess", "claim_body", "claim_hash", "cohesion", "content_hash", "make_claim", "make_thesis",
    "drift_track", "export_guard", "export_thesis", "gate_check", "measure_thesis",
    "recheck_assessment", "refine", "refine_thesis", "steelman_thesis",
    "prune_objects", "registry_stats", "search_theses", "thesis_seal", "verdict_for", "verdict_seal",
    "verify_assessment", "verify_thesis", "__version__",
]
