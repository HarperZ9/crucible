# Privacy

This local profile reads only submitted paths under the workspace selected at
launch. Tool output is returned to the connected client and its chosen model.
No publisher service, telemetry endpoint, inference engine, or credential store
is used by this profile. Do not include confidential data in the selected
workspace unless that client and model are authorized to receive it.

## What this plugin runs and handles

### Hooks

This plugin has no hooks.

### MCP server

The plugin starts one MCP server named `crucible`. Claude Code launches it with this command:

```
python3 -I -S -B ${CLAUDE_PLUGIN_ROOT}/server/serve.py --workspace ${user_config.workspace} --process-consent=${user_config.process_consent} --measure-command=${user_config.measure_command}
```

- `python3` is the Python 3.11 or later on your PATH. The `-I -S -B` flags make Python ignore `PYTHON*` environment variables and your user site-packages, skip site-packages, and write no `.pyc` files.
- `${CLAUDE_PLUGIN_ROOT}` is the folder where Claude Code installed the plugin.
- `${user_config.workspace}` is the folder you choose when you enable the plugin. Crucible reads files only inside it.
- `${user_config.process_consent}` is `true` or `false`. It is `false` unless you turn on "Allow this measurement command".
- `${user_config.measure_command}` is the measurement command you enter, as a JSON list of arguments. It is empty unless you fill it in. Crucible refuses to start if you turn on consent without a command, or enter a command without consent.

With the defaults, the server offers two tools: `crucible.assess` and `crucible.measurement_gate`. Both only read files. With consent on and a command set, it also offers `crucible.benchmark`, which runs that one command.

### Network

Crucible opens no network connection. At startup it blocks its own Python process from using sockets. It also blocks it from starting any other program, except the one measurement command you approve.

There is one exception. If you turn on the measurement command, Crucible runs that program once for each claim, up to 16 claims per call. It sends the program each claim's ID, hash, text and falsification test. That program is separate from Crucible. It runs with your user's permissions and can connect to any network address its own code chooses. Crucible cannot see or limit what it does.

### Files written

With the defaults, Crucible writes no files.

With the measurement command on, each run of the program uses two temporary files in your system temp folder. One holds the claim sent to the program. The other holds the program's answer. Crucible deletes both as soon as that run ends, even when the run fails. If the server is stopped in the middle of a run, or your system refuses the delete, a file can stay in the temp folder until you or your system remove it. The measurement program itself may write any files its own code chooses.

### Environment variables and credentials

Crucible reads no credentials, API keys or tokens.

Crucible's own code reads these environment variables, and only when the measurement command runs:

- `SYSTEMROOT` and `WINDIR`: the Windows system folder. They are passed to the measurement program so it can start on Windows.
- `TEMP` and `TMP`: your temp folder. They are passed to the measurement program.

The program receives only those four variables, when they are set. Crucible passes on none of your other variables, such as API keys or endpoint settings.

Python's standard `tempfile` module also reads `TMPDIR`, `TEMP` and `TMP` to choose where the two temporary files go.

## What it stores and sends

This profile stores nothing on disk and opens no network connection; the launcher
denies Python socket and process operations. The optional measurement oracle runs
only when the person who installs the plugin approves its exact command at launch.
While it runs, Crucible passes the claims to it through two temporary files and
deletes them when the call returns. That oracle program may do whatever its own
code does, including network access.

## Retention and support

Crucible keeps no data after a call returns. Support and security reports:
https://github.com/HarperZ9/crucible/issues
