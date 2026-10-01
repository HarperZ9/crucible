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

The quickstart inputs ship with the package. `crucible examples --out DIR` writes them to a new
folder (it refuses one that already exists), ready for `crucible run`:

```bash
crucible examples --out crucible-examples
crucible run crucible-examples/thesis-binary-search.json   --measurements crucible-examples/measurements-binary-search.json   --registry .crucible-registry
```

The same package can be exercised from source with:

```bash
python -m crucible --help
```

## MCP

Use `crucible mcp` when a host needs the measurement and verdict tools over
stdio. `crucible.recheck_template` returns the same `crucible.replay-template/1`
object that `crucible recheck --template` writes, without writing a local file.
`crucible.recheck` also accepts `template: true`; `pack` and `template` are
exclusive. Replay results with `ok: false` are evaluation failures, not MCP
transport errors.

```bash
crucible mcp
```

## Verify

```bash
python -m pytest
python examples/demo.py
python scripts/check_version_sites.py .
python -m build && python scripts/smoke_wheel.py dist/*.whl
```

`check_version_sites.py` fails when any file states a different version from `pyproject.toml`.
`smoke_wheel.py` installs a built wheel into a fresh environment and checks the version, the
sealed-tolerance probe, the packaged examples and the MCP server.

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

The template output schema is `crucible.replay-template/1`; an external replay
producer emits `crucible.replay-pack/1`. If a pack has a `schema` field, it must
be exactly that value; schema-less legacy packs remain accepted, while template
or unknown schemas are rejected.

Each new template includes a privacy-bounded `replay_binding` with schema
`crucible.replay-set/1`, descriptor and skipped counts, and a SHA-256 digest.
To recompute it, form one exact `{recheck, expected_measurement}` object per
descriptor-bearing replay, serialize each with compact sorted-key JSON
(`ensure_ascii=False`, `separators=(',', ':')`), sort by those serialized forms,
serialize the resulting list with the same settings, and hash its UTF-8 bytes.
Descriptorless rows and their evidence are never included; the top-level
assessment triple binds the full sealed assessment, which Crucible independently
verifies.

Keep the template's top-level `assessment` object unchanged in the completed
pack. The CLI requires its thesis ID (`thesis_id`), assessment seal
(`assessment_seal`), and measurement seal (`measurement_seal`) to match the
selected assessment; a missing, malformed, or mismatched binding is rejected
before any measurement replay runs. Preserve `replay_binding` when emitting a
pack; Crucible compares it to the expected canonical value. Older
assessment-bound packs that omit `replay_binding` remain accepted.

## Boundary

Crucible should expose claim ids, criteria, verdicts, evidence hashes, and
redacted references. Do not require raw prompts, private evidence, verifier
internals, or full result payloads for interop.

## Local client package candidate

The optional client bundle defaults to a read-only MCP profile with an explicit
workspace selected at launch. An operator can grant one fixed measurement command
with `--allow-process --measure-command '["/absolute/oracle", "fixed-argument"]'`.
The `crucible.benchmark` tool then accepts a workspace-local `thesis` path and
uses `SubprocessMeasure` plus witnessed assessment. The approved child is trusted
code with OS user permissions, not sandboxed code. See
[client package setup](client-plugin/README.md) for limits and configuration.
Windows x64 MCPB and ZIP bundles include their runtime; source plugins require
Python 3.11+. The full CLI/MCP retains advanced operations. This profile alone
does not qualify the full product's mature workflows or marketplace acceptance.
