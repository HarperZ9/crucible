# crucible

![python: 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![deps: none (core)](https://img.shields.io/badge/core%20deps-none-success.svg)
![license: fair-source](https://img.shields.io/badge/license-fair--source-blue.svg)

Ideas are cheap to assert and expensive to check. A claim gets repeated until it sounds true.
A correction arrives quietly and never catches up. A theory's standing becomes a vibe rather
than a record, and the loudest version wins. crucible is the organ that holds an idea to account.

It is the cognition counterpart to Gather. Where Gather brings evidence in and records how it was
obtained (the afferent organ), crucible tests a thesis against that evidence and emits a verdict you
can re-check (the efferent organ). You register a thesis as a set of claims, and for each claim the
observation that would refute it. crucible steelmans the claims (proposing the test that would settle
each), measures them against a substrate oracle, and writes a verdict per claim: MATCH, DRIFT, or
UNVERIFIABLE. The verdict is grounded in the measurement, not in a judge's opinion, and it recomputes
from the record, so a confident assertion has no effect on the rechecked result.

## The loop

1. **Register** a thesis with its claims and, per claim, its falsification condition.
2. **Steelman**: independent adversaries propose the strongest refutation of each claim. They
   propose what to test; they do not decide.
3. **Measure**: bind each claim to a substrate and a metric, and record the deviation from what the
   claim predicts.
4. **Refine the weakest axis**: strengthen the substrate, sharpen the measurement, or amend the
   thesis, then re-iterate.
5. **Witness**: a re-checkable verdict per claim (MATCH / DRIFT / UNVERIFIABLE), sealed so a reader
   can re-hash the stored record and catch inconsistent tampering. This is not an authorship
   signature.

The continuous part is the loop: substrates, measurements, and theses all improve across rounds,
and the witnessed verdicts track which moved.

1.0.0 delivered the flagship floor: the full first loop plus drift tracking, Markdown assessment
reports, publication-gated export, registry operations, optional subprocess-backed seam adapters,
Telos witnessed-artifact interop, Gather/index protocol interop, measurement recheck descriptors,
batch assessment/report bundles, and clean verifier practice. The 1.1.0 branch adds operator run and
oracle recheck and cleanroom review commands over that spine. You register a thesis, steelman it
(adversaries propose the test), measure each claim against a substrate oracle, refine across substrate
rounds toward a
cohesively verified thesis, witness a re-derivable verdict per claim,
compare assessment rounds to see what held, moved, improved, or regressed, inspect a growing registry
by status, scope, and latest verified verdict, plug configured oracle commands into the steelman and
measure seams, consume `telos.witnessed-artifact/v1` envelopes by re-running their named verifiers,
use sealed Gather digests as evidence, replay index verification records against supplied graph
packs, persist optional measurement replay descriptors for oracle-level checks, run a manifest of
thesis jobs into one registry, render witnessed assessments as readable Markdown reports, or run the
whole steelman -> measure -> assess -> recheck path as one cleanroom review packet. A fenced thesis
can be assessed locally, but the export edge refuses it by default.

## The differentiator (do not lose this)

A claim's standing is a verdict grounded in a measurement, not a judge's say-so. Steelman
adversaries propose; the measurement decides. The decision is a pure function of the recorded
measurement, with no model in the verdict step, so the verdict recomputes from the stored record
and a fluent assertion has no effect on the rechecked result. UNVERIFIABLE is fail-closed: an axis
that cannot be measured is never read as holding.

## The discipline

- **A receipt on every claim.** Each claim carries a sha256 of its content, so a tampered claim is
  caught by re-hashing.
- **A grounded verdict, not a judgment call.** `verdict_for(claim, measurement)` is pure: a
  measurement within tolerance is MATCH, outside is DRIFT, absent or unmeasurable is UNVERIFIABLE.
- **A witnessed assessment out.** An assessment folds its verdicts into one re-checkable seal that a
  downstream organ consumes.
- **A clean verifier boundary.** A verifier gets the original spec and the artifact. It does not need
  the worker's context, reasoning trace, or intermediate steps. If success cannot be evaluated from
  that minimal state, the spec is not checkable yet. `crucible run --bundle` makes that boundary
  concrete with a packet-level review note, and `crucible review BUNDLE` validates the packet before
  handoff.
- **Stands alone, serves the constellation.** crucible runs on its own with zero third-party
  dependencies and Null seams, and it composes with the other Telos organs (Gather's evidence,
  index's maps) as a peer through clean protocol contracts. Compose, do not absorb.
- **Publication-gated.** Theses and verdicts carry a disposition; fenced material is refused at the
  export edge by default. This is a mechanical disposition and marker guard, not semantic content
  classification. This public repository carries only self-contained, publishable examples.

## Install

When published:

```bash
pip install crucible-bench
```

The distribution is `crucible-bench`; it installs the `crucible` command and the `crucible` package
(`import crucible`). The core is pure standard library. From a clone:

```bash
pip install -e ".[dev]"
```

## Batch manifests

From a clone, run several thesis assessments into one registry, with optional report files:

```bash
crucible batch examples/batch-binary-search.json --registry .crucible-registry --reports reports
```

A job names a thesis plus exactly one measurement source:

```json
{
  "jobs": [
    {
      "id": "binary-search-manual",
      "thesis": "thesis-binary-search.json",
      "measurements": "measurements-binary-search.json"
    },
    {
      "id": "binary-search-substrate",
      "thesis": "thesis-binary-search.json",
      "substrate": "substrate-binary-search.json"
    }
  ]
}
```

## One-command runs

For an operator session, `run` ties the loop together and records the witnessed assessment into a
registry before reporting the disk recheck:

```bash
crucible run examples/thesis-binary-search.json \
  --measurements examples/measurements-binary-search.json \
  --registry .crucible-registry \
  --bundle reports/binary-search-run \
  --json
```

The JSON run record includes thesis metadata, steelman refutations, the witnessed assessment, the
derived verdict rows, disk recheck status, and verifier packet paths. `--bundle DIR` creates
`DIR/spec.json`, `DIR/run.json`, `DIR/report.md`, and `DIR/review.md` with exclusive writes. The
packet gives a verifier only the original spec and artifact. Use `--substrate` instead of
`--measurements` to run through the table oracle in the same session shape.

Before handing the packet to a verifier, validate the cleanroom boundary:

```bash
crucible review reports/binary-search-run --json
```

The review check fails closed if the bundle is missing required files, carries extra context such as
notes or chat logs, omits the cleanroom verifier boundary, has a `spec.json` that no longer
matches the run record, has a `report.md` that does not render from `run.json`, or has
`review.md` instructions that diverge from the cleanroom verifier boundary.

## Oracle recheck packs

Descriptor-bearing measurements can be inspected from the registry:

```bash
crucible recheck .crucible-registry --json
```

To hand the work to a verifier or oracle wrapper, write a replay pack template:

```bash
crucible recheck .crucible-registry --template replay-template.json
```

The template contains claim context, the original `recheck` descriptor, the sealed measurement row to
reproduce, and blank measurement fields for the verifier to fill. The assessment block binds a
returned pack to the thesis id, assessment seal, and measurement seal. A verifier or oracle wrapper
can then return a replay pack with the original descriptor and the reproduced measurement row:

```json
{
  "replays": [
    {
      "recheck": {"oracle": "telos:conservation", "verifier": "conservation"},
      "measurement": {
        "claim_id": "claim-id",
        "claim_sha256": "claim-sha256",
        "deviation": 0.0,
        "tolerance": 0.1,
        "method": "telos:conservation",
        "measured_at": 1000.0,
        "evidence": ["verifier reproduced certificate"]
      }
    }
  ]
}
```

Run the replay check with:

```bash
crucible recheck .crucible-registry --pack replay.json --json
```

The replay pack does not decide the verdict. If it includes an `assessment` block, that block must
match the selected assessment before measurement replay starts. The pack only proves whether the
sealed descriptor-bearing measurement rows can be reproduced; the verdict still follows from the
stored measurement through `verdict_for`.

## Status

crucible is at its 1.0 flagship floor: the core loop is stable, the public CLI is covered, and the
release branch passes tests, lint, type checks, build checks, and minimal-context review before
merge. Development continues by adding sharper substrates and oracle edges without weakening the
measurement -> verdict spine.

Shipped:

- The verdict spine: a pure `verdict_for` returning MATCH / DRIFT / UNVERIFIABLE from a measurement,
  with no model in the verdict step and UNVERIFIABLE fail-closed.
- A content-hash receipt on every claim, and a thesis seal that binds the claims, the title, and the
  disposition (so the publication gate can trust the label).
- A witnessed assessment that persists its verdicts and measurements, so `verify_assessment`
  recomputes the seals from the stored data and `recheck_assessment` re-derives each verdict from the
  thesis and the measurements: a verdict, margin, and grounds cannot be asserted, they must follow
  from the record. Summary counts are re-derived from verdict rows as part of verification, and the
  thesis disposition is carried in the assessment and verdict rows.
- A content-addressed registry that re-verifies stored claims (MATCH / MISSING / CORRUPT), checks
  thesis seals (catching a swapped claim a body check would miss), rejects duplicate thesis ids with
  different seals, refuses symlinked storage paths, and refuses to load a tampered thesis.
- The steelman seam: independent adversaries propose the strongest refutation of each claim and the
  test that would settle it (they propose; the measurement decides). The Null default surfaces the
  claim's own falsification and invents nothing; custom edges plug in through the same API shape.
- The measure seam: a sound oracle that decides a claim against a substrate. The `TableMeasure`
  computes each claim's deviation from a predicted value over a provided substrate (offline, no model);
  the `NullMeasure` default measures nothing (UNVERIFIABLE). The Telos verifier or a proof oracle for
  abstract math plugs in through the same shape, so the verdict stays grounded, never asserted.
- Measurement rechecks: assessment rows persist and seal `measured_at`, evidence, and optional
  `recheck` descriptors. `recheck_measurements` lets a caller provide oracle replayers that reproduce
  stored measurement inputs from those descriptors.
- Oracle replay CLI: `crucible recheck REGISTRY [--template FILE] [--pack FILE]` lists
  descriptor-bearing measurement rows, writes replay pack templates for clean verifier handoff, and
  validates finished oracle replay packs against the sealed measurement rows without creating a second
  verdict path.
- The refine loop: grade each claim's measured margin, compute harmonic-mean cohesion, reflect the
  weakest claim, and re-measure across substrate rounds until the thesis is cohesively verified or the
  budget is spent honestly. The loop reports the weakest claim instead of pretending a short thesis held.
- Drift tracking across witnessed assessments: `drift_track(previous, current)` and
  `crucible drift REGISTRY` compare the latest two rounds and classify each claim as held, moved,
  improved, or regressed from the recorded margins.
- Assessment reports: `render_assessment_report` and `crucible report REGISTRY` render a deterministic
  Markdown artifact with counts, seals, integrity checks, verdict dispositions, measurement evidence,
  and recheck descriptors.
- Batch assessment: `crucible batch MANIFEST --registry DIR [--reports DIR]` consumes a manifest of
  thesis jobs, records each assessment into one registry, and optionally writes one Markdown report
  per job. Manifest paths stay inside the manifest bundle, path-like missing refs fail closed, and
  reports use unique index-prefixed names with exclusive writes.
- Operator runs: `crucible run THESIS --registry DIR (--measurements FILE | --substrate FILE)` runs
  the null steelman, measurement, witnessed assessment, disk recheck, and optional Markdown/JSON
  artifact writes as one scannable session. `--bundle DIR` writes `spec.json`, `run.json`,
  `report.md`, and `review.md` as a self-contained cleanroom review packet.
- Cleanroom bundle review: `crucible review BUNDLE` validates that a review packet contains only
  the allowed spec/artifact files, carries the verifier boundary, has matching `spec.json` and
  run-record thesis metadata, has a `report.md` artifact that re-renders from `run.json`, and keeps
  `review.md` pinned to the cleanroom verifier instructions before verifier handoff.
- Publication-gated export: `gate_check`, `export_guard`, `export_thesis`, and
  `crucible export THESIS` refuse fenced material and explicit restricted markers before emitting a
  public thesis contract.
- Registry operations: `registry_stats`, `search_theses`, `prune_objects`, and
  `crucible registry stats|search|prune` summarize the corpus, recall theses by scope/status/latest
  verdict, and prune orphan claim bodies only when explicitly applied after registry path guards pass.
- Optional subprocess edges: `SubprocessSteelman` and `SubprocessMeasure` run configured commands
  through bounded JSON stdin/stdout, reject shell strings, enforce timeouts, and stamp claim identity
  locally. By default they pass only a minimal environment, discard stderr, and actively terminate
  children whose stdout exceeds the configured response bound. The default seams remain Null and the
  verdict step still has no model in it.
- Telos artifact interop: `TelosMeasure` consumes `telos.witnessed-artifact/v1` envelopes through a
  caller-provided verifier registry. The carried certificate is not trusted; the named verifier is
  re-run, mapped into the normal `Measurement` -> `verdict_for` spine, and stored with a
  `telos:<verifier>` replay descriptor.
- Gather/index interop: `GatherDigestMeasure` consumes sealed Gather digests and checks that a
  claim's expected evidence receipt exists; `IndexMeasure` consumes `index.verification/1` records
  and replays their structural claims against supplied graph packs. Both map into the same normal
  `Measurement` -> `verdict_for` spine.
- Readiness coverage: the bundled examples run through the public CLI under test, help output covers
  the shipped command surface, and `docs/RELEASE-READINESS.md` records the 1.0 gate checklist,
  including the spec-plus-artifact-only verifier rule.
- The `crucible` CLI: `register`, `assess`, `steelman`, `measure`,
  `run`, `recheck`, `review`, `registry list|verify|stats|search|prune`, `refine`, `drift`,
  `report`, `batch`, `export`, `verdicts [--verify]`.

## License

crucible is fair-source: the code is open to read, run, and build on, with commercial use reserved
so the project can fund its own development. Copyright stays with the author. See
[LICENSE](LICENSE) for the exact terms.
