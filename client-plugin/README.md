# crucible local client package

Crucible checks claims against evidence files in a folder you choose and returns a verdict for each claim: MATCH, DRIFT or UNVERIFIABLE.

## Try it

- Assess the claims in thesis.json against measurements.json in my workspace.
- Which claims came back UNVERIFIABLE, and what evidence is missing?
- Verify the measurement packet packet.json against criteria.json.

## Details

Assess local claims and measurement evidence, with an optional launch-approved
measurement command. The default profile is read-only.
It requires an explicit workspace at launch and refuses other tools, path escapes,
links, and tool-supplied permission grants. It does not read ambient grants.
Concurrent filesystem mutation is outside this convenience boundary; it is not
an operating-system sandbox.

The source plugin requires Python 3.11 or later on your PATH as `python3`.
Claude Code asks for the readable workspace when you enable the plugin, along
with the two optional measurement-command settings described below. Other
clients that read the portable `mcp.json` or `.codex-mcp.json` still need
REPLACE_WITH_ABSOLUTE_WORKSPACE replaced with the directory you want the client
to read. Keep the complete extracted bundle. The Windows x64 binary MCPB and ZIP include Python;
open the MCPB in a compatible desktop client and choose a workspace directory,
or configure the ZIP's server executable with --workspace ABSOLUTE_DIRECTORY.
No model, API key, hosting account, automatic client configuration, or publisher
compute is included. Your calling model and client retain their own costs.

Network retrieval and persistent-state operations remain on
the full CLI/MCP surfaces documented in USAGE.md. Do not infer a grant from a
request, document or plugin installation. Public marketplace acceptance, macOS,
Linux native bundles and installed-client compatibility remain unverified.

The local launcher denies Python process and socket operations by default. These
controls are defense in depth for this bundled stdlib tool surface.

## Data and network

| Question | Answer |
| --- | --- |
| What it reads | Thesis, measurement, packet and criteria JSON files you name, resolved inside the workspace you chose. Paths outside it, links, reparse points, network paths and files over 8 MB are refused. |
| What it stores | Nothing. The default profile writes no files. With the optional measurement command on, it writes two temporary files for the child's input and output and deletes them when the call returns. |
| Network calls | None. The launcher denies Python socket operations. The optional measurement command you approve is a separate program and can reach any destination its own code chooses; Crucible does not contact it over the network. |
| Telemetry | None. |
| Retention | Results go back to your client in the tool response. Crucible keeps nothing after the call returns. |

## Optional measurement process

In Claude Code's plugin settings or a compatible MCPB client's setup, leave
**Allow this measurement command** off and **Fixed measurement command (JSON argv)**
empty for the read-only default.
To enable a reviewed oracle, enter its fixed JSON argv and turn on consent.
The launcher rejects a command without consent, consent without a command, or
malformed values. These fields become explicit launch arguments; they do not
create environment-based permission grants.

To run an operator-reviewed measurement oracle, add both `--allow-process` and
`--measure-command` to the server launch arguments. The second flag takes one JSON
array of argv strings, for example `["/absolute/python", "-I", "-S", "/absolute/oracle.py"]`.
Use an existing absolute executable path. No shell string or PATH lookup is accepted.
The launcher exposes `crucible.benchmark` only with this grant; its sole argument
is a thesis JSON path inside the selected workspace. Calls cannot select a different
command, environment, network permission, or output destination.

The fixed oracle reads `crucible.measure/v1` JSON on stdin and returns measurement
JSON on stdout, using the existing `SubprocessMeasure` contract in `USAGE.md`.
The response contains measurements, verdicts and a witnessed assessment. Each
request accepts at most 16 claims, with 10 seconds and 65,536 output bytes per
claim. The child receives only operating-system and temporary-directory variables;
provider keys, endpoint settings and ambient permission grants are omitted.

Review the executable and its arguments before enabling this mode. The approved
child has your OS user permissions and can write files, launch descendants or
access the network. Parent socket denial does not constrain a child, and the time
limit applies to the direct child. This is not an OS sandbox. A valid assessment
receipt does not prove that the oracle or its measurement is correct.
