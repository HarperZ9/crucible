from __future__ import annotations

import json
from codecs import BOM_UTF8

from crucible.cli import main


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _packet():
    return {
        "schema": "project-telos.measurement-layers/v1",
        "tool": "telos.measurement.layers",
        "source_receipts": [
            {
                "title": "Project Telos measurement layers",
                "url": "demo/measurement-layers.mjs",
                "provenance_class": "lawful_source",
                "receipt_hash": "sha256:abc",
            }
        ],
        "privacy": {"raw_payload_required": False, "raw_assets_required_for_interop": False},
        "measurements": [
            {
                "layer_id": "visual.dither-spectrum-meter",
                "unique_levels": 2,
                "pattern": "ordered-bayer-candidate",
                "algorithm_candidates": ["ordered-bayer"],
                "measurement_hash": "fnv1a:ok",
            },
        ],
    }


def test_measurement_gate_cli_emits_json_verdict(tmp_path, capsys):
    packet = _write(tmp_path / "packet.json", _packet())

    assert main(["measurement-gate", packet, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["verification_verdict"] == "MATCH"
    assert payload["decision_outcome"] == "allow"
    assert payload["rows"][0]["layer_id"] == "visual.dither-spectrum-meter"


def test_measurement_gate_cli_accepts_criteria_file(tmp_path, capsys):
    packet = _write(tmp_path / "packet.json", _packet())
    criteria = _write(
        tmp_path / "criteria.json",
        {"visual.dither-spectrum-meter": {"min_unique_levels": 4}},
    )

    assert main(["measurement-gate", packet, "--criteria", criteria, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["verification_verdict"] == "UNVERIFIABLE"
    assert payload["rows"][0]["failure_code"] == "dither_pattern_unverifiable"


def test_measurement_gate_cli_accepts_utf8_bom_json(tmp_path, capsys):
    packet = tmp_path / "packet-bom.json"
    packet.write_bytes(BOM_UTF8 + json.dumps(_packet()).encode("utf-8"))

    assert main(["measurement-gate", str(packet), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["verification_verdict"] == "MATCH"
