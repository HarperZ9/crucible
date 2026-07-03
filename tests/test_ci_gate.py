from __future__ import annotations

import pytest

from crucible.ci_gate import (
    BASELINE_KIND,
    Cell,
    Snapshot,
    cells_from_latest,
    gate,
    make_snapshot,
    snapshot_seal,
)
from crucible.ci_report import render_gate_markdown
from crucible.verdict import DRIFT, MATCH, UNVERIFIABLE


def _cell(claim_id: str, status: str, seal: str = "seal-a", thesis_id: str = "t1") -> Cell:
    return Cell(thesis_id, claim_id, status, seal)


def test_no_regression_passes_and_holds():
    base = make_snapshot([_cell("c1", MATCH), _cell("c2", MATCH)])
    curr = make_snapshot([_cell("c1", MATCH, seal="seal-b"), _cell("c2", MATCH, seal="seal-b")])
    report = gate(base, curr)
    assert report.passed is True
    assert report.summary["held"] == 2
    assert report.summary["regressed"] == 0
    assert report.regressions == ()


def test_match_to_drift_is_a_regression():
    base = make_snapshot([_cell("c1", MATCH), _cell("c2", MATCH)])
    curr = make_snapshot([_cell("c1", MATCH, seal="seal-b"), _cell("c2", DRIFT, seal="seal-b")])
    report = gate(base, curr)
    assert report.passed is False
    assert len(report.regressions) == 1
    row = report.regressions[0]
    assert row.claim_id == "c2"
    assert row.baseline_status == MATCH
    assert row.current_status == DRIFT
    assert row.movement == "regressed"


def test_new_unverifiable_is_a_regression():
    base = make_snapshot([_cell("c1", MATCH)])
    curr = make_snapshot([_cell("c1", UNVERIFIABLE, seal="seal-b")])
    report = gate(base, curr)
    assert report.passed is False
    assert report.regressions[0].movement == "regressed"
    assert report.regressions[0].current_status == UNVERIFIABLE


def test_drift_to_unverifiable_is_a_regression():
    base = make_snapshot([_cell("c1", DRIFT)])
    curr = make_snapshot([_cell("c1", UNVERIFIABLE, seal="seal-b")])
    report = gate(base, curr)
    assert report.passed is False
    assert report.regressions[0].movement == "regressed"


def test_dropped_baselined_claim_is_a_regression():
    base = make_snapshot([_cell("c1", MATCH), _cell("c2", MATCH)])
    curr = make_snapshot([_cell("c1", MATCH, seal="seal-b")])
    report = gate(base, curr)
    assert report.passed is False
    dropped = report.regressions[0]
    assert dropped.claim_id == "c2"
    assert dropped.movement == "dropped"
    assert dropped.current_status is None


def test_improvement_and_new_claim_do_not_fail_the_gate():
    base = make_snapshot([_cell("c1", DRIFT)])
    curr = make_snapshot([_cell("c1", MATCH, seal="seal-b"), _cell("c2", MATCH, seal="seal-b")])
    report = gate(base, curr)
    assert report.passed is True
    movements = {r.claim_id: r.movement for r in report.rows}
    assert movements["c1"] == "improved"
    assert movements["c2"] == "new"


def test_markdown_summary_is_deterministic():
    base = make_snapshot([_cell("c1", MATCH), _cell("c2", MATCH)])
    curr = make_snapshot([_cell("c1", MATCH, seal="seal-b"), _cell("c2", DRIFT, seal="seal-b")])
    report = gate(base, curr)
    first = render_gate_markdown(report)
    second = render_gate_markdown(gate(base, curr))
    assert first == second
    assert "FAIL: 1 regression(s)" in first
    assert "c2" in first
    # No em-dash or en-dash characters leak into the rendered artifact.
    assert "—" not in first and "–" not in first


def test_markdown_pass_summary_states_no_regressions():
    base = make_snapshot([_cell("c1", MATCH)])
    curr = make_snapshot([_cell("c1", MATCH, seal="seal-b")])
    md = render_gate_markdown(gate(base, curr))
    assert "PASS: no regressions" in md
    assert "### What regressed" not in md


def test_snapshot_seal_is_order_independent():
    a = snapshot_seal([_cell("c1", MATCH), _cell("c2", DRIFT)])
    b = snapshot_seal([_cell("c2", DRIFT), _cell("c1", MATCH)])
    assert a == b


def test_snapshot_roundtrips_through_dict():
    snap = make_snapshot([_cell("c1", MATCH), _cell("c2", DRIFT)])
    restored = Snapshot.from_dict(snap.to_dict())
    assert restored.seal == snap.seal
    assert restored.cells == snap.cells


def test_tampered_baseline_is_rejected_on_load():
    snap = make_snapshot([_cell("c1", MATCH)])
    payload = snap.to_dict()
    # Downgrade the recorded status without recomputing the seal: a hand-edited baseline.
    payload["cells"][0]["status"] = DRIFT
    with pytest.raises(ValueError, match="seal does not match"):
        Snapshot.from_dict(payload)


def test_wrong_kind_is_rejected_on_load():
    snap = make_snapshot([_cell("c1", MATCH)])
    payload = snap.to_dict()
    payload["kind"] = "something-else"
    with pytest.raises(ValueError, match="not a .* snapshot"):
        Snapshot.from_dict(payload)


def test_baseline_kind_is_stable():
    assert BASELINE_KIND == "crucible.ci-baseline/v1"


def test_cells_from_latest_reads_verdict_rows_with_packet_seal():
    latest = {
        "t1": {
            "seal": "assessment-seal-1",
            "verdicts": [
                {"claim_id": "c1", "status": MATCH},
                {"claim_id": "c2", "status": DRIFT},
            ],
        }
    }
    cells = cells_from_latest(latest)
    assert len(cells) == 2
    by_id = {c.claim_id: c for c in cells}
    assert by_id["c1"].status == MATCH
    assert by_id["c1"].assessment_seal == "assessment-seal-1"
    assert by_id["c2"].status == DRIFT


def test_cells_from_latest_skips_unknown_status_rather_than_guessing():
    latest = {
        "t1": {
            "seal": "s",
            "verdicts": [
                {"claim_id": "c1", "status": "BOGUS"},
                {"claim_id": "", "status": MATCH},
                {"status": MATCH},
                {"claim_id": "c4", "status": MATCH},
            ],
        }
    }
    cells = cells_from_latest(latest)
    assert [c.claim_id for c in cells] == ["c4"]
