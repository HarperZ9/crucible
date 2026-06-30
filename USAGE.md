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

## Boundary

Crucible should expose claim ids, criteria, verdicts, evidence hashes, and
redacted references. Do not require raw prompts, private evidence, verifier
internals, or full result payloads for interop.
