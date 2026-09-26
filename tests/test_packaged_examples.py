"""The quickstart inputs ship inside the package.

Before 1.3.0 the README's first run read ``examples/*.json``, which only a clone has, so the
documented first command failed after ``pip install crucible-bench``. The inputs now ship as
package data under ``crucible.examples`` and ``crucible examples --out DIR`` writes them out. The
copies in the package are the repository's files byte for byte; the first test fails on drift.
"""
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import pytest

from crucible.cli import main

ROOT = Path(__file__).resolve().parent.parent
INPUTS = (
    "batch-binary-search.json",
    "measurements-binary-search.json",
    "refine-discovery-loop.json",
    "substrate-binary-search.json",
    "thesis-binary-search.json",
)


def test_packaged_inputs_match_the_repository_examples():
    package = resources.files("crucible.examples")
    shipped = sorted(p.name for p in package.iterdir() if p.name.endswith(".json"))
    assert shipped == sorted(INPUTS)
    for name in INPUTS:
        assert package.joinpath(name).read_bytes() == (ROOT / "examples" / name).read_bytes(), name


def test_every_repository_json_example_is_packaged():
    in_repo = sorted(p.name for p in (ROOT / "examples").glob("*.json"))
    assert in_repo == sorted(INPUTS)


def test_pyproject_declares_the_package_data():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"crucible.examples" = ["*.json"]' in pyproject


def test_examples_command_writes_the_inputs(tmp_path, capsys):
    out = tmp_path / "crucible-examples"
    assert main(["examples", "--out", str(out), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert sorted(payload["files"]) == sorted(INPUTS)
    for name in INPUTS:
        assert (out / name).read_bytes() == (ROOT / "examples" / name).read_bytes()


def test_examples_command_refuses_an_existing_folder(tmp_path, capsys):
    out = tmp_path / "taken"
    out.mkdir()
    (out / "keep.txt").write_text("mine", encoding="utf-8")
    assert main(["examples", "--out", str(out)]) == 2
    assert "exists" in capsys.readouterr().err
    assert sorted(p.name for p in out.iterdir()) == ["keep.txt"]


def test_examples_command_needs_an_out_folder():
    with pytest.raises(SystemExit) as exc:
        main(["examples"])
    assert exc.value.code == 2


def test_written_examples_run_the_documented_first_command(tmp_path, capsys):
    out = tmp_path / "ex"
    assert main(["examples", "--out", str(out)]) == 0
    capsys.readouterr()
    code = main(["run", str(out / "thesis-binary-search.json"),
                 "--measurements", str(out / "measurements-binary-search.json"), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    counts = payload["assessment"]
    assert (counts["match"], counts["drift"], counts["unverifiable"]) == (1, 1, 1)
