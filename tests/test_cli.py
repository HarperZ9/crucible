"""The CLI surface: register, assess, registry list/verify, human and JSON, honest exit codes."""
from __future__ import annotations

import json

from crucible.cli import main


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _thesis_file(tmp_path):
    return _write(tmp_path / "thesis.json", {
        "title": "CLI thesis",
        "claims": [
            {"text": "c-match", "falsification": "f1"},
            {"text": "c-drift", "falsification": "f2"},
            {"text": "c-unver", "falsification": "f3"},
        ],
    })


def _measurements_file(tmp_path):
    return _write(tmp_path / "m.json", {"measurements": [
        {"claim": "c-match", "deviation": 0.0, "tolerance": 0.1, "method": "m"},
        {"claim": "c-drift", "deviation": 1.0, "tolerance": 0.1, "method": "m"},
    ]})


def test_register_into_registry(tmp_path, capsys):
    reg = str(tmp_path / "reg")
    code = main(["register", _thesis_file(tmp_path), "--registry", reg])
    assert code == 0
    out = capsys.readouterr().out
    assert "registered thesis" in out and "3 claim(s)" in out


def test_assess_from_file_reports_outcomes(tmp_path, capsys):
    code = main(["assess", _thesis_file(tmp_path), "--measurements", _measurements_file(tmp_path)])
    assert code == 0
    out = capsys.readouterr().out
    assert "MATCH 1" in out and "DRIFT 1" in out and "UNVERIFIABLE 1" in out
    assert "verified: True" in out


def test_assess_json_mode(tmp_path, capsys):
    code = main(["assess", _thesis_file(tmp_path), "--measurements", _measurements_file(tmp_path), "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["assessment"]["match"] == 1
    assert len(payload["verdicts"]) == 3


def test_assess_by_id_from_registry(tmp_path, capsys):
    reg = str(tmp_path / "reg")
    main(["register", _thesis_file(tmp_path), "--registry", reg])
    capsys.readouterr()  # clear the register output before reading the list output
    # recover the registered id from a list --json
    main(["registry", "list", reg, "--json"])
    rows = json.loads(capsys.readouterr().out)
    tid = rows[0]["id"]
    code = main(["assess", tid, "--registry", reg, "--measurements", _measurements_file(tmp_path)])
    assert code == 0
    assert "recorded to" in capsys.readouterr().out


def test_registry_verify_clean_then_corrupt(tmp_path, capsys):
    reg_dir = tmp_path / "reg"
    reg = str(reg_dir)
    main(["register", _thesis_file(tmp_path), "--registry", reg])
    capsys.readouterr()
    assert main(["registry", "verify", reg]) == 0
    # corrupt one stored body
    obj_root = reg_dir / "objects"
    shard = next(obj_root.iterdir())
    body = next(shard.iterdir())
    body.write_text("tampered", encoding="utf-8")
    assert main(["registry", "verify", reg]) == 1
    assert "CORRUPT" in capsys.readouterr().out


def test_no_command_prints_help_and_returns_one(capsys):
    assert main([]) == 1


def test_missing_thesis_file_returns_one(capsys):
    assert main(["assess", "does-not-exist.json"]) == 1
    assert "assess failed" in capsys.readouterr().err


def test_version(capsys):
    import pytest

    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert "crucible" in capsys.readouterr().out


def test_register_human_without_registry(tmp_path, capsys):
    code = main(["register", _thesis_file(tmp_path)])
    assert code == 0
    out = capsys.readouterr().out
    assert "registered thesis" in out and " to " not in out


def test_register_json_mode(tmp_path, capsys):
    code = main(["register", _thesis_file(tmp_path), "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["thesis"]["title"] == "CLI thesis"
    assert payload["stored"] is None


def test_registry_list_human(tmp_path, capsys):
    reg = str(tmp_path / "reg")
    main(["register", _thesis_file(tmp_path), "--registry", reg])
    capsys.readouterr()
    assert main(["registry", "list", reg]) == 0
    out = capsys.readouterr().out
    assert "thesis(es)" in out and "CLI thesis" in out


def test_register_empty_claims_is_an_error(tmp_path, capsys):
    bad = _write(tmp_path / "bad.json", {"title": "t", "claims": []})
    assert main(["register", bad]) == 1
    assert "register failed" in capsys.readouterr().err


def test_assess_measurement_with_unknown_claim_is_an_error(tmp_path, capsys):
    m = _write(tmp_path / "m.json", {"measurements": [{"claim": "nope", "deviation": 0.0, "tolerance": 0.1}]})
    code = main(["assess", _thesis_file(tmp_path), "--measurements", m])
    assert code == 1
    assert "unknown claim" in capsys.readouterr().err
