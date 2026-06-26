from __future__ import annotations

import json

from crucible.cli import main


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _thesis_file(tmp_path):
    return _write(tmp_path / "thesis.json", {
        "title": "Run thesis",
        "claims": [
            {"text": "latency stays under budget", "falsification": "latency exceeds budget"},
            {"text": "quality stays above floor", "falsification": "quality falls below floor"},
        ],
    })


def _measurements_file(tmp_path):
    return _write(tmp_path / "measurements.json", {"measurements": [
        {"claim": "latency stays under budget", "deviation": 0.0, "tolerance": 0.1, "method": "bench"},
        {"claim": "quality stays above floor", "deviation": 1.0, "tolerance": 0.1, "method": "bench"},
    ]})


def _bad_measurements_file(tmp_path):
    return _write(tmp_path / "bad-measurements.json", {"measurements": [
        {"claim": "ghost claim", "deviation": 0.0, "tolerance": 0.1, "method": "bench"},
    ]})


def _substrate_file(tmp_path):
    return _write(tmp_path / "substrate.json", {
        "specs": {
            "latency stays under budget": {"predicted": 10, "tolerance": 0.5, "observe": "latency"},
            "quality stays above floor": {"predicted": 5, "tolerance": 0.5, "observe": "quality"},
        },
        "substrate": {"latency": 10, "quality": 2},
    })


def test_run_json_records_complete_session_and_report(tmp_path, capsys):
    reg = str(tmp_path / "reg")
    report_path = tmp_path / "report.md"
    run_path = tmp_path / "run.json"

    assert main(["run", _thesis_file(tmp_path), "--measurements", _measurements_file(tmp_path),
                 "--registry", reg, "--report", str(report_path), "--out", str(run_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is True
    assert payload["thesis"]["title"] == "Run thesis"
    assert len(payload["refutations"]) == 2
    assert payload["assessment"]["match"] == 1
    assert payload["assessment"]["drift"] == 1
    assert payload["checks"] == {"seals_ok": True, "thesis_ok": True, "verdicts_rederive": True}
    assert {row["status"] for row in payload["verdicts"]} == {"MATCH", "DRIFT"}
    assert payload["report"] == str(report_path)
    assert json.loads(run_path.read_text(encoding="utf-8")) == payload
    assert report_path.read_text(encoding="utf-8").startswith("# crucible report: Run thesis")

    assert main(["verdicts", reg, "--verify"]) == 0


def test_run_bundle_writes_self_contained_review_packet(tmp_path, capsys):
    bundle = tmp_path / "packet"
    reg = str(tmp_path / "reg")

    assert main(["run", _thesis_file(tmp_path), "--measurements", _measurements_file(tmp_path),
                 "--registry", reg, "--bundle", str(bundle), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["bundle"] == str(bundle)
    assert payload["report"] == str(bundle / "report.md")
    assert payload["record"] == str(bundle / "run.json")
    assert payload["spec"] == str(bundle / "spec.json")
    assert payload["review"] == str(bundle / "review.md")
    assert payload["verifier"]["mode"] == "cleanroom"
    assert payload["verifier"]["inputs"] == ["spec.json", "run.json", "report.md"]
    assert "worker context" in payload["verifier"]["excluded"]
    assert "not checkable yet" in payload["verifier"]["checkability"]
    assert (bundle / "report.md").read_text(encoding="utf-8").startswith("# crucible report: Run thesis")
    spec = json.loads((bundle / "spec.json").read_text(encoding="utf-8"))
    assert spec["claims"][0]["falsification"] == "latency exceeds budget"
    review = (bundle / "review.md").read_text(encoding="utf-8")
    assert "original spec and the artifact" in review
    assert "reasoning trace" in review
    assert json.loads((bundle / "run.json").read_text(encoding="utf-8"))["bundle"] == str(bundle)


def test_run_human_output_with_substrate_is_scannable(tmp_path, capsys):
    reg = str(tmp_path / "reg")

    assert main(["run", _thesis_file(tmp_path), "--substrate", _substrate_file(tmp_path),
                 "--registry", reg]) == 0
    out = capsys.readouterr().out

    assert "ran thesis" in out
    assert "steelman refutations: 2" in out
    assert "MATCH 1" in out and "DRIFT 1" in out and "UNVERIFIABLE 0" in out
    assert "re-derived from disk: True" in out


def test_run_requires_registry_and_one_measure_source(tmp_path, capsys):
    thesis = _thesis_file(tmp_path)
    measurements = _measurements_file(tmp_path)
    substrate = _substrate_file(tmp_path)

    assert main(["run", thesis, "--measurements", measurements]) == 1
    assert "run failed" in capsys.readouterr().err

    assert main(["run", thesis, "--registry", str(tmp_path / "reg"),
                 "--measurements", measurements, "--substrate", substrate]) == 1
    assert "exactly one" in capsys.readouterr().err


def test_run_bundle_refuses_existing_dir_and_overlapping_paths(tmp_path, capsys):
    thesis = _thesis_file(tmp_path)
    measurements = _measurements_file(tmp_path)
    reg = str(tmp_path / "reg")
    bundle = tmp_path / "packet"
    bundle.mkdir()

    assert main(["run", thesis, "--measurements", measurements, "--registry", reg,
                 "--bundle", str(bundle)]) == 1
    assert "already exists" in capsys.readouterr().err

    assert main(["run", thesis, "--measurements", measurements, "--registry", reg,
                 "--bundle", str(tmp_path / "other"), "--report", str(tmp_path / "report.md")]) == 1
    assert "cannot be combined" in capsys.readouterr().err


def test_run_bundle_is_not_created_when_run_fails(tmp_path, capsys):
    bundle = tmp_path / "packet"

    assert main(["run", _thesis_file(tmp_path), "--measurements", _bad_measurements_file(tmp_path),
                 "--registry", str(tmp_path / "reg"), "--bundle", str(bundle)]) == 1

    assert "unknown claim" in capsys.readouterr().err
    assert not bundle.exists()
