# Privacy

This local profile reads only submitted paths under the workspace selected at
launch. Tool output is returned to the connected client and its chosen model.
No publisher service, telemetry endpoint, inference engine, or credential store
is used by this profile. Do not include confidential data in the selected
workspace unless that client and model are authorized to receive it.

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
