# Security Policy

## Supported versions

`crucible-bench` is distributed on PyPI. Security fixes go into the current release line as a new
release. Older lines are not backported.

| Version | Supported |
|---------|-----------|
| 1.3.x   | Yes       |
| < 1.3   | No        |

1.2.0 and earlier carry the verdict-integrity defects fixed in 1.3.0: a measurement could widen a
claim's tolerance after the seal and still re-derive MATCH, and `doctor` reported MATCH for checks
it never ran. See the 1.3.0 entry in [CHANGELOG.md](CHANGELOG.md). Upgrade with
`pip install --upgrade crucible-bench`.

## Reporting a vulnerability

Report suspected vulnerabilities privately through GitHub: open the repository's **Security** tab
and choose **Report a vulnerability**, or go straight to
<https://github.com/HarperZ9/crucible/security/advisories/new>. Do not open a public issue, pull
request, or discussion for a security report.

Include:

- the affected version and platform,
- what the issue lets someone do,
- the smallest input or steps that reproduce it.

You will get an acknowledgement, and the fix ships before any public disclosure. Please allow a
reasonable period to remediate before you disclose.

## Scope and trust model

`crucible-bench` is a judgment engine. It registers a thesis, measures it, and emits a verdict per
claim that anyone holding the sealed record can re-derive. The core has no runtime dependencies and
makes no network calls.

- **What counts as a vulnerability here.** Anything that lets a verdict be accepted that the sealed
  record does not support: a MATCH that survives re-derivation without a measurement earning it, a
  tampered record that still verifies, or a check that reports success without running. Path
  escapes from a registry and code execution from data files count too.
- **Child processes.** The `crucible` command and the MCP server start no child process. The
  library edges `ProofMeasure` and `SubprocessMeasure` do: they run a command you configure, with
  your privileges, in the working folder of the calling process. Only configure commands you
  trust, and run measurements that execute external code in a container or other sandbox.
- **Untrusted input.** Thesis files, measurement records, and substrate numbers may come from
  outside sources. crucible treats them as data. The sealing layer is built to fail on tampering;
  it does not make a supplied measurement true.
- **Writes.** Commands write only where their arguments point, and refuse to overwrite an existing
  output file or bundle folder.

## Good practice

- Keep API keys and backend credentials in the environment, never in a thesis, measurement file or
  committed record.
- Seal the tolerance on every new claim (`"tolerance"` in the thesis file). A claim without a sealed
  tolerance keeps the legacy behavior, where a widened tolerance can still re-derive MATCH.
