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
mirroring Gather's digest seal. The seal folds in the title, the disposition, and each claim's id and
content hash, so swapping a claim's content, relabelling its id, or flipping the disposition breaks
the seal; reordering does not, because a thesis is a set. The disposition being sealed is what lets
the publication gate trust the label.

## The witnessed assessment

An assessment folds the per-claim verdicts into a record with its own seal, and it persists the
verdicts and the measurements alongside, so the seal has a preimage on disk rather than fingerprinting
discarded data. `verify_assessment` recomputes every seal from the stored arrays (the verdict seal
from the stored verdicts, the measurement seal from the stored measurements, the record seal from the
fields that bind both); it is not a tautology. `recheck_assessment` goes further: from the thesis and
the stored measurements it re-derives each verdict via `verdict_for` and confirms the stored verdicts
are exactly what the pure function yields, so a verdict that was asserted rather than computed is
exposed even when its seals are internally consistent. The CLI surfaces this as `crucible verdicts
--verify`. The seal proves integrity, not authorship: a fully consistent re-forge (every field and
seal rewritten together) is out of scope without a signature, and the docs say so where a user meets it.

## The seams (the impure and the optional)

Crucible's core is pure standard library. Optional edges live behind a Protocol seam with a Null
default, exactly as Gather isolates its synthesizer.

Shipped:

- **Steelman** (`Steelman` protocol): independent adversaries propose refutations. The default
  `NullSteelman` surfaces the claim's own stated falsification as the standing test and invents
  nothing; a model edge plugs in to generate independent refutations. Adversaries propose what to
  measure; the measurement decides. `steelman_thesis` stamps each refutation's source from the
  producing steelman's name, so the label is the producer's.

Forthcoming (P3, the measurement harness; not yet built, the spec describes it):

- **Measure** (a `Measure` protocol with a `NullMeasure` default): a sound oracle that produces a
  measurement of a claim against a substrate (the Telos verifier, or a symbolic or proof oracle for
  abstract math). `verdict_for` already accepts the `Measurement` such an oracle would produce.

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

Crucible stands alone and serves the constellation at once. What ships today is the standing-alone
half and the published contract: a sealed assessment and its verdicts, re-checkable from disk, that a
downstream organ reads to learn a thesis's standing. Crucible is built to consume other organs through
their documented on-disk contracts (a Gather witnessed digest as evidence, an index verified map or
the Telos verifier as a measurement oracle) without importing their internals; those composition
milestones are on the spec's ladder, Telos at 1.1.0, and are not yet built. Shared primitives, such as
the `refine` loop, are to be integrated natively rather than taken as third-party dependencies, so
reuse never costs standing alone. Seams default to Null, so the absence of a peer is a quieter
capability, never a failure.

## Peer composition

Crucible composes with the rest of the constellation (telos, index, forum, gather) through clean
protocol seams; it does not absorb or get absorbed. The sealed assessment is the contract a
downstream reader consumes. This is why Crucible is a peer organ, not a feature of index or of refine.
