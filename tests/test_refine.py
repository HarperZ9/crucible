from __future__ import annotations

from crucible import margin as exported_margin
from crucible.claim import make_claim
from crucible.measure import MetricSpec, TableMeasure
from crucible.refine import GradedCriterion, cohesion, grade, margin, refine_thesis
from crucible.thesis import make_thesis
from crucible.verdict import DRIFT, MATCH, UNVERIFIABLE


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


def test_refine_never_reports_correct_when_a_sealed_tolerance_is_widened():
    """A claim that sealed its tolerance is decided by that number and no other. If the measurement
    oracle supplies a wider tolerance, verdict_for refuses it (UNVERIFIABLE); the refine grader must
    agree and never report the thesis 'correct' by grading against the widened tolerance. Otherwise
    the status and the verdicts disagree and a consumer keyed on the status accepts a thesis whose
    verdict was rescued by widening the tolerance after the seal."""
    claim = make_claim("position error stays small", "position error grows", tolerance=0.05)
    thesis = make_thesis("sealed loop", (claim,), clock=lambda: 1.0)
    # spec tolerance 0.10 is WIDER than the sealed 0.05; deviation 0.08 passes the grader under 0.10
    # (margin 1 - 0.08/0.10 = 0.2) but is UNVERIFIABLE under the seal.
    specs = {claim.id: MetricSpec(predicted=1.0, tolerance=0.10, observe="position")}

    def propose(_state):
        return TableMeasure(specs, {"position": 1.08}, clock=lambda: 10.0)

    def adjust(_reflection, state):
        return state

    report = refine_thesis(
        thesis,
        propose,
        adjust,
        target_margin=0.1,
        cohesion_bar=0.1,
        max_iter=1,
    )

    assert report.status == "short"
    assert [v.status for v in report.verdicts] == [UNVERIFIABLE]
