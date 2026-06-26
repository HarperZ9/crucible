from __future__ import annotations

import json

from crucible.cli import main


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _thesis_file(tmp_path, name):
    return _write(tmp_path / f"{name}.json", {
        "title": f"{name} thesis",
        "claims": [
            {"text": f"{name} latency holds", "falsification": "latency exceeds budget"},
            {"text": f"{name} quality holds", "falsification": "quality falls below floor"},
        ],
    })


def _measurements_file(tmp_path, name):
    return _write(tmp_path / f"{name}-measurements.json", {"measurements": [
        {"claim": f"{name} latency holds", "deviation": 0.0, "tolerance": 0.1, "method": "bench",
         "evidence": [f"{name} latency p95 42ms"]},
        {"claim": f"{name} quality holds", "deviation": 1.0, "tolerance": 0.1, "method": "bench",
         "evidence": [f"{name} quality 0.71"]},
    ]})


def _substrate_file(tmp_path, name):
    return _write(tmp_path / f"{name}-substrate.json", {
        "specs": {
            f"{name} latency holds": {"predicted": 10, "tolerance": 0.5, "observe": "latency"},
            f"{name} quality holds": {"predicted": 5, "tolerance": 0.5, "observe": "quality"},
        },
        "substrate": {"latency": 10, "quality": 5},
    })


def _manifest(tmp_path, jobs):
    return _write(tmp_path / "batch.json", {"jobs": jobs})


def test_batch_cli_assesses_manifest_jobs_and_writes_reports(tmp_path, capsys):
    alpha = _thesis_file(tmp_path, "alpha")
    beta = _thesis_file(tmp_path, "beta")
    manifest = _manifest(tmp_path, [
        {"id": "alpha-manual", "thesis": alpha, "measurements": _measurements_file(tmp_path, "alpha")},
        {"id": "beta-table", "thesis": beta, "substrate": _substrate_file(tmp_path, "beta")},
    ])
    reg = str(tmp_path / "reg")
    reports = tmp_path / "reports"

    assert main(["batch", manifest, "--registry", reg, "--reports", str(reports), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is True
    assert len(payload["jobs"]) == 2
    assert payload["jobs"][0]["id"] == "alpha-manual"
    assert payload["jobs"][0]["match"] == 1
    assert payload["jobs"][0]["drift"] == 1
    assert payload["jobs"][0]["report"].endswith("alpha-manual.md")
    assert payload["jobs"][1]["id"] == "beta-table"
    assert payload["jobs"][1]["match"] == 2
    assert payload["jobs"][1]["drift"] == 0
    assert (reports / "alpha-manual.md").read_text(encoding="utf-8").startswith("# crucible report: alpha thesis")
    assert (reports / "beta-table.md").read_text(encoding="utf-8").startswith("# crucible report: beta thesis")

    assert main(["registry", "stats", reg, "--json"]) == 0
    stats = json.loads(capsys.readouterr().out)
    assert stats["theses"] == 2
    assert stats["assessments"] == 2


def test_batch_cli_human_output_summarizes_each_job(tmp_path, capsys):
    manifest = _manifest(tmp_path, [
        {"id": "alpha-manual", "thesis": _thesis_file(tmp_path, "alpha"),
         "measurements": _measurements_file(tmp_path, "alpha")},
    ])

    assert main(["batch", manifest, "--registry", str(tmp_path / "reg")]) == 0
    out = capsys.readouterr().out

    assert "batch assessed 1 job(s)" in out
    assert "alpha-manual" in out
    assert "MATCH 1  DRIFT 1  UNVERIFIABLE 0" in out


def test_batch_cli_rejects_jobs_without_a_measurement_source(tmp_path, capsys):
    manifest = _manifest(tmp_path, [{"id": "bad", "thesis": _thesis_file(tmp_path, "alpha")}])

    assert main(["batch", manifest, "--registry", str(tmp_path / "reg")]) == 1
    assert "batch failed" in capsys.readouterr().err
