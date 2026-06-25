# Changelog

All notable changes to Crucible. Versions follow semantic versioning; each minor release is built
behind a feature branch and reviewed before merge.

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
