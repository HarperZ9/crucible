"""Decomposed claims and minority-preserving summaries, with paired mutants."""
from __future__ import annotations

import json

import pytest

from crucible import decompose
from crucible.claim import make_claim
from crucible.cli import main
from crucible.decompose import SubQuestion, make_decomposed, measure_decomposed
from crucible.dissent import dissent_survival, render_views_markdown, summarize_views
from crucible.verdict import DRIFT, MATCH, UNVERIFIABLE

QUESTIONS = [
    SubQuestion("tests", "Does the test suite pass?", "yesno", True),
    SubQuestion("latency", "p95 latency in ms", "number", 200.0, tolerance=50.0),
    SubQuestion("tier", "Which tier ships?", "choice", "beta", options=("alpha", "beta")),
]


def _dc():
    return make_decomposed(make_claim("the release is ready", "any sub-question fails"), QUESTIONS)


def check_combination(measure) -> None:
    dc = _dc()
    good = measure(dc, {"tests": True, "latency": 230.0, "tier": "beta"})
    assert good["verdict"] == MATCH and good["weakest"]["id"] == "latency"
    one_bad = measure(dc, {"tests": True, "latency": 400.0, "tier": "beta"})
    assert one_bad["verdict"] == DRIFT and one_bad["weakest"]["id"] == "latency"
    missing = measure(dc, {"tests": True, "latency": 210.0})
    assert missing["verdict"] == UNVERIFIABLE and missing["weakest"]["id"] == "tier"
    mixed = measure(dc, {"tests": False, "latency": 999.0, "tier": None})
    assert mixed["verdict"] == DRIFT and mixed["weakest"]["id"] == "latency"


def test_sub_verdicts_combine_demote_only_and_name_one_weakest():
    check_combination(measure_decomposed)


@pytest.mark.parametrize("mutant", [
    lambda statuses: max(statuses, key=lambda s: decompose._RANK[s]),       # optimistic
    lambda statuses: statuses[0] if statuses else UNVERIFIABLE,             # first only
])
def test_combination_check_catches_optimistic_merges(monkeypatch, mutant):
    monkeypatch.setattr(decompose, "combine_verdicts", mutant)
    with pytest.raises(AssertionError):
        check_combination(measure_decomposed)


def test_combination_check_catches_a_weakest_that_ignores_margin(monkeypatch):
    monkeypatch.setattr(decompose, "weakest", lambda rows: rows[0][0])
    with pytest.raises(AssertionError):
        check_combination(measure_decomposed)


def test_decomposition_is_sealed_and_validated():
    dc = _dc()
    assert dc.verify()
    tampered = decompose.DecomposedClaim(dc.claim, dc.questions[:2], dc.seal)
    assert not tampered.verify()
    with pytest.raises(ValueError):
        measure_decomposed(tampered, {})
    with pytest.raises(ValueError):
        make_decomposed(dc.claim, [SubQuestion("x", "?", "number", 1.0)])
    with pytest.raises(ValueError):
        make_decomposed(dc.claim, [SubQuestion("x", "?", "choice", "c", options=("a",))])
    assert make_claim("the release is ready", "any sub-question fails").sha256 == dc.claim.sha256


VIEWS = [{"source": f"judge{i}", "position": "ship now", "text": "tests pass"} for i in range(3)]
VIEWS += [{"source": "judge3", "position": "Delay for rollback test", "text": "no rollback path"},
          {"source": "judge4", "position": "delay for rollback  TEST", "text": ""}]


def check_summary(summarize) -> None:
    summary = summarize(VIEWS + [{"source": "judge5", "position": "licence review"}])
    assert [g["position"] for g in summary["majority"]] == ["ship now"]
    minorities = {g["position"]: g for g in summary["minorities"]}
    assert minorities["Delay for rollback test"]["count"] == 2
    assert minorities["Delay for rollback test"]["sources"] == ["judge3", "judge4"]
    assert "licence review" in minorities
    assert summary["views"] == 6


def test_summary_keeps_every_minority_with_sources():
    check_summary(summarize_views)


def test_summary_check_catches_a_majority_only_summary():
    def majority_only(views):
        full = summarize_views(views)
        return {**full, "minorities": full["minorities"][:1]}
    with pytest.raises(AssertionError):
        check_summary(majority_only)


def test_survival_scores_structured_and_text_summaries():
    summary = summarize_views(VIEWS)
    assert dissent_survival(["delay for rollback test"], summary)["rate"] == 1.0
    text = "Most judges say ship now; tests pass."
    lost = dissent_survival(["delay for rollback test"], text)
    assert lost["rate"] == 0.0 and lost["lost"] == ["delay for rollback test"]
    assert dissent_survival(["rollback"], text + " One asks to delay for a rollback test.")["rate"] == 1.0
    tied = summarize_views(VIEWS[:1] + VIEWS[3:4])
    assert len(tied["majority"]) == 2 and tied["minorities"] == []
    assert "Minority (2 of 5)" in "\n".join(render_views_markdown(summary))


def test_cli_faces(tmp_path, capsys):
    pairs = tmp_path / "pairs.json"
    pairs.write_text(json.dumps({"pairs": [{"id": 1, "ab": "first", "ba": "second"},
                                           {"id": 2, "ab": "first", "ba": "first"}]}))
    assert main(["pairwise", str(pairs), "--json"]) == 0
    rep = json.loads(capsys.readouterr().out)["report"]
    assert rep["order_consistency"] == 0.5 and rep["verdicts"] == {"A": 1, "ORDER_DISAGREE": 1}
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"claim": "ready", "falsification": "a check fails",
                                "questions": [q.body() for q in QUESTIONS],
                                "answers": {"tests": True, "latency": 400, "tier": "beta"}}))
    assert main(["decompose", str(spec), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["weakest"]["id"] == "latency"
    views = tmp_path / "views.json"
    views.write_text(json.dumps({"views": VIEWS, "planted": ["delay for rollback test"]}))
    assert main(["views", str(views), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["survival"]["rate"] == 1.0
