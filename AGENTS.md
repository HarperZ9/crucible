# Crucible Agent Instructions

## Scope

Crucible is the Project Telos measurement and verdict tool. Changes should make
claims easier to test, recheck, refine, and audit.

## Developer Contract

- Keep measurements, verdicts, packets, and recheck workflows joined by stable
  identifiers.
- Preserve the split between operational decisions and audit verdicts.
- Prefer hashes, references, and compact evidence packets over raw private
  evidence.
- Keep README, `USAGE.md`, `CHANGELOG.md`, and examples current when workflows
  change.

## Verification

Run the targeted slice for the touched surface first:

```bash
python -m pip install -e ".[dev]"
python -m pytest
crucible status --json
crucible doctor --json
```

For delivery-surface changes, also run:

```bash
python -m public_surface_sweeper . --workspace --json
```
