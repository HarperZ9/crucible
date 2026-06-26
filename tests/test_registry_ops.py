from __future__ import annotations

import json
import os

from crucible.assess import assess
from crucible.claim import make_claim
from crucible.registry import Registry
from crucible.registry_ops import prune_objects, registry_stats, search_theses
from crucible.thesis import FENCED, make_thesis
from crucible.verdict import DRIFT, MATCH, Measurement

CLOCK = lambda: 1000.0  # noqa: E731


def _seed_registry(tmp_path):
    reg = Registry(str(tmp_path), fsync=False)
    engine = make_thesis("Engine fitness", [
        make_claim("latency stays under budget", "latency exceeds budget"),
        make_claim("precision stays above floor", "precision falls below floor"),
    ], clock=CLOCK)
    finance = make_thesis("Capital flow", [
        make_claim("capital raise is gated", "unapproved export is possible"),
    ], clock=CLOCK, disposition=FENCED)
    assess(engine, [
        Measurement(engine.claims[0].id, engine.claims[0].sha256, 0.0, 0.1, "bench", 0.0),
        Measurement(engine.claims[1].id, engine.claims[1].sha256, 1.0, 0.1, "bench", 0.0),
    ], registry=reg, clock=CLOCK)
    assess(finance, registry=reg, clock=CLOCK)
    return reg, engine, finance


def test_registry_stats_counts_theses_claims_dispositions_and_latest_verdicts(tmp_path):
    reg, _engine, _finance = _seed_registry(tmp_path)

    stats = registry_stats(reg)

    assert stats["theses"] == 2
    assert stats["claims"] == 3
    assert stats["unique_claims"] == 3
    assert stats["assessments"] == 2
    assert stats["dispositions"] == {"fenced": 1, "publishable": 1}
    assert stats["verdicts"][MATCH] == 1
    assert stats["verdicts"][DRIFT] == 1
    assert stats["verdicts"]["UNVERIFIABLE"] == 1


def test_search_theses_filters_by_scope_status_and_latest_verdict(tmp_path):
    reg, engine, finance = _seed_registry(tmp_path)

    assert [r["id"] for r in search_theses(reg, scope="latency")] == [engine.id]
    assert [r["id"] for r in search_theses(reg, status="fenced")] == [finance.id]
    assert [r["id"] for r in search_theses(reg, verdict=DRIFT)] == [engine.id]


def test_registry_stats_and_search_exclude_tampered_latest_assessment(tmp_path):
    reg, engine, _finance = _seed_registry(tmp_path)
    path = tmp_path / "assessments.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[0]["verdicts"][0]["margin"] = -999.0
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    stats = registry_stats(reg)
    found = search_theses(reg, verdict=DRIFT)

    assert stats["latest_assessments"] == 1
    assert stats["invalid_latest_assessments"] == 1
    assert stats["verdicts"][MATCH] == 0
    assert stats["verdicts"][DRIFT] == 0
    assert [r["id"] for r in found] == []
    assert [r["id"] for r in search_theses(reg, scope="latency")] == [engine.id]


def test_registry_stats_and_search_fall_back_to_latest_verified_assessment(tmp_path):
    reg, engine, _finance = _seed_registry(tmp_path)
    assess(engine, [
        Measurement(engine.claims[0].id, engine.claims[0].sha256, 0.0, 0.1, "bench", 0.0),
        Measurement(engine.claims[1].id, engine.claims[1].sha256, 0.0, 0.1, "bench", 0.0),
    ], registry=reg, clock=CLOCK)
    path = tmp_path / "assessments.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[-1]["verdicts"][0]["margin"] = -999.0
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    stats = registry_stats(reg)
    found = search_theses(reg, verdict=DRIFT)

    assert stats["latest_assessments"] == 2
    assert stats["invalid_latest_assessments"] == 1
    assert stats["verdicts"][MATCH] == 1
    assert stats["verdicts"][DRIFT] == 1
    assert [r["id"] for r in found] == [engine.id]


def test_prune_objects_dry_runs_then_deletes_orphaned_bodies(tmp_path):
    reg, _engine, _finance = _seed_registry(tmp_path)
    orphan = "f" * 64
    orphan_dir = tmp_path / "objects" / orphan[:2]
    orphan_dir.mkdir(parents=True, exist_ok=True)
    orphan_path = orphan_dir / orphan[2:]
    orphan_path.write_text("orphan body", encoding="utf-8")

    dry = prune_objects(reg)

    assert dry["dry_run"] is True
    assert dry["orphans"] == [orphan]
    assert os.path.exists(orphan_path)

    applied = prune_objects(reg, apply=True)

    assert applied["dry_run"] is False
    assert applied["deleted"] == [orphan]
    assert not os.path.exists(orphan_path)


def test_prune_objects_refuses_escaped_objects_root(tmp_path):
    reg, _engine, _finance = _seed_registry(tmp_path / "reg")
    outside = tmp_path / "outside"
    outside.mkdir()
    orphan = "f" * 64
    shard = outside / orphan[:2]
    shard.mkdir()
    victim = shard / orphan[2:]
    victim.write_text("outside body", encoding="utf-8")
    reg._objects = str(outside)  # noqa: SLF001 - simulate a junctioned/escaped objects root.

    try:
        assert prune_objects(reg, apply=True)["deleted"] == []
    except ValueError:
        pass

    assert victim.exists()
