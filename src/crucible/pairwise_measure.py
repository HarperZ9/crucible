"""PairwiseMeasure: "candidate A beats candidate B" measured on the Measure seam.

Both orders must prefer A for a deviation of 0.0, and both must prefer B for
1.0. A split between the orders, a tie, or an unusable comparator reply leaves
the deviation None, so the verdict is UNVERIFIABLE. The Measurement carries a
``judge:pairwise`` recheck descriptor that seals the rubric, both candidates
and both slot answers, so a replay can show whether the same comparator still
answers the same way.
"""
from __future__ import annotations

import time
from collections.abc import Callable, Mapping

from crucible.artifact_store import artifact_sha
from crucible.claim import Claim
from crucible.judge import rubric_sha
from crucible.pairwise import A, B, Comparator, judge_pair
from crucible.verdict import Measurement

METHOD = "judge:pairwise"


class PairwiseMeasure:
    """Measure claims of the form "A beats B" with an injected comparator.

    ``pairs`` maps a claim id or exact claim text to ``(question, a, b)``.
    """

    name = "pairwise"

    def __init__(self, compare: Comparator, rubric: str,
                 pairs: Mapping[str, tuple[str, str, str]], *,
                 clock: Callable[[], float] = time.time) -> None:
        self._compare, self._rubric, self._pairs, self._clock = compare, rubric, dict(pairs), clock

    def measure(self, claim: Claim) -> Measurement:
        pair = self._pairs.get(claim.id) or self._pairs.get(claim.text)
        if pair is None:
            return self._row(claim, None, ("no candidate pair for claim",), None)
        question, a, b = pair
        result = judge_pair(self._compare, question, a, b, self._rubric)
        deviation = {A: 0.0, B: 1.0}.get(result.verdict)
        recheck = {"oracle": METHOD, "comparator": getattr(self._compare, "__name__", "comparator"),
                   "rubric_sha": rubric_sha(self._rubric), "a_sha": artifact_sha(a),
                   "b_sha": artifact_sha(b), "ab": result.ab, "ba": result.ba}
        evidence = (f"pairwise verdict {result.verdict}",
                    f"order agreement {result.order_agreement}") + result.evidence
        return self._row(claim, deviation, evidence, recheck)

    def _row(self, claim: Claim, deviation: float | None, evidence: tuple[str, ...],
             recheck: Mapping[str, object] | None) -> Measurement:
        return Measurement(claim.id, claim.sha256, deviation, claim.tolerance or 0.5, METHOD,
                           float(self._clock()), evidence, recheck)
