# Release readiness

This checklist is the standing gate for 1.0 and later release work. It records what must stay true
now that crucible has reached its stable flagship floor.

## Verified surface

- The public CLI commands are covered: `register`, `assess`, `steelman`, `measure`, `run`, `recheck`,
  `registry`, `verdicts`, `drift`, `report`, `batch`, `export`, `review`, and `refine`.
- Registry actions are covered: `list`, `verify`, `stats`, `search`, and `prune`.
- Bundled examples run through the public CLI, including manual measurements, table measurements,
  refinement, one-command runs with cleanroom review packets, oracle replay pack template generation,
  cleanroom bundle validation and report/run matching checks, registry stats/search, report rendering,
  the batch manifest example, and
  publication-gated export.
- The offline `examples/demo.py` runs as a script and demonstrates MATCH, DRIFT, UNVERIFIABLE, and
  seal tamper detection.

## Stability checks

- `pip install -e ".[dev]"`
- `python -m pytest -q --cov=crucible --cov-report=term-missing --cov-fail-under=85`
- `python -m ruff check src tests examples`
- `python -m mypy src\crucible`
- `python -m pip install --requirement requirements-release.txt`
- `python -m build --no-isolation`
- `python -m twine check dist\*`

## 1.0 review gate

- Correctness review: verdicts still follow from measurements, and assessments still re-check from
  disk.
- Security review: registry paths stay traversal-guarded, subprocess edges avoid shell strings, and
  fenced material cannot pass the export edge.
- Docs and honesty review: README, architecture, changelog, and examples describe only shipped
  behavior and keep `crucible` lowercase as the flagship name.
- Verifier separation: the verifier receives only the original spec/readiness docs and the artifact
  under review. It does not receive worker context, reasoning traces, or intermediate steps. If the
  verifier cannot evaluate success from that minimal state, the spec or readiness artifact must be
  tightened before release.
- Release workflow: PyPI publishing is tied to GitHub release publication on `v*` tags, uses trusted
  publishing, pins external GitHub Actions by commit SHA, and installs pinned build tooling plus the
  pinned build backend from `requirements-release.txt`. The artifact can verify the workflow
  declaration; PyPI trusted-publisher registration and GitHub environment protection settings are
  external provider configuration checked at release-operations time, not artifact-only acceptance
  criteria.

## Cleanroom acceptance

The release verifier receives only this readiness file, the original spec, and the artifact checkout.
Lineage notes, prior review history, older CI runs, and external sibling repositories are context, not
acceptance evidence unless their facts are visible in the artifact itself. A `crucible run --bundle`
packet follows the same rule with `spec.json`, `run.json`, `report.md`, and `review.md` only.
`crucible review BUNDLE` validates that boundary before verifier handoff and fails on extra
context files or report content that does not render from `run.json`.

Secret hygiene is mechanical at the release gate: no committed credentials, `.env` stays ignored,
runtime dependencies are empty, and subprocess-backed edges run with explicit clean environment
allowlists instead of inheriting the parent process environment. Caller-supplied measurement evidence
is treated as user data and is persisted only when the caller provides it; crucible does not claim to
classify arbitrary evidence text as secret or non-secret. Oracle replay pack template files are local
handoff skeletons; finished oracle replay pack files are verifier-supplied measurement reproductions
for sealed `recheck` descriptors, not new authority over verdict status.
When a replay pack returns the template assessment block, `crucible recheck --pack` checks
that binding before replay.

Run this stale-language scan before release:

```powershell
rg "before 1\.0|release-candidate|0\.14\.1 on main|IN PROGRESS through 0\.14\.1|workflow_dispatch|pip install --upgrade build twine|model edge|not altered|cannot be forged|cannot be faked" -n -g "!docs/RELEASE-READINESS.md"
```

Run this committed-secret scan before release:

```powershell
rg -n --hidden -i -g "!/.git/" -g "!docs/RELEASE-READINESS.md" -g "!.github/workflows/release.yml" "api[_-]?key|token|secret|password|passwd|authorization|bearer|BEGIN .*PRIVATE KEY|AKIA[0-9A-Z]{16}"
```
