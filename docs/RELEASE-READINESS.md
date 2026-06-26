# Release readiness

This checklist is the standing gate before 1.0. It records what must stay true as crucible moves
from release-candidate shape to stable flagship floor.

## Verified surface

- The public CLI commands are covered: `register`, `assess`, `steelman`, `measure`, `registry`,
  `verdicts`, `drift`, `report`, `batch`, `export`, and `refine`.
- Registry actions are covered: `list`, `verify`, `stats`, `search`, and `prune`.
- Bundled examples run through the public CLI, including manual measurements, table measurements,
  refinement, registry stats/search, report rendering, the batch manifest example, and
  publication-gated export.
- The offline `examples/demo.py` runs as a script and demonstrates MATCH, DRIFT, UNVERIFIABLE, and
  seal tamper detection.

## Stability checks

- `python -m pytest -q`
- `python -m ruff check src tests`
- `python -m mypy src\crucible`
- `python -m build`
- `python -m twine check dist\*`

## 1.0 review gate

- Correctness review: verdicts still follow from measurements, and assessments still re-check from
  disk.
- Security review: registry paths stay traversal-guarded, subprocess edges avoid shell strings, and
  fenced material cannot pass the export edge.
- Docs and honesty review: README, architecture, changelog, and examples describe only shipped
  behavior and keep `crucible` lowercase as the flagship name.
