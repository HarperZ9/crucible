"""CLI coverage for the deterministic refine loop."""
from __future__ import annotations

import json

from crucible.cli import main


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _refine_config(tmp_path, **overrides):
    data = {
        "title": "CLI refine",
        "claims": [
            {"text": "c-match", "falsification": "f1"},
            {"text": "c-drift", "falsification": "f2"},
        ],
        "specs": {
            "c-match": {"predicted": 10, "tolerance": 0.5, "observe": "a"},
            "c-drift": {"predicted": 2, "tolerance": 0.5, "observe": "b"},
        },
        "rounds": [{"a": 10, "b": 10}, {"a": 10, "b": 2}],
        "target_margin": 0.25,
        "cohesion_bar": 0.5,
    }
    data.update(overrides)
    return _write(tmp_path / "refine.json", data)


def test_refine_json_reports_correct_round(tmp_path, capsys):
    code = main(["refine", _refine_config(tmp_path), "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "correct"
    assert payload["iterations"] == 2
    assert [v["status"] for v in payload["verdicts"]] == ["MATCH", "MATCH"]


def test_refine_invalid_target_is_a_clean_error(tmp_path, capsys):
    cfg = _refine_config(tmp_path, target_margin="not-a-number")
    assert main(["refine", cfg]) == 1
    assert "refine failed" in capsys.readouterr().err


def test_refine_negative_target_is_a_clean_error(tmp_path, capsys):
    cfg = _refine_config(tmp_path, target_margin=-1.0)
    assert main(["refine", cfg]) == 1
    assert "refine failed" in capsys.readouterr().err
