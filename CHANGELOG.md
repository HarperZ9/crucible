# Changelog

All notable changes to Crucible. Versions follow semantic versioning; each minor release is built
behind a feature branch and reviewed before merge.

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
