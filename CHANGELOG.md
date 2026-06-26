# Changelog

All notable changes to crucible. Versions follow semantic versioning; each minor release is built
behind a feature branch and reviewed before merge.

## 1.1.0

Operator run surface.

- CLI: `crucible run THESIS --registry DIR (--measurements FILE | --substrate FILE)` runs the
  steelman, measurement, witnessed assessment, and disk recheck path as one session.
- `crucible run --json` emits a complete run record with thesis metadata, refutations, assessment,
  verdicts, disk recheck status, and optional report path.
- `crucible run --report FILE` writes the deterministic Markdown assessment report for the same
  witnessed assessment, while `--out FILE` writes the JSON run record with exclusive creation.
- `crucible run --bundle DIR` creates a self-contained cleanroom review packet containing
  `spec.json`, `run.json`, `report.md`, and `review.md`, refusing pre-existing packet directories.
- Bundle run records carry a machine-readable verifier boundary: cleanroom mode, allowed packet
  inputs, excluded worker context, and the checkability rule for underspecified specs.
- CLI: `crucible recheck REGISTRY [--template FILE] [--pack FILE]` lists descriptor-bearing
  measurement rows, writes replay pack templates, and validates finished oracle replay packs without
  creating a second verdict path.

## 1.0.0

Stable flagship floor.

- Assessment integrity now seals verdict margin and grounds, and `recheck_assessment` rejects stored
  verdict rows or summary counts that do not re-derive from the thesis and measurements.
- Measurement rows now persist and seal `measured_at`, and Telos-backed measurements persist a
  `telos:<verifier>` replay descriptor so oracle-level reassessment checks a real stored row.
- Drift and registry status/search now use the latest verified assessments, falling back past invalid
  tail rows instead of trusting or hiding history.
- Registry body verification now reports non-file or unreadable object paths as CORRUPT instead of
  raising, and registration rejects pre-existing non-file object paths.
- Registry prune now applies the registry realpath guard before scanning or deleting object paths, so
  escaped, symlinked, or junctioned object roots are refused before unlink.
- Assessment and verdict records, CLI JSON, and Markdown reports now carry the sealed thesis
  disposition, keeping publication posture visible in witnessed outputs.
- `refine.margin()` is public and reused by grading, matching the documented normalized-margin
  contract.
- Index/Gather interop canonical hashing now uses unescaped sorted JSON (`ensure_ascii=False`) for
  non-ASCII graph-pack content.
- The registry rejects duplicate thesis ids with different seals, refuses symlinked storage paths,
  and keeps object writes on unique temp files inside the registry root.
- Batch manifests keep thesis, measurement, and substrate paths inside the manifest bundle; path-like
  missing refs fail closed without rejecting dotted registry ids; report writes use index-prefixed
  filenames and exclusive creation.
- Subprocess-backed edges use a clean default environment, discard unbounded stderr, write stdout to a
  temporary file, actively terminate children that exceed the response cap, and still reject shell
  strings.
- CLI JSON loaders reject non-object top-level payloads with clean errors, ambiguous claim text refs
  are rejected, and refine thresholds reject negative or non-finite values cleanly.
- Release workflows remove manual PyPI dispatch, pin external GitHub Actions by commit SHA, and
  install pinned build tooling plus the pinned build backend from `requirements-release.txt`.
- README and readiness docs record the clean verifier rule: verifier receives only the original spec
  and artifact, never the worker context or reasoning trace.

## 0.14.1

Batch hardening patch.

- Batch report filenames now include the manifest job index, so duplicate or colliding job IDs do not
  overwrite earlier reports.
- Batch thesis, measurement, and substrate references now fail closed when a manifest-relative or
  absolute file is missing instead of falling back to the caller's current working directory.

## 0.14.0

Batch assessment workflow.

- `crucible.batch_cmd`: adds a manifest runner that assesses multiple thesis jobs into one
  content-addressed registry.
- Manifest jobs accept either explicit measurements or a substrate oracle file, preserving the same
  grounded measurement -> verdict spine as the single-thesis commands.
- CLI: `crucible batch MANIFEST --registry DIR [--reports DIR] [--json]` emits a row per job and can
  write one deterministic Markdown report per assessment.
- Readiness coverage now runs the batch command through the bundled example thesis surface.

## 0.13.0

Markdown assessment reports.

- `crucible.report`: adds `render_assessment_report`, a deterministic Markdown renderer for one
  witnessed assessment and its thesis.
- Reports include assessment/thesis seals, outcome counts, integrity checks, per-claim verdicts,
  measurement evidence, optional recheck descriptors, and unmeasured claims.
- CLI: `crucible report REGISTRY [--index N] [--out FILE]` renders the latest assessment by default
  and can write the Markdown body to disk.
- Public API: exports `render_assessment_report`.

## 0.12.0

Measurement recheck descriptors.

- `Measurement` now accepts an optional `recheck` descriptor, preserved at the end of the dataclass so
  existing positional construction stays compatible.
- Assessments persist and seal `measured_at` plus `recheck` descriptors when present; legacy
  assessment rows without descriptors keep their previous replay shape and still verify.
- `recheck_measurements` replays descriptor-bearing measurement rows through a caller-supplied oracle
  registry and reports checked, skipped, missing, mismatched, and failed replays.
- `recheck_assessment(..., measurement_replayers=...)` can include an oracle-level measurement replay
  result alongside the existing seal/thesis/verdict re-derivation checks.
- Public API: exports `recheck_measurements`.

## 0.11.0

Gather/index protocol interop preview.

- `crucible.ecosystem_measure`: adds `verify_gather_digest`, `receipt_matches`,
  `verify_index_verification`, and `canonical_sha` for consuming sibling-product JSON contracts
  without importing sibling packages.
- `GatherDigestMeasure` maps a verified Gather digest plus receipt selector into a crucible
  `Measurement`: receipt present -> MATCH input, receipt absent -> DRIFT input, malformed or missing
  digest -> UNVERIFIABLE input.
- `IndexMeasure` maps an `index.verification/1` record plus supplied graph pack into a crucible
  `Measurement`: reproduced MATCH -> MATCH input, reproduced REFUTED/DRIFT -> DRIFT input, missing
  or unreplayable pack -> UNVERIFIABLE input.
- Public API: exports `GatherDigestMeasure`, `IndexMeasure`, `verify_gather_digest`,
  `verify_index_verification`, `receipt_matches`, and `canonical_sha`.

## 0.10.0

Telos witnessed-artifact interop preview.

- `crucible.telos_measure`: adds `verify_telos_artifact`, `is_telos_artifact`, `check_content`, and
  `TelosMeasure` for consuming `telos.witnessed-artifact/v1` envelopes through the Measure seam.
- `TelosMeasure` maps a re-run Telos verifier result into a crucible `Measurement`: verified -> MATCH
  input, refuted or drifted -> DRIFT input, absent or unregistered proof -> UNVERIFIABLE input.
- Public API: exports `TelosMeasure`, `verify_telos_artifact`, `is_telos_artifact`, and
  `check_content`.

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
  stated falsification as the test, or flags a claim that states no falsification as unrefutable.
  Custom refuters plug in through the same protocol.
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
