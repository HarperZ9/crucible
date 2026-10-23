<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/HarperZ9/crucible/main/docs/art/hero-dark.svg">
  <img src="https://raw.githubusercontent.com/HarperZ9/crucible/main/docs/art/hero-light.svg" alt="crucible: Register a thesis, measure each claim, name the weakest axis. Seven measured axes fan out from a bright core inside fine rings. One axis falls short of the dashed tolerance ring and is marked DRIFT; one has no measurement and is marked UNVERIFIABLE." width="100%">
</picture>

# Crucible

Test each claim in a thesis against a measurement and get MATCH, DRIFT or UNVERIFIABLE, with a record anyone can recheck.

You write a thesis as a list of claims, and each claim names the observation that would prove it wrong. You supply measurements: a deviation and a tolerance per claim, from a benchmark, a script, a proof checker or a model judge. Crucible decides each verdict with a pure function. A deviation within tolerance is MATCH, a deviation outside it is DRIFT, and a claim with no falsification condition or no measurement is UNVERIFIABLE. It seals the thesis, the measurements and the verdicts into a local registry, so a later reader can recompute every verdict and see any edit.

It is for people who publish or review claims about software, models or research results and want each claim tied to the evidence that settles it: evaluation engineers, reviewers of AI agent output and researchers. The core is Python standard library only, runs offline and needs no account or API key.

## Install and first run

[![version: 1.6.0](https://img.shields.io/badge/version-1.6.0-e6e1d6?style=flat-square&labelColor=1a1712)](https://pypi.org/project/crucible-bench/)

`crucible-bench 1.6.0` is the current release on PyPI. It needs Python 3.11 or newer and installs the `crucible` command and the `crucible` Python package.

```bash
pip install crucible-bench
crucible examples --out crucible-examples
crucible run crucible-examples/thesis-binary-search.json \
  --measurements crucible-examples/measurements-binary-search.json \
  --registry .crucible-registry
```

```text
wrote 5 example inputs to crucible-examples
ran thesis bd7404c02eb2036e: 3 claim(s)
  steelman refutations: 3
  MATCH 1  DRIFT 1  UNVERIFIABLE 1
  re-derived from disk: True  {'seals_ok': True, 'thesis_ok': True, 'verdicts_rederive': True}
```

The example thesis makes three claims about binary search on 1,024 elements. "At most 11 comparisons" measures a deviation of 0 and holds. "At most 3 comparisons" measures a deviation of 8 and drifts. "More elegant than linear search" names no way to be wrong, so it stays UNVERIFIABLE.

Recheck the registry, then change one stored verdict and recheck again:

```bash
crucible verdicts .crucible-registry --verify
python -c "p='.crucible-registry/assessments.jsonl'; s=open(p).read(); open(p,'w').write(s.replace('\"status\": \"DRIFT\"','\"status\": \"MATCH\"',1))"
crucible verdicts .crucible-registry --verify
```

```text
re-checked 1 assessment(s): 1 ok, 0 not
  bd7404c02eb2036e ok=True  seals=True thesis=True rederive=True
re-checked 1 assessment(s): 0 ok, 1 not
  bd7404c02eb2036e ok=False  seals=False thesis=True rederive=False
```

The second check exits with status 1. Add `--bundle DIR` to `crucible run` to write a review packet, and `crucible review DIR` checks the packet before you hand it to a reviewer. `crucible mcp` serves the same operations to an MCP client.

## How it compares

promptfoo, DeepEval, Inspect, OpenAI Evals and Ragas run test cases against a model and score its outputs. They generate the measurements. Crucible starts where a measurement exists and decides what it means for a stated claim. It does not call a model by default and ships no datasets. It adds three things those tools leave to you: every claim must name its falsification condition, a missing measurement is reported as UNVERIFIABLE with the evidence it lacks, and the sealed registry lets a third party recompute each verdict. A score from any of those tools can enter Crucible as a measurement row. `crucible ci` then fails a pull request when a claim moves from MATCH to DRIFT or loses its measurement.

## Limits

- A verdict is only as good as the measurement fed to it. Crucible checks that a measurement binds to its claim and that the tolerance did not change after sealing. It cannot tell whether the measurement itself is correct.
- The steelman stage proposes the test that would settle each claim. The default restates the claim's own falsification condition. A model or command steelman plugs in through the API.
- A sealed registry proves the record is unchanged since sealing. It does not prove who made it or that the claim is true.
- The model-judge, pairwise and decomposition modes were measured once with one 2B local judge (`docs/benchmarks/judging-v1`). Agreement with human preferences is untested.

## Highlights

- **Verdicts that recompute from the record.** `verdict_for(claim, measurement)` is a pure function: within tolerance is MATCH, outside is DRIFT, absent or unmeasurable is UNVERIFIABLE, fail-closed. No model sits in the verdict step, so a fluent assertion cannot move a rechecked result.
- **One-command runs with cleanroom review packets.** `crucible run --bundle DIR` executes steelman, measurement, witnessed assessment, and disk recheck in one session, then writes a self-contained verifier packet (`spec.json`, `run.json`, `report.md`, `review.md`). `crucible review DIR` validates the packet boundary before handoff.
- **A CI regression check.** `crucible ci` compares a registry's verified-latest verdicts against a sealed baseline, exits nonzero when any claim loses standing, and emits a deterministic PR-comment Markdown matrix. New in 1.2.0.
- **A refine loop that names the weakest claim.** Grade each claim's measured margin, compute harmonic-mean cohesion, and re-measure across substrate rounds until the thesis is cohesively verified or the budget is spent. The loop reports the weakest axis instead of pretending a short thesis held.
- **Drift tracking across rounds.** `crucible drift` compares the latest two witnessed assessments and classifies each claim as held, moved, improved, or regressed.
- **LLM-as-judge with the model outside the verdict.** `JudgeMeasure` scores freeform outputs against a rubric; the judge produces a deviation once at the seam, the verdict still derives from `verdict_for`, and a judge that raises or returns garbage fails closed. New in 1.2.0.
- **Oracle recheck packs.** `crucible recheck` lists descriptor-bearing measurements, writes `crucible.replay-template/1` templates, and validates `crucible.replay-pack/1` inputs against the sealed rows without opening a second verdict path. A privacy-bounded `crucible.replay-set/1` binding covers the descriptor-bearing replay contracts without exporting descriptorless rows or their evidence. CLI replay packs must preserve the template's assessment binding; a missing or mismatched thesis ID, assessment seal, or measurement seal fails closed before replay.
- **A content-addressed registry with tamper detection.** Every claim carries a sha256 receipt; the registry re-verifies stored claims (MATCH / MISSING / CORRUPT), checks thesis seals, rejects duplicate ids with different seals, and refuses tampered theses.
- **Typed missing-evidence explanations.** Every UNVERIFIABLE verdict names the exact evidence class it lacks and the concrete next action, derived from the same pure ladder as the verdict, so the explanation can never disagree with it. New in 1.2.0.
- **Batch manifests, Markdown reports, creative measurement gates, native MCP.** `crucible batch` runs a manifest of theses into one registry, `crucible report` renders deterministic Markdown, `crucible measurement-gate` verifies Telos creative measurement packets, and `crucible mcp` serves 17 tools over stdio, including replay-template generation.
- **Zero third-party runtime dependencies.** The core is pure standard library, Python 3.11+.

## How a thesis run works

`crucible run` takes one thesis and produces a packet a reviewer can check
without rerunning anything, and without trusting the run that made it.

<p align="center"><img src="https://raw.githubusercontent.com/HarperZ9/crucible/main/docs/art/thesis-lifecycle.svg" alt="Eight stages from a registered thesis to a self-contained review packet: thesis, steelman, measure, cohesion, verdict, registry, recheck, packet. A round that is not cohesive reflects on the weakest axis and re-measures it. The verdict is a pure function of the measurement and ends as match, drift or unverifiable." width="100%"></p>

Two edges carry the design. The one that loops back is the refine step: grading
every claim yields a margin, the harmonic mean of those margins is the cohesion,
and a round that is not cohesive names its weakest axis and measures that axis
again rather than reporting a thesis that only half held. The one that does not
loop is `verdict_for`, which is a pure function of a deviation and a tolerance.
No model sits in it, so a fluent assertion has no route into a rechecked result,
and an axis that could not be measured reads UNVERIFIABLE instead of holding.

## See it work, step by step

The [animated explainer](https://harperz9.github.io/repo-explainers/crucible.html)
walks through the bundled binary-search thesis through steelman, measurement, the pure verdict function for each claim, the sealed registry and the recheck that catches a flipped verdict. Every value on it is output from this repository. Its
source is [docs/explainer/index.html](docs/explainer/index.html).

## Watch

[![A passing check can still be wrong: a narrated film, 2 min 24 s](https://harperz9.github.io/media/explainers/passing-check/poster.jpg)](https://harperz9.github.io/explainers.html#passing-check-h)

**[A passing check can still be wrong](https://harperz9.github.io/explainers.html#passing-check-h)** (2 min 24 s, narrated, captioned). Crucible steelmans each claim before it measures, because a pass alone can hide a weak check. The film page carries the transcript, the sources and recall questions.

## Scripted demo from a clone

The demo script lives in the repository. The package does not include it:

```bash
git clone https://github.com/HarperZ9/crucible
cd crucible
pip install -e ".[dev]"
python examples/demo.py
```

```text
thesis "Binary search comparison bounds": 3 claims, seal bd7404c02eb2...
  MATCH        deviation 0 within tolerance 0.5
  DRIFT        deviation 8 exceeds tolerance 0.5
  UNVERIFIABLE claim states no falsification condition
counts: MATCH 1  DRIFT 1  UNVERIFIABLE 1
assessment seal 07dafef03f5c..., verified True
after flipping a DRIFT to a MATCH, verified False  <- caught
```

Add `--json` for the machine-readable run record, `--substrate crucible-examples/substrate-binary-search.json` in place of `--measurements` to measure through the table oracle, and `--bundle DIR` to write a cleanroom review packet. A visual verdict surface lives at [`examples/crucible-demo.html`](examples/crucible-demo.html).

## A worked example

A thesis is claims plus falsification conditions:

```json
{
  "title": "Binary search comparison bounds",
  "disposition": "publishable",
  "claims": [
    {
      "text": "binary search over a sorted array of 1024 elements does at most 11 comparisons",
      "falsification": "a measured worst-case comparison count above 11 for n=1024"
    },
    {
      "text": "binary search is more elegant than linear search",
      "falsification": ""
    }
  ]
}
```

<p align="center"><img src="https://raw.githubusercontent.com/HarperZ9/crucible/main/docs/art/verdict-ladder.svg" alt="The seven rungs of crucible's verdict function, in the order it checks them. A claim with no falsification condition, no measurement, a measurement bound to a different claim, a deviation that is not a number, or a tolerance that was widened after the claim sealed one all return UNVERIFIABLE. A deviation within tolerance returns MATCH, and that row carries the mark because it is the only rung on which a claim stands. A deviation over tolerance returns DRIFT." width="100%"></p>

The first claim is measurable: a measurement row binds to it by content hash, records a deviation and a tolerance, and the verdict follows. The second claim states no falsification condition, so it is UNVERIFIABLE by construction, and the assessment says exactly which evidence class is missing. Run it, bundle it, and validate the packet:

```bash
crucible run thesis.json --measurements measurements.json \
  --registry .crucible-registry --bundle reports/my-run
crucible review reports/my-run
```

The bundle gives a verifier only the spec and the artifact, with packet-relative paths. `review` fails closed on missing files, extra context, a `spec.json` that drifted from the run record, or a `report.md` that no longer renders from `run.json`.

To gate pull requests on the registry:

```bash
crucible ci .crucible-registry --write-baseline crucible-baseline.json   # on a known-good commit
crucible ci .crucible-registry --baseline crucible-baseline.json --out crucible-ci.md
```

A regression is a claim moving MATCH to DRIFT, becoming UNVERIFIABLE, or dropping out of the verified-latest set. The baseline seals its own cells, so a hand-edited baseline is rejected on load. The Markdown summary is deterministic and references the assessment seal behind every cell.

## Command surface

| Command | What it does |
| --- | --- |
| `crucible run THESIS --measurements F \| --substrate F` | full loop in one session; `--bundle DIR` writes a review packet |
| `crucible register / assess / steelman / measure` | the individual loop stages |
| `crucible review BUNDLE` | validate a cleanroom packet before verifier handoff |
| `crucible refine CONFIG` | rounds of substrate refinement toward cohesive verification |
| `crucible drift DIR` | classify claim movement between the latest two assessments |
| `crucible ci DIR` | regression gate against a sealed baseline |
| `crucible recheck DIR` | inspect, template, or replay oracle measurement descriptors |
| `crucible registry list\|verify\|stats\|search\|prune` | registry operations, including `--require-witnessed-match` |
| `crucible verdicts DIR [--verify]` | list or re-derive witnessed assessments |
| `crucible report DIR` / `crucible batch MANIFEST` | Markdown reports; manifest runs into one registry |
| `crucible export THESIS` | publication-gated export; fenced material is refused at the edge |
| `crucible measurement-gate PACKET` | verify a Telos creative measurement packet |
| `crucible status / doctor / demo` | status envelope, readiness checks, demo pointer (`--json`) |
| `crucible pairwise FILE` / `decompose FILE` / `views FILE` | both-order pairwise verdicts, typed sub-questions, minority-preserving summaries |
| `crucible mcp` | serve the 17 crucible tools over MCP stdio, including `crucible.recheck_template` |

Every command works identically from a source checkout via `python -m crucible`.

## Extending the seams

The steelman and measure stages are seams with a stable API shape. Defaults are Null (propose nothing, measure nothing, UNVERIFIABLE), and the shipped edges include:

- `TableMeasure`: offline deviation against a provided substrate table, no model.
- `SubprocessSteelman` / `SubprocessMeasure`: configured commands over bounded JSON stdin/stdout, with timeouts, no shell strings, minimal environment, and output caps.
- `TelosMeasure`: consumes `telos.witnessed-artifact/v1` envelopes and re-runs the named verifier rather than trusting the carried certificate.
- `GatherDigestMeasure` / `IndexMeasure`: sealed [gather](https://github.com/HarperZ9/gather) digests as evidence, and `index.verification/1` records replayed against graph packs.
- `JudgeMeasure`: rubric-scored LLM judging behind an injectable backend, deterministic stub in tests, null by default.
- `ProofMeasure`: a proof or type checker (Lean, Coq, a type checker, any command) as the oracle for formal claims. It runs the checker over the claim's artifact: an accepted proof is MATCH, a rejected one DRIFTs, and a checker that is absent or errors is UNVERIFIABLE, fail-closed, so an unrun checker never reports a proof as holding. The measurement binds the exact command and the artifact hash, so a stranger replays the identical check. This is the oracle for the north star, verified discovery in math.

All edges map into the same `Measurement` to `verdict_for` spine. The verdict step never changes.

## Documentation

- [docs/INTRODUCTION.md](docs/INTRODUCTION.md): what crucible is, core concepts, and a first-ten-minutes walkthrough.
- [ARCHITECTURE.md](ARCHITECTURE.md): module layout and the pure/impure boundary.
- [USAGE.md](USAGE.md): commands and the interop boundary.
- [docs/ENTERPRISE-READINESS.md](docs/ENTERPRISE-READINESS.md): the host-integration contract for unattended agent workflows.
- [docs/RELEASE-READINESS.md](docs/RELEASE-READINESS.md): the 1.0 gate checklist.
- [CHANGELOG.md](CHANGELOG.md): per-release detail, including what is merged but not yet on PyPI.
- [SECURITY.md](SECURITY.md): how to report a vulnerability privately, and the supported versions.

## Status

`crucible-bench 1.6.0` covers the full loop, one-command runs, cleanroom review packets, oracle replay, registry operations, creative measurement gates, and the MCP bridge, plus MCP replay-template parity, the CI regression gate, LLM-as-judge, missing-evidence explanations, ill-posed measurement warnings, and the MATCH-provenance gate. 1.6.0 changes the README and package metadata only. 1.5.0 adds both-order pairwise judging, decomposed claims and minority-preserving summaries, with measured results in `docs/benchmarks/judging-v1`. 1.3.0 seals the tolerance that decides each verdict and fixes the verdict-integrity defects listed in the changelog; upgrade from 1.2.0 or earlier. Crucible can take [gather](https://github.com/HarperZ9/gather) digests as evidence, and its verdict packets can be replayed by any tool that reads the registry format.

## Why it matters

Everything above reduces to one property: a verdict is a pure function of a sealed record, so anyone holding the record can recompute it, and a tampered claim, measurement, or baseline is caught by re-hashing the record. Nobody has to take the author's word for it.

## License

Crucible is under the Functional Source License, Version 1.1, MIT Future License (FSL-1.1-MIT). You may use, copy, change and redistribute it for any purpose except a product or service that competes with Crucible. Each release converts to the MIT license two years after it is published. See [LICENSE](LICENSE) for the exact terms.

## Work with it

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

Keep the README, package metadata, and examples aligned with current behavior before opening a PR.

## What this believes

This tool is one tool in a family that holds a single belief steady across
every surface: knowledge open to anyone who can attain the means; acceptance
decided by external checks, never reputation; every result re-runnable;
honest nulls first-class; ownership earned by comprehension; learning woven
into the work. The full text lives in [CREDO.md](CREDO.md).
The long form of this belief: [The Unbundling](https://github.com/HarperZ9/flywheel/blob/main/docs/essays/2026-07-13-the-unbundling.md).

---

Built by **[Zain Dana Harper](https://harperz9.github.io)** in Seattle: evidence-first tools that leave a re-checkable artifact behind. More tools are listed at [harperz9.github.io](https://harperz9.github.io).

## Local client packages

The optional client bundle defaults to a read-only MCP profile with an explicit
workspace selected at launch. You can grant one fixed measurement command
at launch for witnessed benchmarks. That child runs with OS user permissions;
it is not sandboxed. See [client package setup](client-plugin/README.md).
Windows x64 MCPB and ZIP bundles include their runtime; source plugins require
Python 3.11+. The full CLI/MCP retains advanced operations. Client-specific
installation and marketplace acceptance require separate verification.
