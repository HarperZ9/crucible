# Crucible

![python: 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![deps: none (core)](https://img.shields.io/badge/core%20deps-none-success.svg)
![license: fair-source](https://img.shields.io/badge/license-fair--source-blue.svg)

Ideas are cheap to assert and expensive to check. A claim gets repeated until it sounds true.
A correction arrives quietly and never catches up. A theory's standing becomes a vibe rather
than a record, and the loudest version wins. Crucible is the organ that holds an idea to account.

It is the cognition counterpart to Gather. Where Gather brings evidence in and records how it was
obtained (the afferent organ), Crucible tests a thesis against that evidence and emits a verdict you
can re-check (the efferent organ). You register a thesis as a set of claims, and for each claim the
observation that would refute it. Crucible steelmans the claims, measures them against a substrate,
and writes a verdict per claim: MATCH, DRIFT, or UNVERIFIABLE. The verdict is grounded in the
measurement, not in a judge's opinion, and it recomputes from the record, so a confident assertion
cannot fake it.

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
- **Stands alone, serves the constellation.** Crucible runs on its own with zero third-party
  dependencies and Null seams, and it composes with the other Telos organs (Gather's evidence,
  index's maps) as a peer through clean protocol contracts. Compose, do not absorb.
- **Publication-gated.** Theses and verdicts carry a disposition; fenced material is refused at the
  export edge by default. This public repository carries only self-contained, publishable examples.

## Install

When published:

```bash
pip install crucible-engine
```

The distribution is `crucible-engine`; it installs the `crucible` command and the `crucible` package
(`import crucible`). The core is pure standard library. From a clone:

```bash
pip install -e ".[dev]"
```

## Status

Crucible is in active construction, built the way Gather and Forum were: one reviewed release per
increment, behind a feature branch, with tests, lint, and type checks green and an independent
whole-branch review before merge. The operator floor is 1.0; the target is organic completion at
1.5 or beyond.

Shipped:

- (the P1 foundation is the first release; this section grows with each increment)

## License

Crucible is fair-source: the code is open to read, run, and build on, with commercial use reserved
so the project can fund its own development. Copyright stays with the author. See
[LICENSE](LICENSE) for the exact terms.
