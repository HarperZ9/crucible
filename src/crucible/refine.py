"""refine: the reconcile, deepened into a self-improving, refine-until-correct primitive.

This module is natively integrated from the coherence-membrane project (the original `refine`
primitive, the reconcile deepened), adapted into crucible so the discovery loop reuses the proven
shape rather than re-deriving it. It is integrated, not taken as a third-party dependency, so
crucible keeps standing alone with zero external dependencies. The lower half is the generic primitive
(graded criteria, harmonic-mean cohesion, reflect-the-weakest, refine-until-correct); the upper half,
below the separator, is the crucible layer that points the loop at a thesis and a measurement oracle.

The reconcile judges an artifact once (perceive, criterion, certificate). refine generalizes it: judge
against GRADED criteria (each yielding a margin, labelled objective or subjective), measure their
COHESION (the harmonic mean of margins, high only when every axis is healthy AND balanced), and if the
candidate is not CORRECT (all margins past a positive target AND cohesive AND any hard guard holds),
REFLECT on the weakest axis and re-iterate, until correct or until an honest budget is spent (then it
says which axis fell short, never a false "correct"). Fail-closed throughout: a deviation, generate,
or adjust that raises (or a non-numeric deviation) degrades to an honest outcome, never a crash and
never a false "correct". Stdlib only.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Callable

from crucible.measure import Measure, measure_thesis
from crucible.thesis import Thesis
from crucible.verdict import Verdict, verdict_for


@dataclass(frozen=True)
class GradedCriterion:
    """A named, kind-labelled judge that yields a MARGIN, not a verdict.
    deviation(form) returns a float >= 0 (0 is the ideal); tolerance > 0 is the failing threshold."""
    name: str
    kind: str            # "objective" | "subjective"
    deviation: Callable[[Any], float]
    tolerance: float

    def __post_init__(self) -> None:
        if self.kind not in ("objective", "subjective"):
            raise ValueError(f"kind must be objective|subjective, got {self.kind!r}")
        if (not isinstance(self.tolerance, (int, float)) or isinstance(self.tolerance, bool)
                or not math.isfinite(self.tolerance) or self.tolerance <= 0):
            raise ValueError(f"tolerance must be a finite positive number, got {self.tolerance!r}")


@dataclass(frozen=True)
class Grade:
    name: str
    kind: str
    deviation: float
    tolerance: float
    margin: float
    ok: bool


def margin(deviation: float | None, tolerance: float) -> float:
    """Normalize deviation against tolerance. Untrusted inputs fail closed to ``-inf``."""
    if (deviation is None or isinstance(deviation, bool) or not isinstance(deviation, (int, float))
            or isinstance(tolerance, bool) or not isinstance(tolerance, (int, float))):
        return float("-inf")
    dev = float(deviation)
    tol = float(tolerance)
    if not math.isfinite(dev) or not math.isfinite(tol) or dev < 0 or tol <= 0:
        return float("-inf")
    return (tol - dev) / tol


def grade(criterion: GradedCriterion, form) -> Grade:
    """Measure one criterion. A deviation that raises, is non-numeric (incl. bool), non-finite, or
    negative becomes margin -inf, ok False (fail-closed: 'cannot trust the measure' is never 'within
    tolerance'; a buggy grader returning a falsy value must NOT read as perfect)."""
    try:
        raw = criterion.deviation(form)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise TypeError(f"deviation must be a real number, got {type(raw).__name__}")
        d = float(raw)
    except Exception:
        d = float("inf")
    m = margin(d, criterion.tolerance)
    return Grade(criterion.name, criterion.kind, d, criterion.tolerance, m, m >= 0.0)


def cohesion(margins) -> float:
    """The coordination measure: 0.0 if there are no margins or ANY margin <= 0 / non-finite (a
    failing or unmeasurable axis); else the HARMONIC MEAN of the margins. High only when every axis is
    healthy AND balanced, so one weak axis tanks it (a lopsided candidate that bare-passes each axis is
    still not cohesive). Bounded in (0, 1] when defined (margins <= 1)."""
    ms = list(margins)
    if not ms or any((not math.isfinite(m)) or m <= 0.0 for m in ms):
        return 0.0
    return len(ms) / sum(1.0 / m for m in ms)


@dataclass(frozen=True)
class Reflection:
    weakest: str
    kind: str
    margin: float
    shortfall: float          # target_margin - weakest.margin (how far from comfortable)
    margins: tuple            # ((name, margin), ...)
    guard_ok: bool


def reflect(grades, target_margin: float, guard_ok: bool = True) -> Reflection:
    """Grounded self-critique: name the weakest axis and its shortfall from the comfort target."""
    worst = min(grades, key=lambda g: g.margin)
    return Reflection(worst.name, worst.kind, worst.margin, target_margin - worst.margin,
                      tuple((g.name, g.margin) for g in grades), guard_ok)


def is_correct(grades, coh: float, guard_ok: bool, *, target_margin: float, cohesion_bar: float) -> bool:
    """CORRECT, not good-enough: every axis comfortably inside (>= target_margin > 0 in real use), the
    axes cohesive (cohesion >= bar), AND the hard guard holds. Every clause is necessary."""
    return (guard_ok
            and all(g.margin >= target_margin for g in grades)
            and coh >= cohesion_bar)


@dataclass(frozen=True)
class RefineStep:
    iteration: int
    grades: tuple
    cohesion: float
    correct: bool
    guard_ok: bool
    reflection: Reflection


@dataclass(frozen=True)
class RefineOutcome:
    candidate: Any
    status: str               # "correct" | "short"
    trajectory: tuple
    short_axis: str | None    # the weakest axis, or a "<callback>-failed: ..." reason, when "short"


def _validate_refine_inputs(graders, target_margin: float, cohesion_bar: float, max_iter: int) -> None:
    if not graders:
        raise ValueError("refine requires at least one grader")
    if max_iter is None or max_iter < 1:
        raise ValueError("refine requires max_iter >= 1")
    # A negative target_margin or cohesion_bar would let a FAILING axis (margin < 0) read as
    # "correct"; validate them, closing that false-correct escape. >= 0 keeps the documented
    # degenerate-to-reconcile mode (target=0, bar=0).
    for label, val in (("target_margin", target_margin), ("cohesion_bar", cohesion_bar)):
        if (not isinstance(val, (int, float)) or isinstance(val, bool)
                or not math.isfinite(val) or val < 0):
            raise ValueError(f"refine requires {label} >= 0 (finite), got {val!r}")


def refine(generate, graders, adjust, *, guard=None, target_margin: float, cohesion_bar: float,
           max_iter: int, perceive=lambda c: c) -> RefineOutcome:
    """Refine until CORRECT, or until an honest budget is spent.

    generate(state) returns a candidate; perceive(candidate) returns a form; each grader is graded;
    cohesion and correctness are computed; reflect on the weakest axis; adjust(reflection, state)
    steers the next iteration. NEVER returns "correct" unless is_correct holds. On budget exhaustion it
    returns the best guard-passing candidate (highest cohesion) with status "short" plus the weakest
    axis. A generate/adjust callback that RAISES degrades to an honest "short" (never a crash).
    """
    _validate_refine_inputs(graders, target_margin, cohesion_bar, max_iter)
    state = None
    trajectory: list = []
    best = None            # (RefineStep, candidate) with the highest cohesion among guard-passing
    last_candidate = None
    last_refl = None
    for i in range(max_iter):
        try:
            candidate = generate(state)
        except Exception as exc:                          # fail-closed: a broken generator, honest short
            return RefineOutcome(best[1] if best is not None else last_candidate, "short",
                                 tuple(trajectory), f"generate-failed: {exc!r}")
        last_candidate = candidate
        form = perceive(candidate)
        grades = tuple(grade(g, form) for g in graders)
        coh = cohesion([g.margin for g in grades])
        gok = True if guard is None else bool(guard(candidate))
        correct = is_correct(grades, coh, gok, target_margin=target_margin, cohesion_bar=cohesion_bar)
        refl = reflect(grades, target_margin, gok)
        last_refl = refl
        step = RefineStep(i, grades, coh, correct, gok, refl)
        trajectory.append(step)
        if gok and (best is None or coh > best[0].cohesion):
            best = (step, candidate)
        if correct:
            return RefineOutcome(candidate, "correct", tuple(trajectory), None)
        try:
            state = adjust(refl, state)
        except Exception as exc:                          # fail-closed: a broken steer, honest short
            return RefineOutcome(best[1] if best is not None else candidate, "short",
                                 tuple(trajectory), f"adjust-failed: {exc!r}")
    out_candidate = best[1] if best is not None else last_candidate
    short_axis = (best[0].reflection.weakest if best is not None
                  else (last_refl.weakest if last_refl is not None else None))
    return RefineOutcome(out_candidate, "short", tuple(trajectory), short_axis)


# --- crucible layer: point the refine loop at a thesis and a measurement oracle ---------------------
#
# A claim's grader reads its own measurement from the candidate and normalizes the deviation by the
# claim's tolerance (so the grader's tolerance is 1.0 and its margin equals verdict_for's margin: an
# unmeasurable claim becomes margin -inf, fail-closed). The candidate is the list of Measurements the
# oracle produced for the thesis under the current state. So refining the state (a substrate, a
# conjecture configuration) drives the thesis toward cohesive verification, or names the weakest claim.


@dataclass(frozen=True)
class RefineReport:
    """The witnessable outcome of a thesis refinement: did it reach a cohesively verified thesis, how
    many iterations, the weakest claim if it fell short, the final per-claim verdicts, and the cohesion
    at each iteration (the trajectory)."""

    status: str               # "correct" | "short"
    iterations: int
    weakest_claim: str | None
    verdicts: tuple[Verdict, ...]
    cohesions: tuple[float, ...]


def _normalized_deviation(measurement) -> float:
    """A claim's deviation normalized by its tolerance (so a grader of tolerance 1.0 reproduces
    verdict_for's margin). Unmeasurable (deviation None, non-finite, negative, or tolerance <= 0)
    becomes +inf, which grade turns into margin -inf: an unmeasured claim never reads as healthy."""
    dev, tol = measurement.deviation, measurement.tolerance
    if (dev is None or isinstance(dev, bool) or not isinstance(dev, (int, float))
            or not math.isfinite(dev) or dev < 0 or tol <= 0):
        return float("inf")
    return dev / tol


def _claim_graders(thesis: Thesis) -> list[GradedCriterion]:
    graders: list[GradedCriterion] = []

    def deviation_for(index: int) -> Callable[[Any], float]:
        def measure_deviation(measurements: Any) -> float:
            return _normalized_deviation(measurements[index])

        return measure_deviation

    for i, claim in enumerate(thesis.claims):
        graders.append(GradedCriterion(
            name=claim.id, kind="objective", tolerance=1.0,
            deviation=deviation_for(i),
        ))
    return graders


def refine_thesis(
    thesis: Thesis,
    propose: Callable[[Any], Measure],
    adjust: Callable[[Reflection, Any], Any],
    *,
    target_margin: float,
    cohesion_bar: float,
    max_iter: int,
    clock: Callable[[], float] = time.time,
) -> RefineReport:
    """Refine a state until the thesis is cohesively verified, or report the weakest claim.

    ``propose(state)`` returns a measurement oracle for the thesis under that state; the thesis is
    measured against it and each claim's normalized deviation is graded. ``adjust(reflection, state)``
    steers the next iteration toward the weakest claim. The thesis (its claim set) is fixed across a
    refinement; amending the claims is a new refinement. Reuses the refine primitive above, so the
    fail-closed and never-false-correct guarantees carry over. The clock is injected for determinism.
    """
    graders = _claim_graders(thesis)

    def generate(state):
        return measure_thesis(propose(state), thesis)

    outcome = refine(generate, graders, adjust, target_margin=target_margin,
                     cohesion_bar=cohesion_bar, max_iter=max_iter)
    measurements = outcome.candidate or []
    verdicts = tuple(verdict_for(c, measurements[i] if i < len(measurements) else None)
                     for i, c in enumerate(thesis.claims))
    cohesions = tuple(step.cohesion for step in outcome.trajectory)
    return RefineReport(outcome.status, len(outcome.trajectory), outcome.short_axis, verdicts, cohesions)
