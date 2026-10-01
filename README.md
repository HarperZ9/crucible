## Marketplace source distribution

This folder packages the source plugin from release 1.4.0. It requires Python 3.11 or later, available as `python3`. It includes the tool source and no model or bundled runtime. The connected client supplies any model used in the conversation.

The separate [Windows x64 native download](https://github.com/HarperZ9/crucible/releases/download/v1.4.0/crucible-client-1.4.0-win-x64.mcpb) includes its runtime. That download is a manual MCPB package and is not part of this source plugin. Directory approval and availability remain unverified.

This branch contains the installable plugin. Build commands in the release README below apply to the [product source tag](https://github.com/HarperZ9/crucible/tree/v1.4.0). DISTRIBUTION.json records the published asset digest and every packaging change; any SOURCE.json describes the original release payload.

# crucible local client package

Assess local claims and measurement evidence, with an optional launch-approved
measurement command. The default profile is read-only.
It requires an explicit workspace at launch and refuses other tools, path escapes,
links, and tool-supplied permission grants. It does not read ambient grants.
Concurrent filesystem mutation is outside this convenience boundary; it is not
an operating-system sandbox.

The source plugin requires Python 3.11 or later. Claude Code asks for the required
workspace folder when it enables this plugin. For portable or generic MCP clients,
replace REPLACE_WITH_ABSOLUTE_WORKSPACE in their MCP configuration with the
directory you want the client to read, and select your installed Python executable. Keep the
complete extracted bundle. The Windows x64 binary MCPB and ZIP include Python;
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

## Optional measurement process

In a compatible MCPB client's setup, leave **Allow this measurement command** off
and **Fixed measurement command (JSON argv)** empty for the read-only default.
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

## Claude Code workspace

This distribution asks for a required workspace folder when Claude Code enables the plugin. Select an absolute path to an existing folder. The adapter checks that path before starting; no default workspace is supplied. This profile reads local documents and grants no network access. Portable MCP clients still replace the workspace placeholder as described above. Cowork setup for this required setting is not established; use Claude Code for this source distribution.
