# Changelog

All notable changes to crucible. Versions follow semantic versioning; each minor release is built
behind a feature branch and reviewed before merge.

## 0.9.0

1.0-readiness hardening.

- Examples: the bundled demo and JSON examples are now regression-tested through the public CLI.
- CLI surface: help output is covered for the shipped commands and registry actions.
- Docs: adds a release-readiness checklist for the 1.0 review gate.

## 0.8.0

Optional subprocess-backed seam adapters.

- `crucible.subprocess_edges`: adds `SubprocessSteelman` and `SubprocessMeasure`, stdlib-only adapters
  for configured commands that exchange bounded JSON over stdin/stdout.
- Safety posture: commands must be argv sequences rather than shell strings; request and response
  sizes are bounded; timeouts are enforced; claim identity and producer labels are stamped locally.
- Public API: exports `SubprocessSteelman` and `SubprocessMeasure`.

## 0.7.0

Registry operations for a growing corpus.

- `crucible.registry_ops`: adds `registry_stats`, `search_theses`, and `prune_objects` for registry
  health, recall, and object-store hygiene without changing the durable storage contract.
- CLI: `crucible registry stats`, `crucible registry search`, and `crucible registry prune` summarize
  the corpus, search by scope/status/latest verdict, and report orphaned claim bodies. Prune is
  dry-run by default and deletes only with `--apply`.
- Public API: exports `registry_stats`, `search_theses`, and `prune_objects`.

## 0.6.0

Publication-gated thesis export.

- `crucible.gate`: adds `gate_check`, `export_guard`, and `export_thesis`. Fenced disposition and
  explicit fenced/restricted markers fail closed at the public export edge.
- CLI: `crucible export THESIS` emits the public thesis contract for publishable theses, resolves
  thesis ids from a registry with `--registry`, and refuses fenced theses with a clean error.
- Public API: exports `gate_check`, `export_guard`, and `export_thesis`.

## 0.5.0

Drift tracking across witnessed assessment rounds.

- `crucible.drift`: compares two assessments of the same thesis and classifies each claim as held,
  moved, improved, or regressed. Numeric margins decide direction; unrankable transitions such as
  UNVERIFIABLE to MATCH are reported as moved.
- CLI: `crucible drift REGISTRY` compares the latest two stored assessments, with human and JSON
  output and clean errors for too-short or mixed-thesis histories.
- Public API: exports `DriftRow`, `DriftReport`, and `drift_track`.

## 0.4.0

The refine loop: margin, cohesion, reflection, and re-iteration over a thesis.

- `crucible.refine`: a zero-dependency refinement primitive with graded criteria, harmonic-mean
  cohesion, reflect-weakest feedback, and fail-closed handling for broken generators, adjusters, and
  non-numeric measurements.
- `refine_thesis`: points the primitive at a thesis and a `Measure` oracle, grading each claim by its
  normalized measurement margin and returning a `RefineReport` with final verdicts and the cohesion
  trajectory.
- CLI: `crucible refine <config.json>` runs ordered substrate rounds, stops on a cohesively verified
  thesis, or reports the weakest claim when the budget is spent.
- Public API: exports `GradedCriterion`, `Reflection`, `RefineOutcome`, `RefineReport`, `cohesion`,
  `refine`, and `refine_thesis`.

## 0.3.0

The measure seam: a sound oracle decides a claim against a substrate. This is where the verdict is
grounded, the half the differentiator names.

- `crucible.measure`: a `Measure` protocol and a `MetricSpec` (the value a claim predicts, the
  tolerance, the substrate key to observe, and the metric). `verdict_for` already consumes the
  `Measurement` an oracle produces, so there is still no model in the verdict step.
- `NullMeasure`: the standing default, produces no measurement (UNVERIFIABLE); it invents nothing.
- `TableMeasure`: a deterministic, offline oracle. The deviation is the absolute or relative
  difference between the observed value (from the substrate) and the value the claim predicts. An
  unknown claim or a missing observation is UNVERIFIABLE, fail-closed. The shape a real oracle (the
  Telos verifier, a proof or type checker) plugs into.
- `measure_thesis` runs an oracle over every claim in a thesis.
- CLI: `crucible measure <thesis> --substrate FILE` measures each claim and witnesses the verdicts; the
  oracle-produced measurements re-derive from disk via `verdicts --verify`.
- Refactor: the registry-inspecting commands moved to `crucible.registry_cmd` so no module exceeds the
  size budget.

## 0.2.0

The steelman seam: adversarial refutation as a pluggable shape, the conjecture-and-attack half of
judgment.

- `crucible.steelman`: a `Steelman` protocol and a `Refutation` (the proposed attack plus the
  measurable test that would settle it). Adversaries propose what to test; they do not decide.
- `NullSteelman`: the standing default. Deterministic and invents nothing: it surfaces the claim's own
  stated falsification as the test, or flags a claim that states no falsification as unrefutable. A
  model edge (a real independent refuter) plugs in through the same protocol later.
- `steelman_thesis` runs a steelman over every claim in a thesis, returning the proposed tests in
  claim order, ready to feed the measurement step.
- CLI: `crucible steelman <thesis>` prints each claim's challenge and the test it proposes.

## 0.1.0

The P1 foundation: the verdict spine and the witnessed, re-derivable record.

- `crucible.claim`: a `Claim` carrying a content-hash receipt over its assertion and falsification
  condition; `make_claim` computes it and `Claim.verify()` re-hashes to catch tampering.
- `crucible.thesis`: a `Thesis` with a seal binding its claims, title, and disposition (so a fenced
  thesis cannot be relabelled publishable undetected); the seal is over the set, so reordering is not
  a change.
- `crucible.verdict`: the differentiator. `verdict_for` is a pure MATCH / DRIFT / UNVERIFIABLE
  decision from a `Measurement`, with no model in the verdict step. UNVERIFIABLE is fail-closed
  (no measurement, an unmeasurable deviation, a non-positive tolerance, an unfalsifiable claim, or a
  measurement bound to a different claim all read as UNVERIFIABLE, never as holding).
- `crucible.registry`: a content-addressed registry. Claim bodies are deduped and traversal-guarded;
  `verify` reports MATCH / MISSING / CORRUPT; `verify_seals` catches a swapped or relabelled claim a
  body check would miss; a tampered thesis is refused on load; re-registration is idempotent.
- `crucible.assess`: a witnessed `Assessment` that persists its verdicts and measurements.
  `verify_assessment` recomputes the seals from the stored data; `recheck_assessment` re-derives each
  verdict from the thesis and the measurements, so a verdict cannot be asserted, only computed.
- `crucible.cli`: `register`, `assess`, `registry list|verify`, and `verdicts [--verify]`.
- Zero third-party dependencies; an offline `examples/demo.py`; ruff and mypy clean.
