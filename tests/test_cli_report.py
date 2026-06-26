from __future__ import annotations

import json

from crucible.cli import main


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _thesis_file(tmp_path):
    return _write(tmp_path / "thesis.json", {
        "title": "Report thesis",
        "claims": [
            {"text": "latency stays under budget", "falsification": "latency exceeds budget"},
            {"text": "quality stays above floor", "falsification": "quality falls below floor"},
        ],
    })


def _measurements_file(tmp_path):
    return _write(tmp_path / "measurements.json", {"measurements": [
        {"claim": "latency stays under budget", "deviation": 0.0, "tolerance": 0.1, "method": "bench",
         "evidence": ["p95 latency 42ms"]},
        {"claim": "quality stays above floor", "deviation": 1.0, "tolerance": 0.1, "method": "bench",
         "evidence": ["quality fell to 0.71"]},
    ]})


def test_report_cli_renders_latest_assessment_from_registry(tmp_path, capsys):
    reg = str(tmp_path / "reg")
    assert main(["assess", _thesis_file(tmp_path), "--measurements", _measurements_file(tmp_path),
                 "--registry", reg]) == 0
    capsys.readouterr()

    assert main(["report", reg]) == 0
    out = capsys.readouterr().out

    assert out.startswith("# crucible report: Report thesis")
    assert "- counts: MATCH 1 / DRIFT 1 / UNVERIFIABLE 0" in out
    assert "| latency stays under budget | MATCH | 1 | bench | deviation 0 within tolerance 0.1 |" in out
    assert "## Measurement Evidence" in out


def test_report_cli_writes_to_file_without_echoing_body(tmp_path, capsys):
    reg = str(tmp_path / "reg")
    report_path = tmp_path / "report.md"
    assert main(["assess", _thesis_file(tmp_path), "--measurements", _measurements_file(tmp_path),
                 "--registry", reg]) == 0
    capsys.readouterr()

    assert main(["report", reg, "--out", str(report_path)]) == 0
    out = capsys.readouterr().out

    assert out.strip() == f"wrote report to {report_path}"
    assert report_path.read_text(encoding="utf-8").startswith("# crucible report: Report thesis")


def test_report_cli_refuses_to_overwrite_existing_file(tmp_path, capsys):
    reg = str(tmp_path / "reg")
    report_path = tmp_path / "report.md"
    report_path.write_text("keep me", encoding="utf-8")
    assert main(["assess", _thesis_file(tmp_path), "--measurements", _measurements_file(tmp_path),
                 "--registry", reg]) == 0
    capsys.readouterr()

    assert main(["report", reg, "--out", str(report_path)]) == 1

    assert report_path.read_text(encoding="utf-8") == "keep me"
    assert "exists" in capsys.readouterr().err


def test_report_cli_empty_registry_is_clean_error(tmp_path, capsys):
    assert main(["report", str(tmp_path / "reg")]) == 1
    assert "report failed" in capsys.readouterr().err
