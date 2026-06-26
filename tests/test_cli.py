"""The CLI surface: register, assess, steelman, registry list/verify, verdicts [--verify].

Human and JSON output, honest exit codes."""
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
    assert "self-consistent: True" in out


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


def test_register_top_level_json_array_is_a_clean_error(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("[]", encoding="utf-8")

    assert main(["register", str(bad)]) == 1
    assert "register failed" in capsys.readouterr().err


def test_assess_measurement_with_unknown_claim_is_an_error(tmp_path, capsys):
    m = _write(tmp_path / "m.json", {"measurements": [{"claim": "nope", "deviation": 0.0, "tolerance": 0.1}]})
    code = main(["assess", _thesis_file(tmp_path), "--measurements", m])
    assert code == 1
    assert "unknown claim" in capsys.readouterr().err


def test_assess_measurements_must_be_a_list_of_objects(tmp_path, capsys):
    bad = _write(tmp_path / "bad-m.json", {"measurements": "not-a-list"})

    assert main(["assess", _thesis_file(tmp_path), "--measurements", bad]) == 1
    assert "measurements" in capsys.readouterr().err


def test_assess_measurement_with_ambiguous_claim_text_is_an_error(tmp_path, capsys):
    thesis = _write(tmp_path / "ambiguous.json", {
        "title": "Ambiguous",
        "claims": [
            {"id": "a", "text": "same text", "falsification": "first failure"},
            {"id": "b", "text": "same text", "falsification": "second failure"},
        ],
    })
    measurements = _write(tmp_path / "m.json", {
        "measurements": [{"claim": "same text", "deviation": 0.0, "tolerance": 0.1}],
    })

    assert main(["assess", thesis, "--measurements", measurements]) == 1
    assert "ambiguous claim" in capsys.readouterr().err


def test_verdicts_verify_roundtrip_from_disk(tmp_path, capsys):
    reg = str(tmp_path / "reg")
    main(["assess", _thesis_file(tmp_path), "--measurements", _measurements_file(tmp_path), "--registry", reg])
    capsys.readouterr()
    code = main(["verdicts", reg, "--verify"])
    assert code == 0
    out = capsys.readouterr().out
    assert "ok=True" in out and "rederive=True" in out


def test_verdicts_verify_detects_a_tampered_assessment(tmp_path, capsys):
    import json as _json

    reg_dir = tmp_path / "reg"
    reg = str(reg_dir)
    main(["assess", _thesis_file(tmp_path), "--measurements", _measurements_file(tmp_path), "--registry", reg])
    capsys.readouterr()
    # Edit a stored assessment's measurement deviation without re-sealing.
    apath = reg_dir / "assessments.jsonl"
    rec = _json.loads(apath.read_text(encoding="utf-8").strip())
    rec["measurements"][0]["deviation"] = 12345.0
    apath.write_text(_json.dumps(rec) + "\n", encoding="utf-8")
    assert main(["verdicts", reg, "--verify"]) == 1


def test_registry_verify_on_malformed_catalog_is_a_clean_error(tmp_path, capsys):
    reg_dir = tmp_path / "reg"
    main(["register", _thesis_file(tmp_path), "--registry", str(reg_dir)])
    capsys.readouterr()
    (reg_dir / "theses.jsonl").write_text("{ not json\n", encoding="utf-8")
    assert main(["registry", "verify", str(reg_dir)]) == 1
    assert "registry verify failed" in capsys.readouterr().err


def test_verdicts_on_malformed_history_is_a_clean_error(tmp_path, capsys):
    reg_dir = tmp_path / "reg"
    main(["assess", _thesis_file(tmp_path), "--measurements", _measurements_file(tmp_path),
          "--registry", str(reg_dir)])
    capsys.readouterr()
    (reg_dir / "assessments.jsonl").write_text("{ not json\n", encoding="utf-8")
    assert main(["verdicts", str(reg_dir)]) == 1
    assert "verdicts failed" in capsys.readouterr().err


def test_verdicts_list_human(tmp_path, capsys):
    reg = str(tmp_path / "reg")
    main(["assess", _thesis_file(tmp_path), "--measurements", _measurements_file(tmp_path), "--registry", reg])
    capsys.readouterr()
    assert main(["verdicts", reg]) == 0
    out = capsys.readouterr().out
    assert "assessment(s)" in out and "MATCH 1" in out


def test_registry_verify_json(tmp_path, capsys):
    reg = str(tmp_path / "reg")
    main(["register", _thesis_file(tmp_path), "--registry", reg])
    capsys.readouterr()
    assert main(["registry", "verify", reg, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True and "bodies" in payload and "seals" in payload


def test_register_json_with_registry_reports_stored(tmp_path, capsys):
    reg = str(tmp_path / "reg")
    code = main(["register", _thesis_file(tmp_path), "--registry", reg, "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stored"]["registered"] is True and payload["stored"]["added"] == 3


def test_steelman_human(tmp_path, capsys):
    code = main(["steelman", _thesis_file(tmp_path)])
    assert code == 0
    out = capsys.readouterr().out
    assert "steelmanned thesis" in out and "-> measure:" in out


def test_steelman_json(tmp_path, capsys):
    code = main(["steelman", _thesis_file(tmp_path), "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["refutations"]) == 3
    assert all(r["source"] == "null" for r in payload["refutations"])


def test_steelman_by_id_from_registry(tmp_path, capsys):
    reg = str(tmp_path / "reg")
    main(["register", _thesis_file(tmp_path), "--registry", reg])
    capsys.readouterr()
    main(["registry", "list", reg, "--json"])
    tid = json.loads(capsys.readouterr().out)[0]["id"]
    assert main(["steelman", tid, "--registry", reg]) == 0


def test_steelman_missing_file_is_an_error(capsys):
    assert main(["steelman", "nope.json"]) == 1
    assert "steelman failed" in capsys.readouterr().err


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
    # the oracle-produced measurements re-derive from disk
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


def test_steelman_flags_an_unfalsifiable_claim(tmp_path, capsys):
    thesis = _write(tmp_path / "t.json", {"title": "T", "claims": [
        {"text": "a testable claim", "falsification": "a counterexample"},
        {"text": "an untestable claim", "falsification": ""},
    ]})
    assert main(["steelman", thesis]) == 0
    assert "(no test: the claim is unfalsifiable)" in capsys.readouterr().out
    # and the JSON binds the unfalsifiable claim with an empty measurable
    assert main(["steelman", thesis, "--json"]) == 0
    refutations = json.loads(capsys.readouterr().out)["refutations"]
    empty = [r for r in refutations if r["measurable"] == ""]
    assert len(empty) == 1 and empty[0]["claim_sha256"]
