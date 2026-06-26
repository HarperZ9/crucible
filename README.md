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
from the record, so a confident assertion cannot fake it.

## The loop

1. **Register** a thesis with its claims and, per claim, its falsification condition.
2. **Steelman**: independent adversaries propose the strongest refutation of each claim. They
   propose what to test; they do not decide.
3. **Measure**: bind each claim to a substrate and a metric, and record the deviation from what the
   claim predicts.
4. **Refine the weakest axis**: strengthen the substrate, sharpen the measurement, or amend the
   thesis, then re-iterate.
5. **Witness**: a re-checkable verdict per claim (MATCH / DRIFT / UNVERIFIABLE), sealed so a reader
   can confirm it was not altered.

The continuous part is the loop: substrates, measurements, and theses all improve across rounds,
and the witnessed verdicts track which moved.

Shipped today (0.10.0): the full first loop plus drift tracking, publication-gated export, registry
operations, optional subprocess-backed seam adapters, Telos witnessed-artifact interop, and
1.0-readiness coverage. You register a thesis, steelman it (adversaries propose the test), measure
each claim against a substrate oracle, refine across substrate rounds toward a cohesively verified
thesis, witness a re-derivable verdict per claim, compare assessment rounds to see what held, moved,
improved, or regressed, inspect a growing registry by status, scope, and latest verdict, plug
configured model/oracle commands into the steelman and measure seams, and consume
`telos.witnessed-artifact/v1` envelopes by re-running their named verifiers. A fenced thesis can be
assessed locally, but the export edge refuses it by default.

## The differentiator (do not lose this)

A claim's standing is a verdict grounded in a measurement, not a judge's say-so. Steelman
adversaries propose; the measurement decides. The decision is a pure function of the recorded
measurement, with no model in the verdict step, so the verdict recomputes from the stored record
and cannot be forged by a fluent assertion. UNVERIFIABLE is fail-closed: an axis that cannot be
measured is never read as holding.

## The discipline

- **A receipt on every claim.** Each claim carries a sha256 of its content, so a tampered claim is
  caught by re-hashing.
- **A grounded verdict, not a judgment call.** `verdict_for(claim, measurement)` is pure: a
  measurement within tolerance is MATCH, outside is DRIFT, absent or unmeasurable is UNVERIFIABLE.
- **A witnessed assessment out.** An assessment folds its verdicts into one re-checkable seal that a
  downstream organ consumes.
- **Stands alone, serves the constellation.** crucible runs on its own with zero third-party
  dependencies and Null seams, and it composes with the other Telos organs (Gather's evidence,
  index's maps) as a peer through clean protocol contracts. Compose, do not absorb.
- **Publication-gated.** Theses and verdicts carry a disposition; fenced material is refused at the
  export edge by default. This public repository carries only self-contained, publishable examples.

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

## Status

crucible is in active construction, built the way Gather and Forum were: one reviewed release per
increment, behind a feature branch, with tests, lint, and type checks green and an independent
whole-branch review before merge. The operator floor is 1.0; the target is organic completion at
1.5 or beyond.

Shipped:

- The verdict spine: a pure `verdict_for` returning MATCH / DRIFT / UNVERIFIABLE from a measurement,
  with no model in the verdict step and UNVERIFIABLE fail-closed.
- A content-hash receipt on every claim, and a thesis seal that binds the claims, the title, and the
  disposition (so the publication gate can trust the label).
- A witnessed assessment that persists its verdicts and measurements, so `verify_assessment`
  recomputes the seals from the stored data and `recheck_assessment` re-derives each verdict from the
  thesis and the measurements: a verdict cannot be asserted, it must follow from the record.
- A content-addressed registry that re-verifies stored claims (MATCH / MISSING / CORRUPT), checks
  thesis seals (catching a swapped claim a body check would miss), and refuses to load a tampered thesis.
- The steelman seam: independent adversaries propose the strongest refutation of each claim and the
  test that would settle it (they propose; the measurement decides). The Null default surfaces the
  claim's own falsification and invents nothing; a model edge plugs in through the same shape later.
- The measure seam: a sound oracle that decides a claim against a substrate. The `TableMeasure`
  computes each claim's deviation from a predicted value over a provided substrate (offline, no model);
  the `NullMeasure` default measures nothing (UNVERIFIABLE). The Telos verifier or a proof oracle for
  abstract math plugs in through the same shape, so the verdict stays grounded, never asserted.
- The refine loop: grade each claim's measured margin, compute harmonic-mean cohesion, reflect the
  weakest claim, and re-measure across substrate rounds until the thesis is cohesively verified or the
  budget is spent honestly. The loop reports the weakest claim instead of pretending a short thesis held.
- Drift tracking across witnessed assessments: `drift_track(previous, current)` and
  `crucible drift REGISTRY` compare the latest two rounds and classify each claim as held, moved,
  improved, or regressed from the recorded margins.
- Publication-gated export: `gate_check`, `export_guard`, `export_thesis`, and
  `crucible export THESIS` refuse fenced material and explicit restricted markers before emitting a
  public thesis contract.
- Registry operations: `registry_stats`, `search_theses`, `prune_objects`, and
  `crucible registry stats|search|prune` summarize the corpus, recall theses by scope/status/latest
  verdict, and prune orphan claim bodies only when explicitly applied.
- Optional subprocess edges: `SubprocessSteelman` and `SubprocessMeasure` run configured commands
  through bounded JSON stdin/stdout, reject shell strings, enforce timeouts, and stamp claim identity
  locally. The default seams remain Null and the verdict step still has no model in it.
- Telos artifact interop: `TelosMeasure` consumes `telos.witnessed-artifact/v1` envelopes through a
  caller-provided verifier registry. The carried certificate is not trusted; the named verifier is
  re-run and mapped into the normal `Measurement` -> `verdict_for` spine.
- Readiness coverage: the bundled examples run through the public CLI under test, help output covers
  the shipped command surface, and `docs/RELEASE-READINESS.md` records the 1.0 gate checklist.
- The `crucible` CLI: `register`, `assess`, `steelman`, `measure`,
  `registry list|verify|stats|search|prune`, `refine`, `drift`, `export`, `verdicts [--verify]`.

## License

crucible is fair-source: the code is open to read, run, and build on, with commercial use reserved
so the project can fund its own development. Copyright stays with the author. See
[LICENSE](LICENSE) for the exact terms.
