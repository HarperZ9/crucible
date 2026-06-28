# Crucible Enterprise Readiness

Crucible is the enterprise verification edge: it turns claims, packets, and agent outputs into MATCH, DRIFT, or UNVERIFIABLE using measurements that can be replayed outside the model.

This guide aligns the flagship with Project Telos context envelopes and action receipts. The goal is unattended agent work that can be left running and later inspected: what context the agent saw, what exact material it relied on, what it changed, what verified, and what remained unverifiable.

## Enterprise Role

- Bind a thesis or action claim to explicit measurements and tolerances.
- Keep the verdict step pure: the measurement decides, not model confidence.
- Create cleanroom review packets and replay packs that a verifier can re-run without hidden conversation context.

## Host Commands

- `crucible status --json` and `crucible doctor --json` for host readiness.
- `crucible assess THESIS --measurements MEASUREMENTS --json` for a direct verification pass.
- `crucible run THESIS --registry DIR --bundle DIR --json` for an operator packet.
- `crucible review BUNDLE --json` before verifier handoff.
- `crucible recheck REGISTRY --json` or `--pack` for oracle replay.
- `crucible mcp` exposes the same host-callable spine for assess, recheck, run, review, report, batch, registry, drift, refine, and verdict inspection.

## Context Envelope Contribution

- Context envelopes should include the exact thesis, measurements, assessment seal, and replay descriptor refs.
- Summaries may describe verdicts, but the authoritative context is the sealed assessment and measurement rows.
- UNVERIFIABLE remains a first-class outcome when measurements, criteria, or replay descriptors are missing.

## Action Receipt Contribution

- Verification verdict is the native `MATCH | DRIFT | UNVERIFIABLE` output.
- Policy and publication gates should join to the action receipt as policy decisions, not prose-only notes.
- Compensation or correction is a new assessment/review event, not mutation of the old verdict row.

## Readability Gate

Enterprise agent output should be easier for the next agent and a human reviewer to continue:

- Keep patches small enough to review and tied to one bounded work item.
- Prefer named helpers and domain terms over dense inline logic.
- Preserve public interfaces unless the receipt explains why they moved.
- Leave tests, command output, changed files, and next action in the handoff.
- Mark missing source refs, stale packets, failed tests, and verifier abstentions as UNVERIFIABLE instead of guessing.

## Platform Boundary

The flagship remains usable alone through CLI JSON and as part of a larger surface through MCP with parity for the main operator workflow. OpenAI, Anthropic, IDE, CLI, TUI, and application hosts should consume the same tool outputs and receipt fields rather than reimplementing flagship behavior.

See Project Telos `project-telos.context-envelope/v1` and `project-telos.action-receipt/v1` for the shared cross-tool contract.
