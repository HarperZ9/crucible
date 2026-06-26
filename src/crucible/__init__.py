"""crucible: an accountable judgment organ.

Register a thesis and emit a re-checkable verdict per claim (MATCH / DRIFT / UNVERIFIABLE), grounded
in a measurement rather than asserted: the verdict recomputes from the record, so a confident
assertion has no effect on the rechecked result. A thesis is steelmanned (adversaries propose the
test), measured against a sound oracle (the measurement decides), and refined toward a cohesively
verified standing or an honest weakest axis. The core is pure standard library; impure and optional
edges live behind Protocol seams with a Null default, so crucible stands alone and composes as a peer.
"""
from __future__ import annotations

from crucible.assess import (
    Assessment,
    assess,
    recheck_assessment,
    recheck_measurements,
    verdict_seal,
    verify_assessment,
)
from crucible.claim import Claim, claim_body, claim_hash, content_hash, make_claim
from crucible.drift import (
    DriftReport,
    DriftRow,
    drift_track,
)
from crucible.ecosystem_measure import (
    GatherDigestMeasure,
    IndexMeasure,
    canonical_sha,
    receipt_matches,
    verify_gather_digest,
    verify_index_verification,
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
    margin,
    refine,
    refine_thesis,
)
from crucible.registry import Registry
from crucible.registry_ops import prune_objects, registry_stats, search_theses
from crucible.report import render_assessment_report
from crucible.steelman import NullSteelman, Refutation, Steelman, steelman_thesis
from crucible.subprocess_edges import SubprocessMeasure, SubprocessSteelman
from crucible.telos_measure import (
    TelosMeasure,
    check_content,
    is_telos_artifact,
    verify_telos_artifact,
)
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

__version__ = "1.1.0"

__all__ = [
    "Assessment", "Claim", "DriftReport", "DriftRow", "GatherDigestMeasure", "GradedCriterion",
    "IndexMeasure", "Measure", "Measurement", "MetricSpec", "NullMeasure", "NullSteelman",
    "RefineOutcome", "RefineReport", "Reflection", "Refutation", "Registry", "Steelman",
    "SubprocessMeasure", "SubprocessSteelman", "TableMeasure",
    "TelosMeasure", "Thesis", "Verdict",
    "DRIFT", "FENCED", "MATCH", "PUBLISHABLE", "UNVERIFIABLE",
    "assess", "claim_body", "claim_hash", "cohesion", "content_hash", "make_claim", "make_thesis",
    "canonical_sha", "check_content", "drift_track", "export_guard", "export_thesis", "gate_check",
    "is_telos_artifact", "measure_thesis", "receipt_matches",
    "recheck_assessment", "recheck_measurements", "refine", "refine_thesis", "render_assessment_report",
    "steelman_thesis", "margin",
    "prune_objects", "registry_stats", "search_theses", "thesis_seal", "verdict_for", "verdict_seal",
    "verify_assessment", "verify_gather_digest", "verify_index_verification", "verify_telos_artifact",
    "verify_thesis", "__version__",
]
