# Security Policy

## Supported versions

`crucible-bench` is distributed on PyPI. Security fixes are applied to the
current release line and published as a new patch release. Older lines are not
backported.

| Version | Supported |
|---------|-----------|
| 1.2.x   | Yes       |
| < 1.2   | No        |

## Reporting a vulnerability

Please report suspected vulnerabilities privately. Do not open a public issue,
pull request, or discussion for a security report.

Send the report to `<SECURITY CONTACT>`. Include:

- the affected version and platform,
- a description of the issue and its impact,
- the minimal steps or input needed to reproduce it.

You can expect an acknowledgement, and we will work a fix before any public
disclosure. Please allow a reasonable period to remediate before disclosing.

## Scope and trust model

`crucible-bench` is a judgment engine. It registers a thesis, measures it against
a substrate, and emits a re-derivable verdict. The core is zero-dependency.

- Subprocess edge: crucible can shell out to run a configured command as part of
  a measurement (the subprocess edge). That command is under your control and
  runs with your privileges. Only configure commands you trust, and run crucible
  as an unprivileged user in a sandbox when a measurement executes external code.
- Untrusted input: measurement records and substrate numbers may come from
  outside sources. Treat author-supplied deviations and records as untrusted
  input and re-check them; the sealing layer is designed to fail on tampering.
- No network by default: the core performs no network calls. Any model or remote
  backend you wire in is your own edge and its credentials are your
  responsibility.

## Good practice

- Keep API keys and any backend credentials in the environment, not in code or
  in a committed record.
- Run measurements that execute commands in a container or other sandbox.
