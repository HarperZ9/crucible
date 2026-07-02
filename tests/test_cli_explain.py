"""CLI and MCP wiring for the honesty surfaces: an UNVERIFIABLE verdict arrives with a concrete
evidence request, an ill-posed measurements file warns (typed) before assessment, and --strict
turns those warnings into a nonzero exit."""
from __future__ import annotations

import json

from crucible.cli import main
from crucible.mcp import handle_request


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _thesis_file(tmp_path):
    return _write(tmp_path / "thesis.json", {
        "title": "Explain thesis",
        "claims": [
            {"text": "c-match", "falsification": "f1"},
            {"text": "c-unver", "falsification": "f2"},
        ],
    })


def _measurements_file(tmp_path):
    return _write(tmp_path / "m.json", {"measurements": [
        {"claim": "c-match", "deviation": 0.0, "tolerance": 0.1, "method": "m"},
    ]})


def _full_measurements_file(tmp_path):
    return _write(tmp_path / "m-full.json", {"measurements": [
        {"claim": "c-match", "deviation": 0.0, "tolerance": 0.1, "method": "m"},
        {"claim": "c-unver", "deviation": 1.0, "tolerance": 0.1, "method": "m"},
    ]})


def _ill_posed_file(tmp_path):
    return _write(tmp_path / "m-ill.json", {"measurements": [
        {"claim": "c-match", "deviation": -1.0, "tolerance": 0.0, "method": "m"},
        {"claim": "c-match", "deviation": True, "tolerance": 0.1, "method": "m"},
    ]})


def test_assess_human_output_requests_the_missing_evidence(tmp_path, capsys):
    code = main(["assess", _thesis_file(tmp_path), "--measurements", _measurements_file(tmp_path)])
    assert code == 0
    out = capsys.readouterr().out
    assert "evidence needed" in out
    assert "missing measurement" in out
    assert "provide a measurement row" in out


def test_assess_human_output_has_no_evidence_section_when_all_claims_verify(tmp_path, capsys):
    code = main(["assess", _thesis_file(tmp_path),
                 "--measurements", _full_measurements_file(tmp_path)])
    assert code == 0
    assert "evidence needed" not in capsys.readouterr().out


def test_assess_json_includes_typed_explanations_only_for_unverifiable_claims(tmp_path, capsys):
    code = main(["assess", _thesis_file(tmp_path),
                 "--measurements", _measurements_file(tmp_path), "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    unverifiable = {v["claim_id"] for v in payload["verdicts"] if v["status"] == "UNVERIFIABLE"}
    assert [e["claim_id"] for e in payload["explanations"]] == sorted(unverifiable)
    assert payload["explanations"][0]["missing"] == "measurement"
    assert payload["explanations"][0]["needed"]


def test_assess_warns_on_ill_posed_measurements_but_exits_zero(tmp_path, capsys):
    code = main(["assess", _thesis_file(tmp_path), "--measurements", _ill_posed_file(tmp_path)])
    assert code == 0
    err = capsys.readouterr().err
    assert "measurement warning" in err
    for expected in ("untrusted_deviation", "non_positive_tolerance",
                     "duplicate_claim_binding", "boolean_value"):
        assert expected in err


def test_assess_strict_exits_nonzero_on_ill_posed_measurements(tmp_path, capsys):
    code = main(["assess", _thesis_file(tmp_path),
                 "--measurements", _ill_posed_file(tmp_path), "--strict"])
    assert code == 1
    err = capsys.readouterr().err
    assert "measurement warning" in err
    assert "assess failed" in err


def test_assess_strict_passes_well_posed_measurements(tmp_path, capsys):
    code = main(["assess", _thesis_file(tmp_path),
                 "--measurements", _full_measurements_file(tmp_path), "--strict"])
    assert code == 0


def test_assess_json_carries_measurement_warnings(tmp_path, capsys):
    code = main(["assess", _thesis_file(tmp_path),
                 "--measurements", _ill_posed_file(tmp_path), "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    codes = {w["code"] for w in payload["measurement_warnings"]}
    assert "non_positive_tolerance" in codes
    assert "boolean_value" in codes


def test_run_strict_exits_nonzero_on_ill_posed_measurements(tmp_path, capsys):
    code = main(["run", _thesis_file(tmp_path), "--measurements", _ill_posed_file(tmp_path),
                 "--registry", str(tmp_path / "reg"), "--strict"])
    assert code == 1
    err = capsys.readouterr().err
    assert "measurement warning" in err
    assert "run failed" in err


def test_run_warns_and_records_measurement_warnings(tmp_path, capsys):
    code = main(["run", _thesis_file(tmp_path), "--measurements", _ill_posed_file(tmp_path),
                 "--registry", str(tmp_path / "reg"), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    assert "measurement warning" in captured.err
    record = json.loads(captured.out)
    assert {w["code"] for w in record["measurement_warnings"]} >= {
        "untrusted_deviation", "non_positive_tolerance"}


def test_run_records_no_warnings_for_well_posed_measurements(tmp_path, capsys):
    code = main(["run", _thesis_file(tmp_path), "--measurements", _full_measurements_file(tmp_path),
                 "--registry", str(tmp_path / "reg"), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    assert "measurement warning" not in captured.err
    assert json.loads(captured.out)["measurement_warnings"] == []


def _call(name, arguments):
    return handle_request({
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })


def test_mcp_assess_reports_explanations_and_warnings(tmp_path):
    resp = _call("crucible.assess", {
        "thesis": _thesis_file(tmp_path),
        "measurements": _ill_posed_file(tmp_path),
    })
    body = json.loads(resp["result"]["content"][0]["text"])
    assert {w["code"] for w in body["measurement_warnings"]} >= {"boolean_value"}
    assert [e["missing"] for e in body["explanations"]].count("measurement") == 1


def test_mcp_assess_strict_is_an_error_on_ill_posed_measurements(tmp_path):
    resp = _call("crucible.assess", {
        "thesis": _thesis_file(tmp_path),
        "measurements": _ill_posed_file(tmp_path),
        "strict": True,
    })
    assert resp["result"]["isError"] is True
