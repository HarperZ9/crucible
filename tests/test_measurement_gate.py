from __future__ import annotations

from crucible.measurement_gate import verify_measurement_packet

CLOCK = lambda: 1000.0  # noqa: E731


def _packet(*, cluster_over_budget=0, raw_payload=False, source_receipts=True):
    packet = {
        "schema": "project-telos.measurement-layers/v1",
        "tool": "telos.measurement.layers",
        "source_receipts": [
            {
                "title": "Project Telos measurement layers",
                "url": "demo/measurement-layers.mjs",
                "provenance_class": "lawful_source",
                "receipt_hash": "sha256:abc",
            }
        ] if source_receipts else [],
        "privacy": {
            "raw_payload_required": False,
            "raw_assets_required_for_interop": False,
        },
        "measurements": [
            {
                "layer_id": "visual.histogram-field",
                "total_pixels": 16,
                "bin_count": 4,
                "bins": [4, 4, 4, 4],
                "min_luminance": 0,
                "max_luminance": 240,
                "mean_luminance": 120.0,
                "contrast_ratio": 241.0,
                "measurement_hash": "fnv1a:hist",
            },
            {
                "layer_id": "visual.dither-spectrum-meter",
                "unique_levels": 8,
                "pattern": "ordered-bayer-candidate",
                "matrix_size": 4,
                "horizontal_transition_count": 11,
                "algorithm_candidates": ["ordered-bayer", "blue-noise"],
                "measurement_hash": "fnv1a:dither",
            },
            {
                "layer_id": "spatial.splat-probe",
                "splat_count": 3,
                "bounds": {"x": [-1, 1], "y": [-1, 1], "z": [-0.2, 0.2]},
                "radius_mean": 0.4,
                "opacity_mean": 0.75,
                "coverage_estimate": 0.2,
                "measurement_hash": "fnv1a:splat",
            },
            {
                "layer_id": "lighting.cluster-meter",
                "grid": {"columns": 4, "rows": 3},
                "cluster_count": 12,
                "max_lights_per_cluster": 3,
                "mean_lights_per_cluster": 1.25,
                "over_budget_clusters": cluster_over_budget,
                "histogram": {"0": 2, "1": 8, "2": 2},
                "measurement_hash": "fnv1a:cluster",
            },
            {
                "layer_id": "audio.spectral-meter",
                "bin_count": 16,
                "dominant_bins": [{"bin": 3, "magnitude": 12.0}],
                "spectral_centroid_bin": 3.25,
                "measurement_hash": "fnv1a:audio",
            },
        ],
    }
    if raw_payload:
        packet["raw_pixels"] = [0, 255, 0, 255]
    return packet


def test_measurement_gate_matches_complete_telos_packet():
    result = verify_measurement_packet(_packet(), clock=CLOCK)

    assert result["schema"] == "project-telos.crucible.measurement-gate/v1"
    assert result["verification_verdict"] == "MATCH"
    assert result["decision_outcome"] == "allow"
    assert result["summary"] == {"MATCH": 5, "DRIFT": 0, "UNVERIFIABLE": 0}
    assert result["evaluated_at"] == "1970-01-01T00:16:40Z"
    assert {row["layer_id"] for row in result["rows"]} == {
        "visual.histogram-field",
        "visual.dither-spectrum-meter",
        "spatial.splat-probe",
        "lighting.cluster-meter",
        "audio.spectral-meter",
    }
    assert all(row["failure_code"] is None for row in result["rows"])


def test_measurement_gate_separates_drift_from_unverifiable():
    result = verify_measurement_packet(_packet(cluster_over_budget=2), clock=CLOCK)

    assert result["verification_verdict"] == "DRIFT"
    assert result["decision_outcome"] == "require_review"
    row = next(row for row in result["rows"] if row["layer_id"] == "lighting.cluster-meter")
    assert row["failure_code"] == "cluster_budget_exceeded"
    assert row["verification_verdict"] == "DRIFT"


def test_measurement_gate_fails_closed_on_raw_payload_leak():
    result = verify_measurement_packet(_packet(raw_payload=True), clock=CLOCK)

    assert result["verification_verdict"] == "UNVERIFIABLE"
    assert result["decision_outcome"] == "block"
    assert result["failure_codes"] == ["raw_payload_leak"]
    assert result["rows"][0]["failure_code"] == "raw_payload_leak"


def test_measurement_gate_requires_lawful_source_receipts_for_asset_layers():
    result = verify_measurement_packet(_packet(source_receipts=False), clock=CLOCK)

    assert result["verification_verdict"] == "UNVERIFIABLE"
    assert result["decision_outcome"] == "block"
    row = next(row for row in result["rows"] if row["layer_id"] == "spatial.splat-probe")
    assert row["failure_code"] == "asset_provenance_missing"


def test_measurement_gate_uses_explicit_criteria_not_magic_fields():
    packet = _packet()
    criteria = {"visual.histogram-field": {"expected_total_pixels": 32}}

    result = verify_measurement_packet(packet, criteria=criteria, clock=CLOCK)

    assert result["verification_verdict"] == "UNVERIFIABLE"
    row = next(row for row in result["rows"] if row["layer_id"] == "visual.histogram-field")
    assert row["failure_code"] == "pixel_dimensions_mismatch"
    assert row["criterion_source"] == "explicit criteria"
