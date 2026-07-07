# Introduction to crucible

crucible is a judgment engine for claims that a decision depends on. You give it a thesis broken
into claims, each paired with the observation that would refute it. It steelmans the claims,
measures each one against an oracle, and returns a verdict per claim: MATCH, DRIFT, or
UNVERIFIABLE. The verdict is computed from the recorded measurement, not from a model's opinion,
and the whole run persists as a sealed record that anyone can recompute later.

It ships as the PyPI package `crucible-bench` (command `crucible`, package `import crucible`),
requires Python 3.11 or newer, and has zero third-party runtime dependencies.

## Why it exists

Claims are cheap to assert and expensive to check, and in most workflows the check evaporates the
moment it happens: a reviewer nods, a test passes once, a number gets repeated until it sounds
true. crucible exists to make the check durable. Every verdict re-derives from a stored record, so
standing comes from the measurement that survives a recheck, not from whoever asserted it last.

## Core concepts

**Thesis and claims.** A thesis is a titled set of claims. Each claim carries its text, a
falsification condition (what observation would refute it), and a sha256 content hash. A claim
with an empty falsification condition can never verify: it is UNVERIFIABLE by construction.

**Steelman.** Before measuring, independent adversaries propose the strongest refutation of each
claim and the test that would settle it. They propose; they never decide. The default Null
steelman restates the claim's own falsification condition and invents nothing.

**Measurement.** A measurement binds to a claim by content hash and records a deviation from what
the claim predicts, a tolerance, a method, and evidence. Measurements come from a manual JSON
file, from the built-in table oracle (`--substrate`), or from pluggable edges: subprocess
commands, Telos witnessed artifacts, gather digests, index verification records, or an LLM judge.

**Verdict.** `verdict_for(claim, measurement)` is pure: deviation within tolerance is MATCH,
outside is DRIFT, missing or unmeasurable is UNVERIFIABLE. UNVERIFIABLE is fail-closed: an axis
that cannot be measured is never read as holding. No model participates in this step.

**Witnessed assessment.** An assessment folds its verdicts and measurements into one sealed
record. Verification recomputes the seals from the stored data and re-derives every verdict from
the thesis and measurements, so a flipped verdict or edited margin is caught mechanically.

**Registry.** A content-addressed directory that stores theses and assessments, re-verifies claim
bodies, checks thesis seals, and supports list, verify, stats, search, and prune operations.

**Refine and drift.** The loop is continuous: grade each claim's measured margin, refine the
weakest axis (substrate, measurement, or thesis), and re-measure across rounds. `drift` compares
the latest two assessments and classifies each claim as held, moved, improved, or regressed.

## Your first ten minutes

Work from a clone so the examples are on disk:

```bash
git clone https://github.com/HarperZ9/crucible
cd crucible
pip install -e ".[dev]"
```

**Minute 1: the demo.** Run the bundled walkthrough:

```bash
python examples/demo.py
```

It registers a three-claim thesis about binary search, steelmans it, assesses it against
measurements, prints one verdict per claim (one MATCH, one DRIFT, one UNVERIFIABLE), and then
flips a verdict in the stored record to show verification catching the tamper.

**Minutes 2 to 4: read the thesis.** Open `examples/thesis-binary-search.json`. Three claims:
a true bound (at most 11 comparisons for n=1024), a false bound (at most 3), and an opinion with
an empty falsification condition. Open `examples/measurements-binary-search.json` and see how each
measurement row names a `claim_sha256`, a `deviation`, and a `tolerance`. The verdicts you just
saw follow from these two files and nothing else.

**Minutes 5 to 7: a full run into a registry.**

```bash
crucible run examples/thesis-binary-search.json \
  --measurements examples/measurements-binary-search.json \
  --registry .crucible-registry
```

The output reports the verdict counts, the assessment seal, and `re-derived from disk: True`,
meaning the verdicts were recomputed from what was just written, not echoed from memory. Inspect
the stored state:

```bash
crucible verdicts .crucible-registry --verify
crucible registry stats .crucible-registry
crucible report .crucible-registry
```

Swap `--measurements` for `--substrate examples/substrate-binary-search.json` to route the same
run through the table oracle.

**Minutes 8 to 10: a cleanroom packet.** Re-run with `--bundle`:

```bash
crucible run examples/thesis-binary-search.json \
  --measurements examples/measurements-binary-search.json \
  --registry .crucible-registry \
  --bundle reports/first-run
crucible review reports/first-run
```

The bundle directory contains `spec.json`, `run.json`, `report.md`, and `review.md`, with
packet-relative artifact paths. This is the handoff shape: a verifier gets the original spec and
the artifact, nothing else. `review` fails closed if the packet carries extra context, drifted
metadata, or a report that no longer renders from the run record.

## Where to go next

- **Gate your CI on verdicts.** `crucible ci REGISTRY --write-baseline FILE` then
  `--baseline FILE` fails a build when any claim loses standing. Merged to main after 1.1.0;
  available today from a source checkout, on PyPI in the next release. The README has a
  ready-to-copy GitHub Action.
- **Plug in your own oracle.** Start with `SubprocessMeasure` (a configured command over bounded
  JSON stdio) or the interop edges: `TelosMeasure`, `GatherDigestMeasure`, `IndexMeasure`,
  `JudgeMeasure`. See [ARCHITECTURE.md](../ARCHITECTURE.md) for the seam shapes.
- **Batch and track.** `crucible batch MANIFEST --registry DIR` runs many theses into one
  registry; `crucible drift DIR` shows what moved between rounds; `crucible recheck DIR` writes
  oracle replay templates for descriptor-bearing measurements.
- **Serve it to a host.** `crucible mcp` exposes 13 tools over MCP stdio; `crucible status --json`
  and `crucible doctor --json` give hosts a machine-readable envelope.
- **Read the contracts.** [USAGE.md](../USAGE.md) for the interop boundary,
  [ENTERPRISE-READINESS.md](ENTERPRISE-READINESS.md) for unattended-agent integration,
  [CHANGELOG.md](../CHANGELOG.md) for what is merged but not yet released.
