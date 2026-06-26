from __future__ import annotations

from crucible import margin as exported_margin
from crucible.claim import make_claim
from crucible.measure import MetricSpec, TableMeasure
from crucible.refine import GradedCriterion, cohesion, grade, margin, refine_thesis
from crucible.thesis import make_thesis
from crucible.verdict import DRIFT, MATCH


def _thesis():
    claims = (
        make_claim("position error stays small", "position error grows"),
        make_claim("energy deviation stays small", "energy deviation grows"),
    )
    return make_thesis("discovery loop", claims, clock=lambda: 1.0)


def _specs(thesis):
    c1, c2 = thesis.claims
    return {
        c1.id: MetricSpec(predicted=1.0, tolerance=0.5, observe="position"),
        c2.id: MetricSpec(predicted=1.0, tolerance=0.5, observe="energy"),
    }


def test_cohesion_requires_every_axis_to_hold():
    assert cohesion([1.0, 0.5]) > 0
    assert cohesion([1.0, 0.0]) == 0.0
    assert cohesion([1.0, float("-inf")]) == 0.0


def test_margin_is_public_and_fails_closed():
    assert margin(0.0, 0.5) == 1.0
    assert margin(0.25, 0.5) == 0.5
    assert margin(1.0, 0.5) == -1.0
    assert margin(None, 0.5) == float("-inf")
    assert margin(0.0, 0.0) == float("-inf")
    assert exported_margin is margin


def test_grade_fails_closed_when_deviation_is_not_numeric():
    g = GradedCriterion("shape", "objective", lambda _form: "unknown", 1.0)
    result = grade(g, object())
    assert result.ok is False
    assert result.margin == float("-inf")


def test_refine_thesis_reaches_correct_after_better_measurement_round():
    thesis = _thesis()
    specs = _specs(thesis)
    rounds = (
        {"position": 1.0, "energy": 4.0},
        {"position": 1.0, "energy": 1.0},
    )

    def propose(state):
        idx = 0 if state is None else int(state)
        return TableMeasure(specs, rounds[idx], clock=lambda: 10.0 + idx)

    def adjust(_reflection, state):
        return (0 if state is None else int(state)) + 1

    report = refine_thesis(
        thesis,
        propose,
        adjust,
        target_margin=0.25,
        cohesion_bar=0.5,
        max_iter=len(rounds),
    )

    assert report.status == "correct"
    assert report.iterations == 2
    assert report.weakest_claim is None
    assert list(report.cohesions) == [0.0, 1.0]
    assert [v.status for v in report.verdicts] == [MATCH, MATCH]


def test_refine_thesis_reports_weakest_claim_when_budget_is_spent():
    thesis = _thesis()
    c1, c2 = thesis.claims
    specs = _specs(thesis)
    rounds = (
        {"position": 1.0, "energy": 4.0},
        {"position": 1.0, "energy": 3.0},
    )

    def propose(state):
        idx = 0 if state is None else int(state)
        return TableMeasure(specs, rounds[idx], clock=lambda: 20.0 + idx)

    def adjust(_reflection, state):
        return (0 if state is None else int(state)) + 1

    report = refine_thesis(
        thesis,
        propose,
        adjust,
        target_margin=0.25,
        cohesion_bar=0.5,
        max_iter=len(rounds),
    )

    assert report.status == "short"
    assert report.weakest_claim == c2.id
    assert [v.status for v in report.verdicts] == [MATCH, DRIFT]
    assert report.verdicts[0].claim_id == c1.id
