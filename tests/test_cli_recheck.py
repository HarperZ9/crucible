from __future__ import annotations

import hashlib
import json

import pytest

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
    legacy_measured = Measurement(
        legacy.id,
        legacy.sha256,
        0.0,
        0.1,
        "manual",
        43.0,
        ("descriptorless private evidence",),
    )
    assess(thesis, [measured, legacy_measured], clock=CLOCK, registry=Registry(str(reg_dir), fsync=False))
    return str(reg_dir), thesis, measured


def _replay_pack(path, measurement, *, deviation=0.0, assessment=None):
    payload = {"replays": [{
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
    }]}
    if assessment is not None:
        payload["assessment"] = assessment
    return _write(path, payload)


def _template_as_pack(template, pack):
    payload = json.loads(template.read_text(encoding="utf-8"))
    payload["schema"] = "crucible.replay-pack/1"
    payload.pop("instructions", None)
    for row in payload["replays"]:
        row["measurement"] = row["expected_measurement"]
    _write(pack, payload)
    return payload


def _canonical_sha256(value):
    def canonical(row):
        return json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    rows = sorted(value, key=canonical)
    body = canonical(rows)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def test_recheck_json_lists_oracle_replay_plan(tmp_path, capsys):
    reg, thesis, _measurement = _seed_registry(tmp_path)

    assert main(["recheck", reg, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["assessment"]["thesis_id"] == thesis.id
    assert payload["summary"] == {"descriptors": 1, "skipped": 1}
    assert payload["replay_binding"]["schema"] == "crucible.replay-set/1"
    assert payload["replay_binding"]["descriptor_count"] == 1
    assert payload["replay_binding"]["skipped_count"] == 1
    assert "measurement_seal_rows" not in payload
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
    assert payload["schema"] == "crucible.replay-template/1"
    assert payload["assessment"]["thesis_id"] == thesis.id
    assert payload["replay_binding"]["schema"] == "crucible.replay-set/1"
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


def test_recheck_template_carries_privacy_bounded_replay_binding(tmp_path, capsys):
    reg, thesis, measurement = _seed_registry(tmp_path)
    template = tmp_path / "mixed-template.json"
    pack = tmp_path / "mixed-pack.json"

    assert main(["recheck", reg, "--template", str(template)]) == 0
    capsys.readouterr()
    raw_template = template.read_text(encoding="utf-8")
    payload = _template_as_pack(template, pack)
    legacy_claim = next(claim for claim in thesis.claims if claim.id != measurement.claim_id)
    contract_rows = [
        {
            "recheck": row["recheck"],
            "expected_measurement": row["expected_measurement"],
        }
        for row in payload["replays"]
    ]

    assert payload["replay_binding"] == {
        "schema": "crucible.replay-set/1",
        "descriptor_count": 1,
        "skipped_count": 1,
        "sha256": _canonical_sha256(contract_rows),
    }
    assert "measurement_seal_rows" not in payload
    assert legacy_claim.id not in raw_template
    assert "descriptorless private evidence" not in raw_template
    assert main(["recheck", reg, "--pack", str(pack), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["replay"]["checked"] == 1
    assert result["replay"]["skipped"] == 1


def test_recheck_pack_rejects_tampered_replay_binding(tmp_path, capsys):
    reg, _thesis, _measurement = _seed_registry(tmp_path)
    template = tmp_path / "mixed-template.json"
    pack = tmp_path / "tampered-pack.json"

    assert main(["recheck", reg, "--template", str(template)]) == 0
    capsys.readouterr()
    payload = _template_as_pack(template, pack)
    payload["replay_binding"]["sha256"] = "0" * 64
    _write(pack, payload)

    assert main(["recheck", reg, "--pack", str(pack)]) == 1
    assert "replay binding mismatch" in capsys.readouterr().err


def test_recheck_pack_accepts_legacy_schema_less_bound_pack(tmp_path, capsys):
    reg, _thesis, measurement = _seed_registry(tmp_path)
    assert main(["recheck", reg, "--json"]) == 0
    assessment = json.loads(capsys.readouterr().out)["assessment"]
    pack = _replay_pack(tmp_path / "replay.json", measurement, assessment=assessment)
    assert "schema" not in json.loads((tmp_path / "replay.json").read_text(encoding="utf-8"))

    assert main(["recheck", reg, "--pack", pack, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is True
    assert payload["checks"]["measurements_rerun"] is True
    assert payload["replay"] == {"ok": True, "checked": 1, "skipped": 1, "missing": 0,
                                 "mismatched": 0, "failed": 0}


@pytest.mark.parametrize("schema", ["crucible.replay-template/1", "unknown.replay-pack/1"])
def test_recheck_pack_rejects_non_pack_schema(tmp_path, capsys, schema):
    reg, _thesis, measurement = _seed_registry(tmp_path)
    assert main(["recheck", reg, "--json"]) == 0
    assessment = json.loads(capsys.readouterr().out)["assessment"]
    pack_path = tmp_path / "wrong-schema.json"
    _replay_pack(pack_path, measurement, assessment=assessment)
    payload = json.loads(pack_path.read_text(encoding="utf-8"))
    payload["schema"] = schema
    _write(pack_path, payload)

    assert main(["recheck", reg, "--pack", str(pack_path)]) == 1
    assert "replay pack schema" in capsys.readouterr().err


def test_recheck_pack_accepts_matching_assessment_binding(tmp_path, capsys):
    reg, thesis, measurement = _seed_registry(tmp_path)
    assert main(["recheck", reg, "--json"]) == 0
    assessment = json.loads(capsys.readouterr().out)["assessment"]
    pack = _replay_pack(tmp_path / "bound-replay.json", measurement, assessment=assessment)

    assert main(["recheck", reg, "--pack", pack, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert assessment["thesis_id"] == thesis.id
    assert payload["ok"] is True
    assert payload["replay"]["checked"] == 1


def test_recheck_pack_rejects_missing_assessment_binding(tmp_path, capsys):
    reg, _thesis, measurement = _seed_registry(tmp_path)
    pack = _replay_pack(tmp_path / "unbound-replay.json", measurement)

    assert main(["recheck", reg, "--pack", pack]) == 1

    assert "assessment binding" in capsys.readouterr().err


def test_recheck_pack_reports_replayed_measurement_drift(tmp_path, capsys):
    reg, _thesis, measurement = _seed_registry(tmp_path)
    assert main(["recheck", reg, "--json"]) == 0
    assessment = json.loads(capsys.readouterr().out)["assessment"]
    pack = _replay_pack(
        tmp_path / "drifted.json", measurement, deviation=2.0, assessment=assessment
    )

    assert main(["recheck", reg, "--pack", pack, "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is False
    assert payload["checks"]["measurements_rerun"] is False
    assert payload["replay"]["mismatched"] == 1


def test_recheck_pack_rejects_wrong_assessment_binding(tmp_path, capsys):
    reg, _thesis, measurement = _seed_registry(tmp_path)
    wrong = {
        "thesis_id": "other",
        "assessment_seal": "not-this-assessment",
        "measurement_seal": "not-this-measurement-seal",
    }
    pack = _replay_pack(tmp_path / "wrong-assessment.json", measurement, assessment=wrong)

    assert main(["recheck", reg, "--pack", pack]) == 1

    assert "assessment binding mismatch" in capsys.readouterr().err


def test_recheck_pack_rejects_null_assessment_binding(tmp_path, capsys):
    reg, _thesis, measurement = _seed_registry(tmp_path)
    pack = _write(tmp_path / "null-assessment.json", {
        "assessment": None,
        "replays": [{
            "recheck": measurement.recheck,
            "measurement": {
                "claim_id": measurement.claim_id,
                "claim_sha256": measurement.claim_sha256,
                "deviation": measurement.deviation,
                "tolerance": measurement.tolerance,
                "method": measurement.method,
                "measured_at": measurement.measured_at,
                "evidence": list(measurement.evidence),
            },
        }],
    })

    assert main(["recheck", reg, "--pack", pack]) == 1

    assert "replay pack assessment must be an object" in capsys.readouterr().err


def test_recheck_rejects_template_and_pack_together(tmp_path, capsys):
    reg, _thesis, measurement = _seed_registry(tmp_path)
    pack = _replay_pack(tmp_path / "replay.json", measurement)

    assert main(["recheck", reg, "--pack", pack, "--template", str(tmp_path / "template.json")]) == 1

    assert "cannot be combined" in capsys.readouterr().err
