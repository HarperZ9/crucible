"""The measure seam: a sound oracle that produces a measurement of a claim against a substrate.

The measurement is where a claim is DECIDED. An oracle returns the deviation between what the claim
predicts and what the substrate shows, and ``verdict_for`` turns that into MATCH / DRIFT /
UNVERIFIABLE. There is no model in the verdict step; the oracle is the impure edge. The default
``NullMeasure`` stands alone and produces no measurement (UNVERIFIABLE): it invents nothing. A real
oracle (a metric over a substrate, the Telos verifier, a proof or type checker for abstract math)
plugs in through the ``Measure`` protocol without the core importing it.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Mapping, Protocol

from crucible.claim import Claim
from crucible.thesis import Thesis
from crucible.verdict import Measurement


@dataclass(frozen=True, slots=True)
class MetricSpec:
    """How to measure one claim: the value it predicts, the tolerance that separates holding from
    breaking, the substrate key to observe, and the metric (absolute or relative difference)."""

    predicted: float
    tolerance: float
    observe: str
    metric: str = "abs"  # "abs" -> |observed - predicted|; "rel" -> |observed - predicted| / |predicted|

    def __post_init__(self) -> None:
        # Validate the metric at construction (the way the refine lineage validates a criterion's kind),
        # so an unknown metric fails fast as a misconfiguration rather than silently computing abs.
        if self.metric not in ("abs", "rel"):
            raise ValueError(f"metric must be 'abs' or 'rel', got {self.metric!r}")


class Measure(Protocol):
    """The measurement seam, the sound-oracle edge. ``measure`` returns a Measurement of a claim
    against a substrate; ``verdict_for`` decides from it. The default is the deterministic
    ``NullMeasure``, so crucible stands alone; an oracle plugs in through this shape."""

    name: str

    def measure(self, claim: Claim) -> Measurement: ...


class NullMeasure:
    """The standing default: produces no measurement (deviation None -> UNVERIFIABLE). It invents no
    measurement, so it is safe to be the default; a real oracle must be wired in to decide a claim."""

    name = "null"

    def __init__(self, *, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock

    def measure(self, claim: Claim) -> Measurement:
        return Measurement(claim.id, claim.sha256, None, 1.0, self.name, float(self._clock()), ())


def _deviation(spec: MetricSpec, observed: float) -> float | None:
    """The deviation of an observation from what a claim predicts. ``metric`` is validated to be abs
    or rel at MetricSpec construction. A relative metric at a zero prediction is undefined, so it
    returns None (UNVERIFIABLE), fail-closed."""
    diff = abs(observed - spec.predicted)
    if spec.metric == "rel":
        return None if spec.predicted == 0 else diff / abs(spec.predicted)
    return diff  # "abs"


class TableMeasure:
    """A deterministic sound oracle over a provided substrate: the deviation is the metric between the
    observed value (looked up in the substrate) and the value the claim predicts. Offline, no model. An
    unknown claim or a missing observation yields deviation None (UNVERIFIABLE), fail-closed: an oracle
    that cannot observe never reports a claim as holding."""

    name = "table"

    def __init__(self, specs: Mapping[str, MetricSpec], substrate: Mapping[str, float], *,
                 clock: Callable[[], float] = time.time) -> None:
        self._specs = dict(specs)
        self._substrate = dict(substrate)
        self._clock = clock

    def measure(self, claim: Claim) -> Measurement:
        spec = self._specs.get(claim.id)
        now = float(self._clock())
        if spec is None or spec.observe not in self._substrate:
            tol = spec.tolerance if spec is not None else 1.0
            return Measurement(claim.id, claim.sha256, None, tol, self.name, now, ())
        observed = self._substrate[spec.observe]
        dev = _deviation(spec, observed)
        evidence = (f"observed {spec.observe}={observed:g}, predicted {spec.predicted:g}, "
                    f"metric {spec.metric}",)
        return Measurement(claim.id, claim.sha256, dev, spec.tolerance, self.name, now, evidence)


def measure_thesis(measure: Measure, thesis: Thesis) -> list[Measurement]:
    """Run a measure over every claim in a thesis, returning one Measurement per claim in order."""
    return [measure.measure(c) for c in thesis.claims]
