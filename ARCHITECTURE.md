# Crucible: architecture

Crucible is the cognition organ of the constellation: it tests a thesis against evidence and emits a
verdict you can re-check. This document is the map of how it is built and why. It grows as the organ
does; sections describe what is shipped.

## The one shape: a grounded `Verdict`

Every judgment Crucible makes reduces to one shape: a verdict per claim, computed from a measurement,
never asserted.

```python
def verdict_for(claim: Claim, measurement: Measurement | None) -> Verdict: ...
```

A measurement records a deviation from what the claim predicts and a tolerance. The verdict is a
pure function of that record: within tolerance is MATCH, outside is DRIFT, absent or unmeasurable is
UNVERIFIABLE. There is no model in this step, so the verdict recomputes from the stored record and a
confident assertion cannot fake it. UNVERIFIABLE is fail-closed: an axis that cannot be measured is
never read as holding.

## The receipt: `Claim`

Every claim carries a content hash, so a tampered claim is caught by re-hashing.

```python
@dataclass(frozen=True, slots=True)
class Claim:
    id: str            # defaults to sha256[:16]
    text: str          # the assertion
    falsification: str  # the observation that would refute it
    sha256: str        # content hash binding (text, falsification)
```

`make_claim` computes the hash; `Claim.verify()` re-hashes and confirms it still matches. A claim
with no falsification condition can only ever be UNVERIFIABLE: nothing would settle it.

## The thesis and its seal

A `Thesis` is a set of claims with a re-checkable seal over them (sorted, canonical JSON, sha256),
mirroring Gather's digest seal. Reordering, swapping, or relabelling a claim breaks the seal exactly
as tampering with content does. A thesis also carries a `disposition` (publishable or fenced) for the
publication gate.

## The witnessed assessment

An assessment folds the per-claim verdicts into a record with its own seal: when it ran, the thesis
seal, the counts of MATCH / DRIFT / UNVERIFIABLE, and the seal over the verdicts. It is re-checkable
from disk, so a reader confirms both that the verdicts are these and that they were not altered.

## The seams (the impure and the optional)

Crucible's core is pure standard library. Two edges are optional and live behind a Protocol seam with
a Null default, exactly as Gather isolates its synthesizer:

- **Steelman** (`Steelman` protocol): independent adversaries propose refutations. The default
  `NullSteelman` surfaces the claim's own stated falsification as the standing test and invents
  nothing; a model edge plugs in to generate independent refutations. Adversaries propose what to
  measure; the measurement decides.
- **Measure** (`Measure` protocol): produces a measurement of a claim against a substrate. The
  default `NullMeasure` makes no measurement (UNVERIFIABLE); a real oracle or metric plugs in.

The core imports neither the Null nor any model, so the package keeps zero third-party dependencies.

## The registry

A `Registry` is durable, content-addressed storage for theses and their assessments, mirroring
Gather's corpus: claim bodies at `objects/ab/cdef...` keyed by the claim hash, a `theses.jsonl`
catalog, and an `assessments.jsonl` history. `verify()` re-hashes every stored body and reports
MATCH / MISSING / CORRUPT, so the verdict's proof stays durable over a growing registry.

## Determinism and the zero-dependency core

Clocks are injected everywhere time is recorded; iteration is sorted; JSON is canonical
(`sort_keys`, `ensure_ascii=False`). So an assessment replays and a seal recomputes. The core is pure
standard library. A model edge may pull in whatever it needs, but only behind a seam, and only at the
impure edge.

## Protocol interoperability (the dual mandate)

Crucible stands alone and serves the constellation at once. It consumes other organs through their
documented on-disk contracts (a Gather witnessed digest as evidence, an index verified map as a
substrate) without importing their internals, and it is consumed through its own published contract
(the sealed assessment and verdicts). Shared primitives, such as the `refine` loop, are integrated
natively rather than taken as third-party dependencies, so reuse never costs standing alone. Seams
default to Null, so the absence of a peer is a quieter capability, never a failure.

## Peer composition

Crucible composes with the rest of the constellation (telos, index, forum, gather) through clean
protocol seams; it does not absorb or get absorbed. The sealed assessment is the contract a
downstream reader consumes. This is why Crucible is a peer organ, not a feature of index or of refine.
