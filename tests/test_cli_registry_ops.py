from __future__ import annotations

import json

from crucible.cli import main


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _thesis_file(tmp_path):
    return _write(tmp_path / "thesis.json", {
        "title": "Registry ops thesis",
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


def test_registry_stats_json_reports_current_shape(tmp_path, capsys):
    reg = str(tmp_path / "reg")
    assert main(["assess", _thesis_file(tmp_path), "--measurements", _measurements_file(tmp_path),
                 "--registry", reg]) == 0
    capsys.readouterr()

    assert main(["registry", "stats", reg, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["theses"] == 1
    assert payload["claims"] == 2
    assert payload["verdicts"]["MATCH"] == 1
    assert payload["verdicts"]["DRIFT"] == 1


def test_registry_search_json_filters_by_scope_and_verdict(tmp_path, capsys):
    reg = str(tmp_path / "reg")
    assert main(["assess", _thesis_file(tmp_path), "--measurements", _measurements_file(tmp_path),
                 "--registry", reg]) == 0
    capsys.readouterr()

    assert main(["registry", "search", reg, "latency", "--verdict", "MATCH", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert len(payload) == 1
    assert payload[0]["title"] == "Registry ops thesis"
    assert payload[0]["latest_verdicts"] == ["DRIFT", "MATCH"]


def test_registry_prune_is_dry_run_until_apply(tmp_path, capsys):
    reg_dir = tmp_path / "reg"
    reg = str(reg_dir)
    assert main(["register", _thesis_file(tmp_path), "--registry", reg]) == 0
    capsys.readouterr()
    orphan = "e" * 64
    orphan_dir = reg_dir / "objects" / orphan[:2]
    orphan_dir.mkdir(parents=True, exist_ok=True)
    orphan_path = orphan_dir / orphan[2:]
    orphan_path.write_text("orphan body", encoding="utf-8")

    assert main(["registry", "prune", reg]) == 0
    assert "dry-run" in capsys.readouterr().out
    assert orphan_path.exists()

    assert main(["registry", "prune", reg, "--apply", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["deleted"] == [orphan]
    assert not orphan_path.exists()
