"""The standalone seal verifier: it re-derives the three assessment seals from an artifact's own
rows, passes an untampered record, and flags a tampered sealed row as DRIFT.

The verifier under test (``verify_seals.py`` at the repo root) imports no crucible package. This test
may import crucible to BUILD a real artifact, then drives the vendored file by path so the stranger
path (load the file, run it against a JSON artifact) is what is exercised.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

from crucible.assess import assess
from crucible.claim import make_claim
from crucible.thesis import make_thesis
from crucible.verdict import Measurement

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLOCK = lambda: 1000.0  # noqa: E731


def _verifier():
    spec = importlib.util.spec_from_file_location("verify_seals", ROOT / "verify_seals.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _artifact(tmp_path, name="assessment.json", *, recheck=False):
    thesis = make_thesis("mixed", [
        make_claim("holds", "f1"),
        make_claim("breaks", "f2"),
        make_claim("untested", "f3"),
    ], clock=CLOCK)
    rc = {"oracle": "x", "artifact_sha": "0" * 64} if recheck else None
    measurements = [
        Measurement(thesis.claims[0].id, thesis.claims[0].sha256, 0.0, 0.1, "oracle", 0.0, recheck=rc),
        Measurement(thesis.claims[1].id, thesis.claims[1].sha256, 9.0, 0.1, "oracle", 0.0),
    ]
    record, _ = assess(thesis, measurements, clock=CLOCK)
    path = tmp_path / name
    path.write_text(json.dumps(record.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def test_clean_artifact_is_match(tmp_path, capsys):
    path = _artifact(tmp_path)
    assert _verifier().main([str(path)]) == 0
    assert "MATCH" in capsys.readouterr().out


def test_clean_artifact_with_recheck_rows_is_match(tmp_path):
    path = _artifact(tmp_path, recheck=True)
    assert _verifier().main([str(path)]) == 0


def test_tampered_sealed_verdict_row_is_drift(tmp_path, capsys):
    path = _artifact(tmp_path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["verdicts"][0]["grounds"] = "asserted after the seal"  # a sealed field, seal left unchanged
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    assert _verifier().main([str(path)]) == 1
    assert "DRIFT" in capsys.readouterr().out


def test_tampered_count_is_drift(tmp_path):
    path = _artifact(tmp_path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["match"] = doc["match"] + 5
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    assert _verifier().main([str(path)]) == 1


def test_missing_artifact_is_unverifiable(tmp_path):
    assert _verifier().main([str(tmp_path / "does-not-exist.json")]) == 2
