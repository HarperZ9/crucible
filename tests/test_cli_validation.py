from __future__ import annotations

import json

from crucible.cli import main


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _thesis_file(tmp_path):
    return _write(tmp_path / "thesis.json", {
        "title": "Validation thesis",
        "claims": [{"text": "c", "falsification": "f"}],
    })


def _refine_config(tmp_path, **overrides):
    data = {
        "title": "Validation refine",
        "claims": [{"text": "c", "falsification": "f"}],
        "specs": {"c": {"predicted": 1, "tolerance": 0.1, "observe": "v"}},
        "rounds": [{"v": 1}],
    }
    data.update(overrides)
    return _write(tmp_path / "refine.json", data)


def test_register_rejects_non_string_claim_fields_cleanly(tmp_path, capsys):
    cases = [
        {"text": ["not", "string"], "falsification": "f"},
        {"text": "c", "falsification": ["not", "string"]},
        {"id": ["bad"], "text": "c", "falsification": "f"},
    ]
    for i, claim in enumerate(cases):
        thesis = _write(tmp_path / f"bad-{i}.json", {"title": "Bad", "claims": [claim]})
        assert main(["register", thesis]) == 1
        assert "claim" in capsys.readouterr().err


def test_refine_rounds_must_be_objects(tmp_path, capsys):
    cfg = _refine_config(tmp_path, rounds=["not-object"])

    assert main(["refine", cfg]) == 1
    assert "round" in capsys.readouterr().err


def test_verdicts_verify_rejects_malformed_nested_assessment_rows(tmp_path, capsys):
    reg_dir = tmp_path / "reg"
    assert main(["assess", _thesis_file(tmp_path), "--registry", str(reg_dir)]) == 0
    capsys.readouterr()
    path = reg_dir / "assessments.jsonl"
    row = json.loads(path.read_text(encoding="utf-8").strip())
    row["verdicts"] = {"not": "a-list"}
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    assert main(["verdicts", str(reg_dir), "--verify"]) == 1
    assert "verdicts failed" in capsys.readouterr().err
