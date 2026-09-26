"""The widened-tolerance probe, through the public CLI.

crucible-bench 1.2.0 returned MATCH for these inputs: the thesis seals tolerance 0.5 on a claim
whose measured deviation is 8, and the measurement widens the tolerance to 10 after the seal. The
fixed verdict is UNVERIFIABLE. The same files feed ``scripts/smoke_wheel.py``, which runs them
against a built wheel in a fresh environment, so the release check and this test share one input.
"""
from __future__ import annotations

import json
from pathlib import Path

from crucible.cli import main

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sealed-tolerance"


def _assess(measurements: str, capsys) -> list[str]:
    code = main(["assess", str(FIXTURES / "thesis.json"),
                 "--measurements", str(FIXTURES / measurements), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code in (0, 1)
    return [v["status"] for v in payload["verdicts"]]


def test_widened_tolerance_is_unverifiable(capsys):
    assert _assess("measurements-widened.json", capsys) == ["UNVERIFIABLE"]


def test_the_sealed_tolerance_still_decides(capsys):
    assert _assess("measurements-sealed.json", capsys) == ["DRIFT"]
