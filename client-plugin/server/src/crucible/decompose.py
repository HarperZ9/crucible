"""Decomposed claims: a claim split into typed sub-questions, each measured on its own.

A broad claim often mixes several judgments. Splitting it into small typed
questions (yes or no, a number, a choice among options) lets each one be
answered and checked separately, and lets the report name the single
sub-question that held least well. Each sub-question becomes its own sealed
sub-claim and is decided by ``verdict_for``, so no model sits in the verdict.
The parent's verdict combines its sub-verdicts demote-only: any DRIFT gives
DRIFT, otherwise any UNVERIFIABLE gives UNVERIFIABLE, otherwise MATCH.

The decomposition is sealed beside the parent claim, so the parent claim's own
hash is unchanged and legacy registries keep verifying.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass

from crucible.claim import Claim, make_claim
from crucible.verdict import (
    DRIFT,
    MATCH,
    UNVERIFIABLE,
    Measurement,
    Verdict,
    verdict_for,
)

KINDS = ("yesno", "number", "choice")
METHOD = "decompose:typed"
_RANK = {DRIFT: 0, UNVERIFIABLE: 1, MATCH: 2}


@dataclass(frozen=True, slots=True)
class SubQuestion:
    """One typed question. ``expected`` is the answer that makes the parent hold.

    yesno: expected is True or False. choice: expected is one of ``options``.
    number: expected is a number and ``tolerance`` the allowed absolute gap.
    """

    id: str
    text: str
    kind: str
    expected: object
    tolerance: float | None = None
    options: tuple[str, ...] = ()

    def body(self) -> dict:
        return {"id": self.id, "text": self.text, "kind": self.kind, "expected": self.expected,
                "tolerance": self.tolerance, "options": list(self.options)}


def _check(sq: SubQuestion) -> None:
    if sq.kind not in KINDS:
        raise ValueError(f"sub-question {sq.id!r}: kind must be one of {KINDS}")
    if sq.kind == "yesno" and not isinstance(sq.expected, bool):
        raise ValueError(f"sub-question {sq.id!r}: a yesno answer must be true or false")
    if sq.kind == "choice" and sq.expected not in sq.options:
        raise ValueError(f"sub-question {sq.id!r}: expected must be one of its options")
    if sq.kind == "number":
        ok = isinstance(sq.expected, (int, float)) and not isinstance(sq.expected, bool)
        tol = sq.tolerance
        if not ok or tol is None or not math.isfinite(tol) or tol <= 0:
            raise ValueError(f"sub-question {sq.id!r}: a number needs a numeric expected "
                             "answer and a positive tolerance")


@dataclass(frozen=True, slots=True)
class DecomposedClaim:
    claim: Claim
    questions: tuple[SubQuestion, ...]
    seal: str

    def verify(self) -> bool:
        return self.claim.verify() and decomposition_seal(self.claim, self.questions) == self.seal


def decomposition_seal(claim: Claim, questions: tuple[SubQuestion, ...]) -> str:
    """SHA-256 over the parent claim's hash and the sub-questions, in order."""
    payload = {"claim": claim.sha256, "questions": [q.body() for q in questions]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def make_decomposed(claim: Claim, questions: list[SubQuestion] | tuple[SubQuestion, ...]) -> DecomposedClaim:
    qs = tuple(questions)
    if not qs:
        raise ValueError("a decomposed claim needs at least one sub-question")
    ids = [q.id for q in qs]
    if len(set(ids)) != len(ids):
        raise ValueError("sub-question ids must be unique")
    for q in qs:
        _check(q)
    return DecomposedClaim(claim, qs, decomposition_seal(claim, qs))


def sub_claim(parent: Claim, sq: SubQuestion) -> Claim:
    """The sealed sub-claim a sub-question stands for."""
    tol = sq.tolerance if sq.kind == "number" else 0.5
    return make_claim(f"{parent.text} :: {sq.text}",
                      f"the answer differs from {json.dumps(sq.expected)}",
                      tolerance=tol, id=f"{parent.id}:{sq.id}")


def deviation(sq: SubQuestion, answer: object) -> float | None:
    """Distance between an observed answer and the expected one; None if unusable."""
    if answer is None:
        return None
    if sq.kind == "yesno":
        return None if not isinstance(answer, bool) else float(answer != sq.expected)
    if sq.kind == "choice":
        return None if answer not in sq.options else float(answer != sq.expected)
    if isinstance(answer, bool) or not isinstance(answer, (int, float)) or not math.isfinite(answer):
        return None
    return abs(float(answer) - float(sq.expected))  # type: ignore[arg-type]


def combine_verdicts(statuses: list[str]) -> str:
    """Demote-only: the worst status wins (DRIFT, then UNVERIFIABLE, then MATCH)."""
    if not statuses:
        return UNVERIFIABLE
    return min(statuses, key=lambda s: _RANK[s])


def weakest(rows: list[tuple[SubQuestion, Verdict]]) -> SubQuestion:
    """The one sub-question that held least well: worst status, then lowest margin, then order."""
    def key(item):
        index, (sq, v) = item
        margin = v.margin if v.margin is not None else -math.inf
        return (_RANK[v.status], margin, index)
    return min(enumerate(rows), key=key)[1][0]


def measure_decomposed(dc: DecomposedClaim, answers: Mapping[str, object], *,
                       measured_at: float = 0.0) -> dict:
    """Verdict per sub-question, the combined verdict, and the named weakest sub-question."""
    if not dc.verify():
        raise ValueError("decomposition seal does not verify")
    rows = []
    for sq in dc.questions:
        sc = sub_claim(dc.claim, sq)
        m = Measurement(sc.id, sc.sha256, deviation(sq, answers.get(sq.id)), sc.tolerance or 0.5,
                        METHOD, measured_at, (f"answer={json.dumps(answers.get(sq.id))}",))
        rows.append((sq, verdict_for(sc, m)))
    weak = weakest(rows)
    return {
        "claim_id": dc.claim.id, "seal": dc.seal,
        "verdict": combine_verdicts([v.status for _, v in rows]),
        "weakest": {"id": weak.id, "text": weak.text},
        "sub_verdicts": [{"id": sq.id, "status": v.status, "margin": v.margin,
                          "grounds": v.grounds} for sq, v in rows],
    }


def from_spec(spec: Mapping[str, object]) -> tuple[DecomposedClaim, Mapping[str, object]]:
    """Build a decomposed claim and its answers from a JSON spec."""
    claim = make_claim(str(spec["claim"]), str(spec.get("falsification", "")))
    raw_questions = spec["questions"]
    if not isinstance(raw_questions, list):
        raise ValueError("questions must be a list")
    questions = [SubQuestion(str(q["id"]), str(q["text"]), str(q["kind"]), q.get("expected"),
                             q.get("tolerance"), tuple(q.get("options", ())))
                 for q in raw_questions]
    answers = spec.get("answers") or {}
    if not isinstance(answers, Mapping):
        raise ValueError("answers must map sub-question ids to answers")
    return make_decomposed(claim, questions), dict(answers)
