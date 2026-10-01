"""Gate Telos creative measurement packets against explicit verifier criteria.

The packet is evidence, not authority. Crucible turns the packet into row-level
MATCH / DRIFT / UNVERIFIABLE verdicts, then derives a separate admission-style
decision outcome for hosts that need to decide whether an output can proceed.
"""
from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime

from crucible.verdict import DRIFT, MATCH, UNVERIFIABLE

TELOS_MEASUREMENT_SCHEMA = "project-telos.measurement-layers/v1"
GATE_SCHEMA = "project-telos.crucible.measurement-gate/v1"

ALLOW = "allow"
BLOCK = "block"
REQUIRE_REVIEW = "require_review"

RAW_PAYLOAD_KEYS = {
    "pixels", "raw_pixels", "raw_payload", "raw_assets", "samples", "waveform_samples",
    "splats", "lights", "tool_args", "prompt", "result_payload",
}

LAYER_FAILURE = {
    "visual.histogram-field": "pixel_dimensions_mismatch",
    "visual.dither-spectrum-meter": "dither_pattern_unverifiable",
    "spatial.splat-probe": "asset_provenance_missing",
    "lighting.cluster-meter": "cluster_budget_exceeded",
    "audio.spectral-meter": "audio_spectrum_unverifiable",
}


def verify_measurement_packet(
    packet: object,
    *,
    criteria: Mapping[str, Mapping[str, object]] | None = None,
    clock: Callable[[], float] = time.time,
) -> dict:
    """Verify a Telos measurement-layer packet without requiring raw assets."""
    criteria = criteria or {}
    if not isinstance(packet, Mapping):
        return _result([], ["measurement_source_missing"], clock)
    if _has_raw_payload(packet):
        rows = [_row(_layer_id(row), UNVERIFIABLE, "raw_payload_leak", "privacy boundary rejected raw payload")
                for row in _measurement_rows(packet)]
        rows = rows or [_row("packet", UNVERIFIABLE, "raw_payload_leak", "privacy boundary rejected raw payload")]
        return _result(rows, ["raw_payload_leak"], clock)
    if packet.get("schema") != TELOS_MEASUREMENT_SCHEMA:
        row = _row("packet", UNVERIFIABLE, "measurement_source_missing", "unsupported or missing packet schema")
        return _result([row], ["measurement_source_missing"], clock)

    measurements = _measurement_rows(packet)
    if not measurements:
        row = _row("packet", UNVERIFIABLE, "measurement_source_missing", "no measurement rows")
        return _result([row], ["measurement_source_missing"], clock)

    receipts_ok = _source_receipts_ok(packet.get("source_receipts"))
    rows = [_verify_row(row, criteria.get(_layer_id(row), {}), receipts_ok) for row in measurements]
    failures = sorted({row["failure_code"] for row in rows if row["failure_code"]})
    return _result(rows, failures, clock)


def _verify_row(row: Mapping[str, object], criteria: Mapping[str, object], receipts_ok: bool) -> dict:
    layer_id = _layer_id(row)
    if layer_id == "visual.histogram-field":
        return _verify_histogram(row, criteria)
    if layer_id == "visual.dither-spectrum-meter":
        return _verify_dither(row, criteria)
    if layer_id == "spatial.splat-probe":
        return _verify_splat(row, criteria, receipts_ok)
    if layer_id == "lighting.cluster-meter":
        return _verify_cluster(row, criteria)
    if layer_id == "audio.spectral-meter":
        return _verify_audio(row, criteria)
    return _row(layer_id, UNVERIFIABLE, "measurement_source_missing", "unknown measurement layer")


def _verify_histogram(row: Mapping[str, object], criteria: Mapping[str, object]) -> dict:
    bins = row.get("bins")
    total = _finite_number(row.get("total_pixels"))
    bin_count = _finite_number(row.get("bin_count"))
    mean = _finite_number(row.get("mean_luminance"))
    contrast = _finite_number(row.get("contrast_ratio"))
    expected = _finite_number(criteria.get("expected_total_pixels"))
    bin_values = list(bins) if isinstance(bins, Sequence) and not isinstance(bins, str) else []
    summed = sum(_finite_number(value) or 0.0 for value in bin_values)
    ok = (
        total is not None and total > 0
        and bin_count is not None and bin_values and len(bin_values) == int(bin_count)
        and summed == total
        and mean is not None and 0 <= mean <= 255
        and contrast is not None and contrast >= 1
        and _has_hash(row)
        and (expected is None or total == expected)
    )
    if ok:
        return _row("visual.histogram-field", MATCH, None, "histogram bins, totals, and bounds verified")
    return _row("visual.histogram-field", UNVERIFIABLE, "pixel_dimensions_mismatch",
                "histogram dimensions or criteria did not verify", criteria)


def _verify_dither(row: Mapping[str, object], criteria: Mapping[str, object]) -> dict:
    min_levels = int(_finite_number(criteria.get("min_unique_levels")) or 2)
    unique = _finite_number(row.get("unique_levels"))
    candidates = row.get("algorithm_candidates")
    pattern = row.get("pattern")
    ok = (
        unique is not None and unique >= min_levels
        and isinstance(pattern, str) and bool(pattern)
        and isinstance(candidates, Sequence) and not isinstance(candidates, str) and len(candidates) > 0
        and _has_hash(row)
    )
    if ok:
        return _row("visual.dither-spectrum-meter", MATCH, None, "dither pattern has checkable structure")
    return _row("visual.dither-spectrum-meter", UNVERIFIABLE, "dither_pattern_unverifiable",
                "dither pattern did not meet explicit criteria", criteria)


def _verify_splat(
    row: Mapping[str, object],
    criteria: Mapping[str, object],
    receipts_ok: bool,
) -> dict:
    count = _finite_number(row.get("splat_count"))
    opacity = _finite_number(row.get("opacity_mean"))
    coverage = _finite_number(row.get("coverage_estimate"))
    require_receipts = criteria.get("require_source_receipts", True) is not False
    ok = (
        count is not None and count > 0
        and _bounds_ok(row.get("bounds"))
        and opacity is not None and 0 <= opacity <= 1
        and coverage is not None and coverage >= 0
        and _has_hash(row)
        and (receipts_ok or not require_receipts)
    )
    if ok:
        return _row("spatial.splat-probe", MATCH, None, "splat bounds and provenance verified")
    return _row("spatial.splat-probe", UNVERIFIABLE, "asset_provenance_missing",
                "splat layer needs redacted lawful source receipts and bounded geometry", criteria)


def _verify_cluster(row: Mapping[str, object], criteria: Mapping[str, object]) -> dict:
    clusters = _finite_number(row.get("cluster_count"))
    max_lights = _finite_number(row.get("max_lights_per_cluster"))
    over = _finite_number(row.get("over_budget_clusters"))
    max_over = _finite_number(criteria.get("max_over_budget_clusters"))
    max_over = 0 if max_over is None else max_over
    if clusters is None or clusters <= 0 or max_lights is None or over is None or not _has_hash(row):
        return _row("lighting.cluster-meter", UNVERIFIABLE, "measurement_source_missing",
                    "cluster layer is missing checkable counts", criteria)
    if over > max_over:
        return _row("lighting.cluster-meter", DRIFT, "cluster_budget_exceeded",
                    "cluster light budget exceeded explicit ceiling", criteria)
    return _row("lighting.cluster-meter", MATCH, None, "cluster light budget verified")


def _verify_audio(row: Mapping[str, object], criteria: Mapping[str, object]) -> dict:
    bins = _finite_number(row.get("bin_count"))
    centroid = _finite_number(row.get("spectral_centroid_bin"))
    dominant = row.get("dominant_bins")
    ok = (
        bins is not None and bins > 0
        and centroid is not None and 0 <= centroid < bins
        and isinstance(dominant, Sequence) and not isinstance(dominant, str) and len(dominant) > 0
        and _has_hash(row)
    )
    if ok:
        return _row("audio.spectral-meter", MATCH, None, "audio spectrum has checkable bins")
    return _row("audio.spectral-meter", UNVERIFIABLE, "audio_spectrum_unverifiable",
                "audio spectrum did not meet explicit criteria", criteria)


def _result(rows: list[dict], failure_codes: list[str], clock: Callable[[], float]) -> dict:
    summary = {
        MATCH: sum(1 for row in rows if row["verification_verdict"] == MATCH),
        DRIFT: sum(1 for row in rows if row["verification_verdict"] == DRIFT),
        UNVERIFIABLE: sum(1 for row in rows if row["verification_verdict"] == UNVERIFIABLE),
    }
    verdict = UNVERIFIABLE if summary[UNVERIFIABLE] else DRIFT if summary[DRIFT] else MATCH
    return {
        "schema": GATE_SCHEMA,
        "tool": "crucible.measurement_gate",
        "verification_verdict": verdict,
        "decision_outcome": _decision(verdict),
        "evaluated_at": datetime.fromtimestamp(float(clock()), UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": summary,
        "failure_codes": failure_codes,
        "rows": rows,
        "privacy": {
            "raw_payload_required": False,
            "raw_assets_required_for_interop": False,
            "exported_fields": [
                "layer_id",
                "measurement_hash",
                "failure_code",
                "verification_verdict",
                "decision_outcome",
            ],
        },
    }


def _row(
    layer_id: str,
    verdict: str,
    failure_code: str | None,
    evidence: str,
    criteria: Mapping[str, object] | None = None,
) -> dict:
    return {
        "layer_id": layer_id,
        "verification_verdict": verdict,
        "failure_code": failure_code,
        "criterion_source": "explicit criteria" if criteria else "telos.measurement.layers",
        "evidence_ref": evidence,
    }


def _decision(verdict: str) -> str:
    if verdict == MATCH:
        return ALLOW
    if verdict == DRIFT:
        return REQUIRE_REVIEW
    return BLOCK


def _measurement_rows(packet: Mapping[str, object]) -> list[Mapping[str, object]]:
    rows = packet.get("measurements")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def _layer_id(row: Mapping[str, object]) -> str:
    value = row.get("layer_id")
    return value if isinstance(value, str) and value else "unknown"


def _has_hash(row: Mapping[str, object]) -> bool:
    value = row.get("measurement_hash")
    return isinstance(value, str) and bool(value)


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number == number and number not in (float("inf"), float("-inf")) else None


def _bounds_ok(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    for axis in ("x", "y", "z"):
        points = value.get(axis)
        if not isinstance(points, Sequence) or isinstance(points, str) or len(points) != 2:
            return False
        if _finite_number(points[0]) is None or _finite_number(points[1]) is None:
            return False
    return True


def _source_receipts_ok(value: object) -> bool:
    if not isinstance(value, list) or not value:
        return False
    for row in value:
        if not isinstance(row, Mapping):
            return False
        if row.get("provenance_class") != "lawful_source":
            return False
        receipt = row.get("receipt_hash")
        if not isinstance(receipt, str) or not receipt.startswith("sha256:"):
            return False
    return True


def _has_raw_payload(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str) and key in RAW_PAYLOAD_KEYS:
                return True
            if _has_raw_payload(child):
                return True
    elif isinstance(value, list):
        return any(_has_raw_payload(child) for child in value)
    return False
