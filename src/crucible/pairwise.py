"""Pairwise judging in both orders, with order disagreement reported.

A judge that compares two answers side by side often prefers whichever answer it
reads first. ``judge_pair`` asks the injected comparator twice, once with A in
the first slot and once with B there, maps each slot answer back to the
candidate it names, and returns A or B only when both orders agree. A split
comes back as ORDER_DISAGREE and a tie as TIE; neither counts as a preference.
A comparator that raises or returns anything unusable fails closed to
UNVERIFIABLE. ``pairwise_report`` turns a batch of results into the order-swap
consistency rate with a Wilson interval and the first-slot preference rate.
"""
from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

A, B, TIE = "A", "B", "TIE"
ORDER_DISAGREE = "ORDER_DISAGREE"
UNVERIFIABLE = "UNVERIFIABLE"
FIRST, SECOND = "first", "second"
SLOTS = (FIRST, SECOND, "tie")
REPORT_SCHEMA = "crucible.pairwise-report/1"

# A comparator takes (question, first, second, rubric) and returns
# {"prefer": "first" | "second" | "tie", "evidence": [...]}.
Comparator = Callable[[str, str, str, str], "Mapping[str, object]"]


def make_null_comparator() -> Comparator:
    """The default comparator: prefers nothing, so every pair stays UNVERIFIABLE."""
    def null_comparator(question: str, first: str, second: str, rubric: str) -> Mapping[str, object]:
        return {"prefer": None, "evidence": ("null comparator: no preference produced",)}
    return null_comparator


@dataclass(frozen=True, slots=True)
class PairResult:
    """One pair judged in both orders. ``ab`` had A first; ``ba`` had B first."""

    verdict: str
    ab: str | None
    ba: str | None
    order_agreement: bool | None
    evidence: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {"verdict": self.verdict, "ab": self.ab, "ba": self.ba,
                "order_agreement": self.order_agreement, "evidence": list(self.evidence)}


def slot_answer(reply: object) -> str | None:
    """The slot a comparator reply names, or None when the reply is unusable."""
    if not isinstance(reply, Mapping):
        return None
    prefer = reply.get("prefer")
    return prefer if isinstance(prefer, str) and prefer in SLOTS else None


def to_candidate(slot: str, a_first: bool) -> str:
    """Map a slot answer to the candidate it names, given which candidate sat first."""
    if slot == "tie":
        return TIE
    return (A if slot == FIRST else B) if a_first else (B if slot == FIRST else A)


def combine(ab: str | None, ba: str | None) -> PairResult:
    """Combine the two slot answers (``ab``: A first, ``ba``: B first) into one result."""
    if ab is None or ba is None:
        return PairResult(UNVERIFIABLE, ab, ba, None)
    first, second = to_candidate(ab, True), to_candidate(ba, False)
    if first != second:
        return PairResult(ORDER_DISAGREE, ab, ba, False)
    return PairResult(first, ab, ba, True)


def _ask(compare: Comparator, question: str, first: str, second: str, rubric: str):
    try:
        reply = compare(question, first, second, rubric)
    except Exception as exc:  # noqa: BLE001 - the comparator is an impure edge; failure is evidence.
        return None, (f"comparator raised: {exc}",)
    raw = reply.get("evidence", ()) if isinstance(reply, Mapping) else ()
    items: Iterable[object] = (raw,) if isinstance(raw, str) else (
        raw if isinstance(raw, (list, tuple)) else ())
    return slot_answer(reply), tuple(str(e) for e in items)


def judge_pair(compare: Comparator, question: str, a: str, b: str, rubric: str = "") -> PairResult:
    """Judge candidates ``a`` and ``b`` in both orders and combine the answers."""
    ab, ev_ab = _ask(compare, question, a, b, rubric)
    ba, ev_ba = _ask(compare, question, b, a, rubric)
    result = combine(ab, ba)
    return PairResult(result.verdict, ab, ba, result.order_agreement,
                      tuple(f"A first: {e}" for e in ev_ab) + tuple(f"B first: {e}" for e in ev_ba))


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """Wilson score interval for a proportion; None when n is zero."""
    if n <= 0:
        return None
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def pairwise_report(results: Iterable[PairResult]) -> dict:
    """Order-swap consistency, first-slot preference rate and verdict counts for a batch.

    Consistency counts pairs where both orders gave a usable answer; a pair is
    consistent when both orders name the same candidate (or both say tie).
    The first-slot rate is the share of usable slot answers that picked the
    first slot, where 0.5 means no position bias.
    """
    rows = list(results)
    usable = [r for r in rows if r.order_agreement is not None]
    agree = sum(1 for r in usable if r.order_agreement)
    slots = [s for r in usable for s in (r.ab, r.ba) if s in (FIRST, SECOND)]
    first = sum(1 for s in slots if s == FIRST)
    return {
        "schema": REPORT_SCHEMA,
        "pairs": len(rows),
        "usable_pairs": len(usable),
        "verdicts": dict(sorted(Counter(r.verdict for r in rows).items())),
        "order_consistency": agree / len(usable) if usable else None,
        "order_consistency_wilson95": wilson(agree, len(usable)),
        "first_slot_rate": first / len(slots) if slots else None,
        "first_slot_wilson95": wilson(first, len(slots)),
    }
