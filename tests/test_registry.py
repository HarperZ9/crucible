"""The registry: content-addressed claim bodies, deduped, re-verifiable, traversal guarded."""
from __future__ import annotations

import os

import pytest

from crucible.claim import make_claim
from crucible.registry import CORRUPT, MATCH, MISSING, Registry, _check_sha
from crucible.thesis import make_thesis, verify_thesis

CLOCK = lambda: 1000.0  # noqa: E731


def _thesis(title="t"):
    return make_thesis(title, [make_claim("claim one", "refute one"),
                               make_claim("claim two", "refute two")], clock=CLOCK)


def test_register_writes_objects_and_a_row(tmp_path):
    reg = Registry(str(tmp_path), fsync=False)
    summary = reg.register(_thesis())
    assert summary == {"added": 2, "deduped": 0, "total": 2, "registered": True}
    rows = list(reg.theses())
    assert len(rows) == 1 and len(rows[0]["claims"]) == 2
    assert os.path.isdir(tmp_path / "objects")


def test_reregister_is_idempotent_at_the_row_level(tmp_path):
    reg = Registry(str(tmp_path), fsync=False)
    t = _thesis()
    reg.register(t)
    again = reg.register(t)
    assert again["registered"] is False
    assert len(list(reg.theses())) == 1


def test_identical_claim_body_is_deduped(tmp_path):
    reg = Registry(str(tmp_path), fsync=False)
    shared = make_claim("shared claim", "shared refute")
    t1 = make_thesis("t1", [shared], clock=CLOCK)
    t2 = make_thesis("t2", [shared], clock=CLOCK)
    reg.register(t1)
    summary = reg.register(t2)
    assert summary["deduped"] == 1 and summary["added"] == 0


def test_verify_reports_match_for_intact_bodies(tmp_path):
    reg = Registry(str(tmp_path), fsync=False)
    reg.register(_thesis())
    results = reg.verify()
    assert results and all(r["status"] == MATCH for r in results)


def test_verify_reports_missing_when_body_deleted(tmp_path):
    reg = Registry(str(tmp_path), fsync=False)
    t = _thesis()
    reg.register(t)
    sha = t.claims[0].sha256
    os.remove(tmp_path / "objects" / sha[:2] / sha[2:])
    statuses = {r["sha256"]: r["status"] for r in reg.verify()}
    assert statuses[sha] == MISSING


def test_verify_reports_corrupt_when_body_altered(tmp_path):
    reg = Registry(str(tmp_path), fsync=False)
    t = _thesis()
    reg.register(t)
    sha = t.claims[0].sha256
    path = tmp_path / "objects" / sha[:2] / sha[2:]
    path.write_text("tampered body", encoding="utf-8")
    statuses = {r["sha256"]: r["status"] for r in reg.verify()}
    assert statuses[sha] == CORRUPT


def test_load_thesis_reconstructs_and_reverifies(tmp_path):
    reg = Registry(str(tmp_path), fsync=False)
    t = _thesis()
    reg.register(t)
    loaded = reg.get_thesis(t.id)
    assert loaded is not None
    assert loaded.seal == t.seal
    assert verify_thesis(loaded)
    assert reg.get_thesis("nonexistent") is None


def test_get_thesis_refuses_a_tampered_body(tmp_path):
    reg = Registry(str(tmp_path), fsync=False)
    t = _thesis()
    reg.register(t)
    sha = t.claims[0].sha256  # overwrite the body so it no longer hashes to its receipt
    (tmp_path / "objects" / sha[:2] / sha[2:]).write_text(
        '{"text": "evil", "falsification": "x"}', encoding="utf-8")
    with pytest.raises(ValueError, match="failed verification"):
        reg.get_thesis(t.id)


def test_verify_seals_catches_a_swapped_claim_that_body_verify_misses(tmp_path):
    import json

    reg = Registry(str(tmp_path), fsync=False)
    t = _thesis()
    reg.register(t)
    # Repoint the first claim's sha at the second claim's (intact) body: a swap without re-sealing.
    theses_path = tmp_path / "theses.jsonl"
    row = json.loads(theses_path.read_text(encoding="utf-8").strip())
    row["claims"][0]["sha256"] = t.claims[1].sha256
    theses_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    # Body-level verify sees two intact bodies and reports all MATCH...
    assert all(r["status"] == MATCH for r in reg.verify())
    # ...but the seal pass catches that the thesis is no longer the claims it was sealed over.
    assert any(r["status"] == "SEAL_BROKEN" for r in reg.verify_seals())


def test_assessment_history_appends_and_streams(tmp_path):
    reg = Registry(str(tmp_path), fsync=False)
    reg.add_assessment({"thesis_id": "a", "seal": "x"})
    reg.add_assessment({"thesis_id": "b", "seal": "y"})
    records = list(reg.assessments())
    assert [r["thesis_id"] for r in records] == ["a", "b"]


def test_check_sha_rejects_traversal_and_non_hex():
    for bad in ("../etc/passwd", "g" * 64, "abc", "ab/cd", 123):
        with pytest.raises(ValueError):
            _check_sha(bad)
    good = "a" * 64
    assert _check_sha(good) == good


def test_malformed_catalog_line_raises_located_error(tmp_path):
    reg = Registry(str(tmp_path), fsync=False)
    reg.register(_thesis())
    with open(tmp_path / "theses.jsonl", "a", encoding="utf-8") as f:
        f.write("{ not valid json\n")
    with pytest.raises(ValueError, match="theses line"):
        list(reg.theses())
