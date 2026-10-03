"""Pairwise judging in both orders.

Each behaviour check runs against the real code and against a named mutant;
the mutant must fail the same check.
"""
from __future__ import annotations

import pytest

from crucible import pairwise
from crucible.claim import make_claim
from crucible.pairwise import (
    ORDER_DISAGREE,
    TIE,
    UNVERIFIABLE,
    A,
    B,
    combine,
    judge_pair,
    make_null_comparator,
    pairwise_report,
    wilson,
)
from crucible.pairwise_measure import PairwiseMeasure
from crucible.verdict import DRIFT, MATCH, verdict_for


def prefers(text):
    """A comparator that always prefers whichever slot holds ``text``."""
    def compare(question, first, second, rubric):
        return {"prefer": "first" if first == text else "second", "evidence": ["looked"]}
    return compare


def first_slot(question, first, second, rubric):
    return {"prefer": "first"}


def check_judging(judge, combine_fn) -> None:
    assert judge(prefers("a"), "q", "a", "b").verdict == A
    assert judge(prefers("b"), "q", "a", "b").verdict == B
    biased = judge(first_slot, "q", "a", "b")
    assert biased.verdict == ORDER_DISAGREE and biased.order_agreement is False
    assert combine_fn("tie", "tie").verdict == TIE
    assert combine_fn("first", None).verdict == UNVERIFIABLE


def test_both_orders_must_agree():
    check_judging(judge_pair, combine)


@pytest.mark.parametrize("mutant", [
    lambda slot, a_first: (A if slot == "first" else B) if slot != "tie" else TIE,  # ignores order
    lambda slot, a_first: TIE if slot == "tie" else (B if slot == "first" else A),  # inverted
])
def test_judging_check_catches_a_broken_order_mapping(monkeypatch, mutant):
    monkeypatch.setattr(pairwise, "to_candidate", mutant)
    with pytest.raises(AssertionError):
        check_judging(judge_pair, combine)


def test_judging_check_catches_a_single_order_judge():
    def one_order(compare, question, a, b, rubric=""):
        slot = pairwise.slot_answer(compare(question, a, b, rubric))
        return combine(slot, "second" if slot == "first" else "first")
    with pytest.raises(AssertionError):
        check_judging(one_order, combine)


def test_unusable_or_raising_comparators_fail_closed():
    def boom(*_):
        raise RuntimeError("down")
    assert judge_pair(boom, "q", "a", "b").verdict == UNVERIFIABLE
    assert judge_pair(lambda *_: {"prefer": "left"}, "q", "a", "b").verdict == UNVERIFIABLE
    assert judge_pair(lambda *_: "first", "q", "a", "b").verdict == UNVERIFIABLE
    assert judge_pair(make_null_comparator(), "q", "a", "b").verdict == UNVERIFIABLE
    assert "comparator raised: down" in judge_pair(boom, "q", "a", "b").evidence[0]


def test_report_counts_consistency_and_position_bias():
    rows = [judge_pair(prefers("a"), "q", "a", "b") for _ in range(6)]
    rows += [judge_pair(first_slot, "q", "a", "b") for _ in range(4)]
    rows += [combine(None, "first")]
    rep = pairwise_report(rows)
    assert rep["pairs"] == 11 and rep["usable_pairs"] == 10
    assert rep["order_consistency"] == pytest.approx(0.6)
    assert rep["first_slot_rate"] == pytest.approx((6 + 8) / 20)
    low, high = rep["order_consistency_wilson95"]
    assert low < 0.6 < high
    assert rep["verdicts"] == {A: 6, ORDER_DISAGREE: 4, UNVERIFIABLE: 1}


def test_wilson_interval_matches_a_known_value():
    low, high = wilson(8, 10)
    assert low == pytest.approx(0.4902, abs=1e-3) and high == pytest.approx(0.9433, abs=1e-3)
    assert wilson(0, 0) is None


def test_pairwise_measure_needs_both_orders_for_a_verdict():
    claim = make_claim("answer a beats answer b", "b is preferred in both orders")
    pairs = {claim.id: ("q", "a", "b")}
    assert verdict_for(claim, PairwiseMeasure(prefers("a"), "r", pairs).measure(claim)).status == MATCH
    assert verdict_for(claim, PairwiseMeasure(prefers("b"), "r", pairs).measure(claim)).status == DRIFT
    split = PairwiseMeasure(first_slot, "rubric", pairs, clock=lambda: 1.0).measure(claim)
    assert split.deviation is None and split.recheck["ab"] == "first" and split.recheck["ba"] == "first"
    assert split.recheck["oracle"] == "judge:pairwise" and len(split.recheck["rubric_sha"]) == 16
    missing = make_claim("other claim", "x")
    assert PairwiseMeasure(prefers("a"), "r", pairs).measure(missing).deviation is None
