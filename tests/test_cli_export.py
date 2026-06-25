from __future__ import annotations

import json

from crucible.cli import main


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def test_export_publishable_thesis_as_json(tmp_path, capsys):
    thesis = _write(tmp_path / "thesis.json", {
        "title": "Publishable",
        "claims": [{"text": "claim", "falsification": "counterexample"}],
    })

    assert main(["export", thesis]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["title"] == "Publishable"
    assert payload["disposition"] == "publishable"
    assert payload["claims"][0]["text"] == "claim"


def test_export_refuses_fenced_thesis(tmp_path, capsys):
    thesis = _write(tmp_path / "fenced.json", {
        "title": "Fenced",
        "disposition": "fenced",
        "claims": [{"text": "claim", "falsification": "counterexample"}],
    })

    assert main(["export", thesis]) == 1
    assert "export failed" in capsys.readouterr().err


def test_export_by_id_from_registry(tmp_path, capsys):
    thesis = _write(tmp_path / "thesis.json", {
        "title": "Stored",
        "claims": [{"text": "claim", "falsification": "counterexample"}],
    })
    reg = str(tmp_path / "reg")
    assert main(["register", thesis, "--registry", reg]) == 0
    capsys.readouterr()
    assert main(["registry", "list", reg, "--json"]) == 0
    tid = json.loads(capsys.readouterr().out)[0]["id"]

    assert main(["export", tid, "--registry", reg]) == 0
    assert json.loads(capsys.readouterr().out)["title"] == "Stored"
