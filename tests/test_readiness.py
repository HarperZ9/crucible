from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from crucible.cli import main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def test_flagship_brand_assets_exist_and_are_referenced():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    for rel in [
        "docs/brand/crucible-mark.svg",
        "docs/brand/crucible-hero.png",
        "examples/crucible-demo.html",
    ]:
        assert (root / rel).exists(), rel
        assert rel in readme
    assert "## Why it matters" in readme
    assert "## Work with it" in readme
    demo = (root / "examples/crucible-demo.html").read_text(encoding="utf-8")
    assert "original spec and artifact only" in demo
    assert "UNVERIFIABLE" in demo


def _example(name: str) -> str:
    return str(EXAMPLES / name)


def _json_out(capsys):
    return json.loads(capsys.readouterr().out)


def test_demo_example_runs_as_a_script():
    run = subprocess.run([sys.executable, _example("demo.py")], cwd=ROOT, capture_output=True,
                         text=True, timeout=10, check=False)

    assert run.returncode == 0
    assert "MATCH" in run.stdout
    assert "DRIFT" in run.stdout
    assert "UNVERIFIABLE" in run.stdout
    assert "verified True" in run.stdout
    assert "verified False" in run.stdout


def test_example_assess_registry_search_and_report(tmp_path, capsys):
    thesis = _example("thesis-binary-search.json")
    measurements = _example("measurements-binary-search.json")
    reg = str(tmp_path / "reg")
    run_reg = str(tmp_path / "run-reg")
    run_bundle = tmp_path / "run-packet"

    assert main(["register", thesis, "--registry", reg, "--json"]) == 0
    registered = _json_out(capsys)
    assert registered["stored"]["registered"] is True

    assert main(["assess", thesis, "--measurements", measurements, "--registry", reg, "--json"]) == 0
    assessed = _json_out(capsys)
    assert assessed["assessment"]["match"] == 1
    assert assessed["assessment"]["drift"] == 1
    assert assessed["assessment"]["unverifiable"] == 1

    assert main(["registry", "stats", reg, "--json"]) == 0
    stats = _json_out(capsys)
    assert stats["theses"] == 1
    assert stats["assessments"] == 1

    assert main(["registry", "search", reg, "binary", "--verdict", "DRIFT", "--json"]) == 0
    rows = _json_out(capsys)
    assert len(rows) == 1
    assert rows[0]["title"] == "Binary search comparison bounds"

    assert main(["report", reg]) == 0
    report = capsys.readouterr().out
    assert report.startswith("# crucible report: Binary search comparison bounds")
    assert "## Verdicts" in report

    assert main(["run", thesis, "--measurements", measurements, "--registry", run_reg,
                 "--bundle", str(run_bundle), "--json"]) == 0
    run = _json_out(capsys)
    assert run["ok"] is True
    assert run["report"] == "report.md"
    assert run["spec"] == "spec.json"
    assert run["review"] == "review.md"
    assert run["verifier"]["mode"] == "cleanroom"
    assert json.loads((run_bundle / "run.json").read_text(encoding="utf-8"))["assessment"]["match"] == 1
    assert "original spec and the artifact" in (run_bundle / "review.md").read_text(encoding="utf-8")

    assert main(["review", str(run_bundle), "--json"]) == 0
    reviewed = _json_out(capsys)
    assert reviewed["checks"]["artifact_paths"] is True
    assert reviewed["checks"]["report_matches_run"] is True
    assert reviewed["checks"]["review_instructions"] is True
    assert reviewed["checks"]["run_integrity"] is True


def test_example_measure_and_refine_through_public_cli(capsys):
    thesis = _example("thesis-binary-search.json")
    substrate = _example("substrate-binary-search.json")
    refine_config = _example("refine-discovery-loop.json")

    assert main(["measure", thesis, "--substrate", substrate, "--json"]) == 0
    measured = _json_out(capsys)
    assert measured["assessment"]["match"] == 1
    assert measured["assessment"]["drift"] == 1

    assert main(["refine", refine_config, "--json"]) == 0
    refined = _json_out(capsys)
    assert refined["status"] == "correct"
    assert refined["iterations"] == 2


def test_example_batch_and_export_through_public_cli(tmp_path, capsys):
    thesis = _example("thesis-binary-search.json")

    assert main(["batch", _example("batch-binary-search.json"),
                 "--registry", str(tmp_path / "batch-reg"), "--json"]) == 0
    batched = _json_out(capsys)
    assert len(batched["jobs"]) == 2
    assert batched["jobs"][0]["id"] == "binary-search-manual"
    assert batched["jobs"][0]["match"] == 1
    assert batched["jobs"][0]["drift"] == 1
    assert batched["jobs"][1]["id"] == "binary-search-substrate"
    assert batched["jobs"][1]["unverifiable"] == 1

    assert main(["export", thesis]) == 0
    exported = _json_out(capsys)
    assert exported["disposition"] == "publishable"


def test_cli_help_advertises_shipped_command_surface(capsys):
    with pytest.raises(SystemExit) as root_help:
        main(["--help"])
    assert root_help.value.code == 0
    root = capsys.readouterr().out
    for command in ("register", "assess", "steelman", "measure", "run", "recheck", "review", "registry",
                    "report", "batch", "verdicts", "drift", "export", "refine", "measurement-gate"):
        assert command in root

    with pytest.raises(SystemExit) as registry_help:
        main(["registry", "--help"])
    assert registry_help.value.code == 0
    registry = capsys.readouterr().out
    for action in ("list", "verify", "stats", "search", "prune"):
        assert action in registry


def test_release_workflow_uses_pinned_build_tool_requirements():
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    requirements = ROOT / "requirements-release.txt"
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert requirements.exists()
    pins = requirements.read_text(encoding="utf-8")
    assert "build==" in pins
    assert "twine==" in pins
    assert "setuptools==" in pins
    assert 'requires = ["setuptools==' in pyproject
    assert "pip install --requirement requirements-release.txt" in workflow
    assert "python -m build --no-isolation" in workflow
    assert "pip install --upgrade " + "build twine" not in workflow
    assert "workflow_" + "dispatch" not in workflow


def test_release_docs_define_cleanroom_checkability_rules():
    readiness = (ROOT / "docs" / "RELEASE-READINESS.md").read_text(encoding="utf-8")
    normalized_readiness = " ".join(readiness.lower().split())
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

    assert "crucible Fair-Source License" in license_text
    assert "Cru" + "cible" not in license_text
    assert "Cleanroom acceptance" in readiness
    assert "api[_-]?key|" + "to" + "ken|se" + "cret|pass" + "word" in readiness
    assert "before 1\\.0|" + "release-" + "candidate" in readiness
    assert "caller-supplied measurement evidence is treated as user data" in normalized_readiness
    assert "not artifact-only acceptance criteria" in normalized_readiness
    assert "spec.json" in readiness and "review.md" in readiness
    assert "oracle replay pack" in normalized_readiness
    assert "replay pack template" in normalized_readiness
    assert "assessment block" in normalized_readiness
    assert "report content that does not render from `run.json`" in normalized_readiness
    assert "review instructions that diverge from the cleanroom boundary" in normalized_readiness
    assert "references those artifacts relative to the packet root" in normalized_readiness
    assert "run.json artifact paths" in normalized_readiness
    assert "failed embedded run integrity checks" in normalized_readiness
    assert "crucible review" in normalized_readiness
