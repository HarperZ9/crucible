# crucible: architecture

crucible is the cognition organ of the constellation: it tests a thesis against evidence and emits a
verdict you can re-check. This document is the map of how it is built and why. It grows as the organ
does; sections describe what is shipped.

## The one shape: a grounded `Verdict`

Every judgment crucible makes reduces to one shape: a verdict per claim, computed from a measurement,
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

Measurements may carry an optional `recheck` descriptor. When present, it is persisted with the
measurement row and included in the measurement seal; when absent, legacy rows keep the original seal
shape, so older assessments still verify. `recheck_measurements` is the oracle-level hook: a caller
provides replay functions keyed by descriptor `oracle`, and crucible compares the replayed measurement
inputs to the stored row. The shipped CLI still re-derives verdicts from stored measurements; external
callers can now also re-run descriptor-bearing measurements.

## The seams (the impure and the optional)

crucible's core is pure standard library. Optional edges live behind a Protocol seam with a Null
default, exactly as Gather isolates its synthesizer.

- **Steelman** (`Steelman` protocol): independent adversaries propose refutations. The default
  `NullSteelman` surfaces the claim's own stated falsification as the standing test and invents
  nothing; a model edge plugs in to generate independent refutations. Adversaries propose what to
  measure; the measurement decides. `steelman_thesis` stamps each refutation's source from the
  producing steelman's name, so the label is the producer's.
- **Measure** (`Measure` protocol): the sound-oracle edge that decides a claim against a substrate.
  The default `NullMeasure` measures nothing (UNVERIFIABLE); the deterministic `TableMeasure` computes
  a claim's deviation from a predicted value over a provided substrate (offline, no model). A real
  oracle (the Telos verifier, or a symbolic or proof oracle for abstract math) plugs in through the
  same shape, and `verdict_for` decides from the `Measurement` it produces. This is where the verdict
  is grounded.
- **Refine** (`refine_thesis`): the continuous loop that measures a thesis, grades each claim by its
  normalized margin, computes harmonic-mean cohesion, reflects the weakest claim, and re-iterates via
  a caller-provided adjuster. It never returns `correct` unless every claim has enough margin and the
  margins are cohesive; if the budget is spent it reports the weakest claim.

The core imports neither the Null nor any model, so the package keeps zero third-party dependencies.

## Subprocess seam adapters

`SubprocessSteelman` and `SubprocessMeasure` are optional stdlib adapters for configured commands.
They exchange one bounded JSON request/response over stdin/stdout, enforce a timeout, and reject shell
strings so arguments are not re-parsed by a shell. A child process may propose a challenge or report a
deviation, but crucible stamps the claim identity, claim hash, and producer name locally. The verdict
still follows from `verdict_for`; a subprocess cannot assert MATCH.

## Telos artifact interop

`TelosMeasure` consumes the Telos engine's `telos.witnessed-artifact/v1` protocol without importing
Telos. The artifact carries a compact certificate and a `recheck` descriptor naming a verifier. A
caller supplies a verifier registry; crucible re-runs the named verifier, compares the reproduced
verdict to the carried verdict, and turns that live result into a normal Measurement. Reproduced
`verified` becomes a MATCH input, reproduced `refuted` or a drifted carried verdict becomes a DRIFT
input, and a missing/unregistered/unverifiable proof becomes an UNVERIFIABLE input. That keeps the
interop on the same spine: trust the proof, not the emitter.

## Gather/index interop

`GatherDigestMeasure` consumes Gather's digest contract directly: a list of evidence receipts and a
seal recomputed from those receipts. A caller maps a crucible claim to the receipt fields it expects
to exist. A verified digest with that receipt becomes a MATCH input; a verified digest without it
becomes a DRIFT input; a malformed or missing digest becomes UNVERIFIABLE. This makes "show me the
evidence receipt" a measurable claim.

`IndexMeasure` consumes `index.verification/1` records directly. The record carries an index claim,
the canonical hash of the graph pack it was computed against, and a carried verdict. crucible is
given the graph pack by hash, replays the supported structural claim (`exists` or `depends`), and
maps the reproduced result into the same Measurement spine. It does not import index, execute index,
or trust the carried verdict without replaying the pack.

## Drift tracking

The continuous loop needs an honest account of what changed between rounds. `drift_track(previous,
current)` compares two witnessed assessments of the same thesis and classifies each claim as held,
moved, improved, or regressed. Numeric margins decide improvement and regression. Unrankable
transitions, such as UNVERIFIABLE to MATCH, are reported as moved rather than silently promoted.
The CLI exposes this as `crucible drift REGISTRY`, comparing the latest two stored assessments.

## Publication gate

Assessment and export are deliberately separate. A fenced thesis may be registered and assessed
locally, but the public export edge applies `gate_check` and refuses anything with a fenced
disposition or an explicit fenced/restricted marker in the title, claim text, or falsification. The
exported contract omits runtime metadata and carries only the title, disposition, thesis seal, and
content-hashed claims needed for public re-checking.

## The registry

A `Registry` is durable, content-addressed storage for theses and their assessments, mirroring
Gather's corpus: claim bodies at `objects/ab/cdef...` keyed by the claim hash, a `theses.jsonl`
catalog, and an `assessments.jsonl` history. `verify()` re-hashes every stored body and reports
MATCH / MISSING / CORRUPT, so the verdict's proof stays durable over a growing registry.

`registry_ops` reads across that store without changing the storage contract. `registry_stats`
summarizes thesis counts, claim bodies, dispositions, assessment history, and the latest verdict
posture per thesis. `search_theses` recalls theses by scope text, thesis status, and latest verdict
status. `prune_objects` identifies orphaned claim bodies and is dry-run by default; deletion requires
an explicit apply path and validates each object path before unlinking it.

## Determinism and the zero-dependency core

Clocks are injected everywhere time is recorded; iteration is sorted; JSON is canonical
(`sort_keys`, `ensure_ascii=False`). So an assessment replays and a seal recomputes. The core is pure
standard library. A model edge may pull in whatever it needs, but only behind a seam, and only at the
impure edge.

## Protocol interoperability (the dual mandate)

crucible stands alone and serves the constellation at once. What ships today is the standing-alone
half and the published contract: a sealed assessment and its verdicts, re-checkable from disk, that a
downstream organ reads to learn a thesis's standing. It also includes first protocol adapters for
Telos witnessed artifacts, Gather witnessed digests, and index verification records. These adapters
consume documented JSON contracts without importing sibling internals. Shared primitives, such as the
`refine` loop, are integrated natively rather than taken as third-party dependencies, so reuse never
costs standing alone. Seams default to Null, so the absence of a peer is a quieter capability, never a
failure.

## Peer composition

crucible composes with the rest of the constellation (telos, index, forum, gather) through clean
protocol seams; it does not absorb or get absorbed. The sealed assessment is the contract a
downstream reader consumes. This is why crucible is a peer organ, not a feature of index or of refine.
