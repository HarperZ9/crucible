from __future__ import annotations

import json

from crucible.cli import main


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _thesis_file(tmp_path):
    return _write(tmp_path / "thesis.json", {
        "title": "CLI drift thesis",
        "claims": [
            {"text": "c-stable", "falsification": "f1"},
            {"text": "c-improves", "falsification": "f2"},
            {"text": "c-regresses", "falsification": "f3"},
        ],
    })


def _measurements_file(tmp_path, name, stable, improves, regresses):
    return _write(tmp_path / name, {"measurements": [
        {"claim": "c-stable", "deviation": stable, "tolerance": 1.0, "method": "m"},
        {"claim": "c-improves", "deviation": improves, "tolerance": 1.0, "method": "m"},
        {"claim": "c-regresses", "deviation": regresses, "tolerance": 1.0, "method": "m"},
    ]})


def test_drift_command_compares_latest_two_assessments(tmp_path, capsys):
    reg = str(tmp_path / "reg")
    thesis = _thesis_file(tmp_path)
    first = _measurements_file(tmp_path, "m1.json", 0.25, 0.90, 0.10)
    second = _measurements_file(tmp_path, "m2.json", 0.25, 0.10, 1.50)
    assert main(["assess", thesis, "--measurements", first, "--registry", reg]) == 0
    capsys.readouterr()
    assert main(["assess", thesis, "--measurements", second, "--registry", reg]) == 0
    capsys.readouterr()

    assert main(["drift", reg, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["summary"] == {"held": 1, "moved": 0, "improved": 1, "regressed": 1}
    statuses = {row["current_status"]: row["status"] for row in payload["rows"]}
    assert statuses["MATCH"] in {"held", "improved"}
    assert any(row["status"] == "regressed" and row["current_status"] == "DRIFT"
               for row in payload["rows"])


def test_drift_command_needs_two_assessments(tmp_path, capsys):
    reg = str(tmp_path / "reg")
    thesis = _thesis_file(tmp_path)
    first = _measurements_file(tmp_path, "m1.json", 0.25, 0.90, 0.10)
    assert main(["assess", thesis, "--measurements", first, "--registry", reg]) == 0
    capsys.readouterr()

    assert main(["drift", reg]) == 1
    assert "needs at least two verified assessments" in capsys.readouterr().err


def test_drift_command_rejects_different_latest_theses_cleanly(tmp_path, capsys):
    reg = str(tmp_path / "reg")
    first = _thesis_file(tmp_path)
    second = _write(tmp_path / "other.json", {
        "title": "Other",
        "claims": [{"text": "other", "falsification": "other counterexample"}],
    })
    assert main(["assess", first, "--registry", reg]) == 0
    capsys.readouterr()
    assert main(["assess", second, "--registry", reg]) == 0
    capsys.readouterr()

    assert main(["drift", reg]) == 1
    assert "same thesis" in capsys.readouterr().err


def test_drift_command_fails_when_tampering_leaves_fewer_than_two_verified_rounds(tmp_path, capsys):
    reg_dir = tmp_path / "reg"
    thesis = _thesis_file(tmp_path)
    first = _measurements_file(tmp_path, "m1.json", 0.25, 0.90, 0.10)
    second = _measurements_file(tmp_path, "m2.json", 0.25, 0.10, 1.50)
    assert main(["assess", thesis, "--measurements", first, "--registry", str(reg_dir)]) == 0
    capsys.readouterr()
    assert main(["assess", thesis, "--measurements", second, "--registry", str(reg_dir)]) == 0
    capsys.readouterr()
    lines = (reg_dir / "assessments.jsonl").read_text(encoding="utf-8").splitlines()
    latest = json.loads(lines[-1])
    latest["verdicts"][0]["margin"] = -999.0
    lines[-1] = json.dumps(latest)
    (reg_dir / "assessments.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert main(["drift", str(reg_dir)]) == 1
    assert "two verified assessments" in capsys.readouterr().err


def test_drift_command_falls_back_to_latest_two_verified_rounds(tmp_path, capsys):
    reg_dir = tmp_path / "reg"
    thesis = _thesis_file(tmp_path)
    first = _measurements_file(tmp_path, "m1.json", 0.25, 0.90, 0.10)
    second = _measurements_file(tmp_path, "m2.json", 0.25, 0.10, 1.50)
    third = _measurements_file(tmp_path, "m3.json", 0.25, 0.05, 2.00)
    assert main(["assess", thesis, "--measurements", first, "--registry", str(reg_dir)]) == 0
    capsys.readouterr()
    assert main(["assess", thesis, "--measurements", second, "--registry", str(reg_dir)]) == 0
    capsys.readouterr()
    assert main(["assess", thesis, "--measurements", third, "--registry", str(reg_dir)]) == 0
    capsys.readouterr()
    lines = (reg_dir / "assessments.jsonl").read_text(encoding="utf-8").splitlines()
    latest = json.loads(lines[-1])
    latest["verdicts"][0]["margin"] = -999.0
    lines[-1] = json.dumps(latest)
    (reg_dir / "assessments.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert main(["drift", str(reg_dir), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["summary"] == {"held": 1, "moved": 0, "improved": 1, "regressed": 1}
