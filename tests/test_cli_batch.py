from __future__ import annotations

import json

from crucible.cli import main


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _thesis_file(tmp_path, name):
    return _write(tmp_path / f"{name}.json", {
        "id": name,
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
    assert payload["jobs"][0]["report"].endswith("0001-alpha-manual.md")
    assert payload["jobs"][1]["id"] == "beta-table"
    assert payload["jobs"][1]["match"] == 2
    assert payload["jobs"][1]["drift"] == 0
    assert (reports / "0001-alpha-manual.md").read_text(encoding="utf-8").startswith("# crucible report: alpha thesis")
    assert (reports / "0002-beta-table.md").read_text(encoding="utf-8").startswith("# crucible report: beta thesis")

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


def test_batch_cli_resolves_thesis_ids_from_registry(tmp_path, capsys):
    thesis = _thesis_file(tmp_path, "alpha")
    reg = str(tmp_path / "reg")
    assert main(["register", thesis, "--registry", reg]) == 0
    capsys.readouterr()
    manifest = _manifest(tmp_path, [
        {"id": "alpha-by-id", "thesis": "alpha", "measurements": _measurements_file(tmp_path, "alpha")},
    ])

    assert main(["batch", manifest, "--registry", reg, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["jobs"][0]["id"] == "alpha-by-id"
    assert payload["jobs"][0]["thesis_id"] == "alpha"
    assert payload["jobs"][0]["match"] == 1
    assert payload["jobs"][0]["drift"] == 1


def test_batch_cli_rejects_jobs_without_a_measurement_source(tmp_path, capsys):
    manifest = _manifest(tmp_path, [{"id": "bad", "thesis": _thesis_file(tmp_path, "alpha")}])

    assert main(["batch", manifest, "--registry", str(tmp_path / "reg")]) == 1
    assert "batch failed" in capsys.readouterr().err


def test_batch_cli_prefixes_report_paths_to_avoid_slug_collisions(tmp_path, capsys):
    manifest = _manifest(tmp_path, [
        {"id": "a/b", "thesis": _thesis_file(tmp_path, "alpha"),
         "measurements": _measurements_file(tmp_path, "alpha")},
        {"id": "a?b", "thesis": _thesis_file(tmp_path, "beta"),
         "measurements": _measurements_file(tmp_path, "beta")},
    ])
    reports = tmp_path / "reports"

    assert main(["batch", manifest, "--registry", str(tmp_path / "reg"),
                 "--reports", str(reports), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["jobs"][0]["report"].endswith("0001-a-b.md")
    assert payload["jobs"][1]["report"].endswith("0002-a-b.md")
    assert len(list(reports.glob("*.md"))) == 2


def test_batch_cli_rejects_missing_manifest_relative_measurements_even_if_cwd_has_file(
    tmp_path,
    monkeypatch,
    capsys,
):
    manifest_dir = tmp_path / "manifest"
    manifest_dir.mkdir()
    thesis = _thesis_file(manifest_dir, "alpha")
    _measurements_file(tmp_path, "alpha")
    manifest = _write(manifest_dir / "batch.json", {
        "jobs": [{"id": "bad-path", "thesis": thesis, "measurements": "alpha-measurements.json"}],
    })
    monkeypatch.chdir(tmp_path)

    assert main(["batch", manifest, "--registry", str(tmp_path / "reg")]) == 1
    assert "batch failed" in capsys.readouterr().err


def test_batch_cli_rejects_missing_manifest_relative_substrate_even_if_cwd_has_file(
    tmp_path,
    monkeypatch,
    capsys,
):
    manifest_dir = tmp_path / "manifest"
    manifest_dir.mkdir()
    thesis = _thesis_file(manifest_dir, "alpha")
    _substrate_file(tmp_path, "alpha")
    manifest = _write(manifest_dir / "batch.json", {
        "jobs": [{"id": "bad-path", "thesis": thesis, "substrate": "alpha-substrate.json"}],
    })
    monkeypatch.chdir(tmp_path)

    assert main(["batch", manifest, "--registry", str(tmp_path / "reg")]) == 1
    assert "batch failed" in capsys.readouterr().err


def test_batch_cli_rejects_missing_manifest_relative_thesis_even_if_cwd_has_file(
    tmp_path,
    monkeypatch,
    capsys,
):
    manifest_dir = tmp_path / "manifest"
    manifest_dir.mkdir()
    _thesis_file(tmp_path, "alpha")
    manifest = _write(manifest_dir / "batch.json", {
        "jobs": [{"id": "bad-path", "thesis": "alpha.json",
                  "measurements": _measurements_file(manifest_dir, "alpha")}],
    })
    monkeypatch.chdir(tmp_path)

    assert main(["batch", manifest, "--registry", str(tmp_path / "reg")]) == 1
    assert "batch failed" in capsys.readouterr().err
