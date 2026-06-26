"""CLI coverage for table-backed measurement."""
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


def _substrate_file(tmp_path):
    return _write(tmp_path / "sub.json", {
        "specs": {
            "c-match": {"predicted": 10, "tolerance": 0.5, "observe": "v"},
            "c-drift": {"predicted": 2, "tolerance": 0.5, "observe": "v"},
        },
        "substrate": {"v": 10},
    })


def test_measure_against_substrate_decides_each_claim(tmp_path, capsys):
    code = main(["measure", _thesis_file(tmp_path), "--substrate", _substrate_file(tmp_path)])
    assert code == 0
    out = capsys.readouterr().out
    assert "measured thesis" in out
    assert "MATCH 1" in out and "DRIFT 1" in out and "UNVERIFIABLE 1" in out


def test_measure_json_and_recheck_from_registry(tmp_path, capsys):
    reg = str(tmp_path / "reg")
    code = main(["measure", _thesis_file(tmp_path), "--substrate", _substrate_file(tmp_path),
                 "--registry", reg, "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["assessment"]["match"] == 1 and payload["assessment"]["drift"] == 1
    assert main(["verdicts", reg, "--verify"]) == 0


def test_measure_spec_for_unknown_claim_is_an_error(tmp_path, capsys):
    sub = _write(tmp_path / "bad.json", {"specs": {"ghost": {"predicted": 1, "observe": "v"}},
                                         "substrate": {"v": 1}})
    assert main(["measure", _thesis_file(tmp_path), "--substrate", sub]) == 1
    assert "unknown claim" in capsys.readouterr().err


def test_measure_substrate_shapes_are_clean_errors(tmp_path, capsys):
    bad_specs = _write(tmp_path / "bad-specs.json", {"specs": [], "substrate": {"v": 1}})
    assert main(["measure", _thesis_file(tmp_path), "--substrate", bad_specs]) == 1
    assert "specs" in capsys.readouterr().err

    bad_substrate = _write(tmp_path / "bad-substrate.json", {"specs": {}, "substrate": []})
    assert main(["measure", _thesis_file(tmp_path), "--substrate", bad_substrate]) == 1
    assert "substrate" in capsys.readouterr().err


def test_measure_spec_with_ambiguous_claim_text_is_an_error(tmp_path, capsys):
    thesis = _write(tmp_path / "ambiguous.json", {
        "title": "Ambiguous",
        "claims": [
            {"id": "a", "text": "same text", "falsification": "first failure"},
            {"id": "b", "text": "same text", "falsification": "second failure"},
        ],
    })
    substrate = _write(tmp_path / "sub.json", {
        "specs": {"same text": {"predicted": 1, "tolerance": 0.1, "observe": "v"}},
        "substrate": {"v": 1},
    })

    assert main(["measure", thesis, "--substrate", substrate]) == 1
    assert "ambiguous claim" in capsys.readouterr().err


def test_measure_unknown_metric_is_a_clean_error(tmp_path, capsys):
    sub = _write(tmp_path / "bad.json", {
        "specs": {"c-match": {"predicted": 1, "tolerance": 0.1, "observe": "v", "metric": "relative"}},
        "substrate": {"v": 1}})
    assert main(["measure", _thesis_file(tmp_path), "--substrate", sub]) == 1
    assert "measure failed" in capsys.readouterr().err
