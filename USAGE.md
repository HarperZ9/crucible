# Crucible Usage

Crucible evaluates claims, measurements, and verdicts with recheckable evidence
packets. It is built for humans and agents that need to know why a conclusion
held, drifted, or became unverifiable.

## Install

```bash
python -m pip install crucible-bench
```

From a source checkout:

```bash
python -m pip install -e ".[dev]"
```

## Run

```bash
crucible status --json
crucible doctor --json
crucible demo --json
crucible --help
```

The same package can be exercised from source with:

```bash
python -m crucible --help
```

## MCP

Use `crucible mcp` when a host needs the measurement and verdict tools over
stdio.

```bash
crucible mcp
```

## Verify

```bash
python -m pytest
python examples/demo.py
```

For public/developer delivery checks:

```bash
python -m public_surface_sweeper . --workspace --json
```

## Replay oracle measurements

Create a replay template from a witnessed assessment, let the named oracle fill
its measurement rows, and submit the completed pack against the same registry:

```bash
crucible recheck REGISTRY --template replay-template.json
crucible recheck REGISTRY --pack replay-pack.json --json
```

Keep the template's top-level `assessment` object unchanged in the completed
pack. The CLI requires its thesis ID (`thesis_id`), assessment seal
(`assessment_seal`), and measurement seal (`measurement_seal`) to match the
selected assessment; a missing, malformed, or mismatched binding is rejected
before any measurement replay runs.

## Boundary

Crucible should expose claim ids, criteria, verdicts, evidence hashes, and
redacted references. Do not require raw prompts, private evidence, verifier
internals, or full result payloads for interop.
