from __future__ import annotations

import json

from crucible.assess import assess
from crucible.claim import make_claim
from crucible.cli import main
from crucible.registry import Registry
from crucible.thesis import make_thesis
from crucible.verdict import Measurement

CLOCK = lambda: 1000.0  # noqa: E731


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _seed_registry(tmp_path):
    reg_dir = tmp_path / "reg"
    claim = make_claim("energy is conserved", "Telos verifier refutes conservation")
    legacy = make_claim("period stays stable", "period measurement drifts")
    thesis = make_thesis("Telos replay", [claim, legacy], clock=CLOCK)
    desc = {"oracle": "telos:conservation", "verifier": "conservation", "expr": "energy"}
    measured = Measurement(claim.id, claim.sha256, 0.0, 0.1, "telos:conservation", 42.0,
                           ("telos verified conservation",), recheck=desc)
    legacy_measured = Measurement(legacy.id, legacy.sha256, 0.0, 0.1, "manual", 43.0)
    assess(thesis, [measured, legacy_measured], clock=CLOCK, registry=Registry(str(reg_dir), fsync=False))
    return str(reg_dir), thesis, measured


def _replay_pack(path, measurement, *, deviation=0.0):
    return _write(path, {"replays": [{
        "recheck": measurement.recheck,
        "measurement": {
            "claim_id": measurement.claim_id,
            "claim_sha256": measurement.claim_sha256,
            "deviation": deviation,
            "tolerance": measurement.tolerance,
            "method": measurement.method,
            "measured_at": measurement.measured_at,
            "evidence": list(measurement.evidence),
        },
    }]})


def test_recheck_json_lists_oracle_replay_plan(tmp_path, capsys):
    reg, thesis, _measurement = _seed_registry(tmp_path)

    assert main(["recheck", reg, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["assessment"]["thesis_id"] == thesis.id
    assert payload["summary"] == {"descriptors": 1, "skipped": 1}
    assert payload["descriptors"][0]["claim_text"] == "energy is conserved"
    assert payload["descriptors"][0]["oracle"] == "telos:conservation"
    assert payload["descriptors"][0]["recheck"]["expr"] == "energy"


def test_recheck_template_writes_replay_pack_skeleton(tmp_path, capsys):
    reg, thesis, measurement = _seed_registry(tmp_path)
    template = tmp_path / "replay-template.json"

    assert main(["recheck", reg, "--template", str(template)]) == 0
    out = capsys.readouterr().out
    payload = json.loads(template.read_text(encoding="utf-8"))

    assert "wrote replay template" in out
    assert payload["assessment"]["thesis_id"] == thesis.id
    assert "Fill each measurement" in payload["instructions"]
    assert payload["replays"][0]["claim"]["text"] == "energy is conserved"
    assert payload["replays"][0]["recheck"] == measurement.recheck
    assert payload["replays"][0]["expected_measurement"]["deviation"] == 0.0
    assert payload["replays"][0]["expected_measurement"]["measured_at"] == 42.0
    assert payload["replays"][0]["measurement"]["claim_id"] == measurement.claim_id
    assert payload["replays"][0]["measurement"]["claim_sha256"] == measurement.claim_sha256
    assert payload["replays"][0]["measurement"]["deviation"] is None
    assert payload["replays"][0]["measurement"]["measured_at"] is None
    assert payload["replays"][0]["measurement"]["evidence"] == []


def test_recheck_pack_replays_descriptor_bearing_measurements(tmp_path, capsys):
    reg, _thesis, measurement = _seed_registry(tmp_path)
    pack = _replay_pack(tmp_path / "replay.json", measurement)

    assert main(["recheck", reg, "--pack", pack, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is True
    assert payload["checks"]["measurements_rerun"] is True
    assert payload["replay"] == {"ok": True, "checked": 1, "skipped": 1, "missing": 0,
                                 "mismatched": 0, "failed": 0}


def test_recheck_pack_reports_replayed_measurement_drift(tmp_path, capsys):
    reg, _thesis, measurement = _seed_registry(tmp_path)
    pack = _replay_pack(tmp_path / "drifted.json", measurement, deviation=2.0)

    assert main(["recheck", reg, "--pack", pack, "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is False
    assert payload["checks"]["measurements_rerun"] is False
    assert payload["replay"]["mismatched"] == 1


def test_recheck_rejects_template_and_pack_together(tmp_path, capsys):
    reg, _thesis, measurement = _seed_registry(tmp_path)
    pack = _replay_pack(tmp_path / "replay.json", measurement)

    assert main(["recheck", reg, "--pack", pack, "--template", str(tmp_path / "template.json")]) == 1

    assert "cannot be combined" in capsys.readouterr().err
