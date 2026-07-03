from __future__ import annotations

import json

from crucible.cli import main


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _thesis_file(tmp_path):
    return _write(tmp_path / "thesis.json", {
        "title": "CI gate thesis",
        "claims": [
            {"text": "c-hold", "falsification": "f1"},
            {"text": "c-break", "falsification": "f2"},
        ],
    })


def _measurements_file(tmp_path, name, hold, break_):
    return _write(tmp_path / name, {"measurements": [
        {"claim": "c-hold", "deviation": hold, "tolerance": 1.0, "method": "m"},
        {"claim": "c-break", "deviation": break_, "tolerance": 1.0, "method": "m"},
    ]})


def _seed_registry(tmp_path, hold, break_, name="m.json"):
    reg = str(tmp_path / "reg")
    thesis = _thesis_file(tmp_path)
    meas = _measurements_file(tmp_path, name, hold, break_)
    assert main(["assess", thesis, "--measurements", meas, "--registry", reg]) == 0
    return reg


def test_write_baseline_captures_current_verdicts(tmp_path, capsys):
    reg = _seed_registry(tmp_path, 0.2, 0.3)
    capsys.readouterr()
    baseline = tmp_path / "base.json"
    assert main(["ci", reg, "--write-baseline", str(baseline)]) == 0
    out = capsys.readouterr().out
    assert "wrote baseline of 2 verdict cell(s)" in out
    payload = json.loads(baseline.read_text(encoding="utf-8"))
    assert payload["kind"] == "crucible.ci-baseline/v1"
    assert len(payload["cells"]) == 2
    assert all(cell["status"] == "MATCH" for cell in payload["cells"])
    # Every cell references the re-derivable assessment packet it was read from.
    assert all(cell["assessment_seal"] for cell in payload["cells"])


def test_no_regression_exits_zero_with_match_summary(tmp_path, capsys):
    reg = _seed_registry(tmp_path, 0.2, 0.3)
    capsys.readouterr()
    baseline = tmp_path / "base.json"
    assert main(["ci", reg, "--write-baseline", str(baseline)]) == 0
    capsys.readouterr()

    assert main(["ci", reg, "--baseline", str(baseline)]) == 0
    out = capsys.readouterr().out
    assert "PASS: no regressions" in out
    assert "MATCH | MATCH | held" in out
    assert "### What regressed" not in out


def test_injected_regression_exits_nonzero_and_names_the_drifted_claim(tmp_path, capsys):
    reg = _seed_registry(tmp_path, 0.2, 0.3, name="m1.json")
    capsys.readouterr()
    baseline = tmp_path / "base.json"
    assert main(["ci", reg, "--write-baseline", str(baseline)]) == 0
    capsys.readouterr()

    # Re-assess so c-break drifts (deviation now exceeds tolerance).
    thesis = _thesis_file(tmp_path)
    regressed = _measurements_file(tmp_path, "m2.json", 0.2, 1.9)
    assert main(["assess", thesis, "--measurements", regressed, "--registry", reg]) == 0
    capsys.readouterr()

    # Identify the claim id of c-break from the baseline so we can assert the gate names it.
    base_cells = json.loads(baseline.read_text(encoding="utf-8"))["cells"]
    # Both baselined claims were MATCH; the drifted one is whichever id now reads DRIFT in JSON.
    assert main(["ci", reg, "--baseline", str(baseline), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    drifted_id = payload["regressions"][0]["claim_id"]
    assert drifted_id in {c["claim_id"] for c in base_cells}

    code = main(["ci", reg, "--baseline", str(baseline)])
    captured = capsys.readouterr()
    assert code == 1
    assert "FAIL: 1 regression(s)" in captured.out
    assert "MATCH -> DRIFT" in captured.out
    # The drifted claim is named (by its id) on stderr for the CI log, and in the Markdown body.
    assert drifted_id in captured.err
    assert drifted_id in captured.out
    assert "regressed" in captured.out


def test_markdown_summary_is_deterministic_across_runs(tmp_path, capsys):
    reg = _seed_registry(tmp_path, 0.2, 0.3, name="m1.json")
    capsys.readouterr()
    baseline = tmp_path / "base.json"
    assert main(["ci", reg, "--write-baseline", str(baseline)]) == 0
    capsys.readouterr()
    thesis = _thesis_file(tmp_path)
    regressed = _measurements_file(tmp_path, "m2.json", 0.2, 1.9)
    assert main(["assess", thesis, "--measurements", regressed, "--registry", reg]) == 0
    capsys.readouterr()

    assert main(["ci", reg, "--baseline", str(baseline)]) == 1
    first = capsys.readouterr().out
    assert main(["ci", reg, "--baseline", str(baseline)]) == 1
    second = capsys.readouterr().out
    assert first == second


def test_json_output_carries_regression_and_packet_seals(tmp_path, capsys):
    reg = _seed_registry(tmp_path, 0.2, 0.3, name="m1.json")
    capsys.readouterr()
    baseline = tmp_path / "base.json"
    assert main(["ci", reg, "--write-baseline", str(baseline)]) == 0
    capsys.readouterr()
    thesis = _thesis_file(tmp_path)
    regressed = _measurements_file(tmp_path, "m2.json", 0.2, 1.9)
    assert main(["assess", thesis, "--measurements", regressed, "--registry", reg]) == 0
    capsys.readouterr()

    assert main(["ci", reg, "--baseline", str(baseline), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is False
    assert len(payload["regressions"]) == 1
    reg_row = payload["regressions"][0]
    assert reg_row["baseline_status"] == "MATCH"
    assert reg_row["current_status"] == "DRIFT"
    assert reg_row["current_seal"]  # references the re-derivable current packet


def test_out_writes_markdown_file_and_still_signals_regression(tmp_path, capsys):
    reg = _seed_registry(tmp_path, 0.2, 0.3, name="m1.json")
    capsys.readouterr()
    baseline = tmp_path / "base.json"
    assert main(["ci", reg, "--write-baseline", str(baseline)]) == 0
    capsys.readouterr()
    thesis = _thesis_file(tmp_path)
    regressed = _measurements_file(tmp_path, "m2.json", 0.2, 1.9)
    assert main(["assess", thesis, "--measurements", regressed, "--registry", reg]) == 0
    capsys.readouterr()

    summary = tmp_path / "summary.md"
    assert main(["ci", reg, "--baseline", str(baseline), "--out", str(summary)]) == 1
    body = summary.read_text(encoding="utf-8")
    assert "crucible CI regression gate" in body
    assert "FAIL: 1 regression(s)" in body


def test_missing_baseline_argument_fails_cleanly(tmp_path, capsys):
    reg = _seed_registry(tmp_path, 0.2, 0.3)
    capsys.readouterr()
    assert main(["ci", reg]) == 1
    assert "pass --baseline FILE" in capsys.readouterr().err


def test_gate_rejects_a_tampered_baseline_file(tmp_path, capsys):
    reg = _seed_registry(tmp_path, 0.2, 0.3)
    capsys.readouterr()
    baseline = tmp_path / "base.json"
    assert main(["ci", reg, "--write-baseline", str(baseline)]) == 0
    capsys.readouterr()
    payload = json.loads(baseline.read_text(encoding="utf-8"))
    payload["cells"][0]["status"] = "DRIFT"
    baseline.write_text(json.dumps(payload), encoding="utf-8")

    assert main(["ci", reg, "--baseline", str(baseline)]) == 1
    assert "seal does not match" in capsys.readouterr().err
