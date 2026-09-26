"""Install a built crucible wheel into a fresh environment and check what a user gets.

    python scripts/smoke_wheel.py dist/crucible_bench-X.Y.Z-py3-none-any.whl [--json]

Runs from a new empty folder with nothing from the source tree on the path, and checks:

- the package imports from the environment, and ``crucible --version`` names the wheel's version;
- the sealed-tolerance probe (``tests/fixtures/sealed-tolerance``) returns UNVERIFIABLE for a
  widened tolerance and DRIFT for the sealed one (crucible-bench 1.2.0 returned MATCH);
- ``crucible examples`` writes the packaged inputs and the documented first run gives 1/1/1;
- ``crucible mcp`` initializes, lists the tools ``status`` names, and answers ``crucible.status``.

Exit 0 when every check passes, 1 otherwise. Stdlib only; installs with ``--no-index``, so it
needs no network (crucible has no runtime dependencies).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "sealed-tolerance"
TIMEOUT = 120


class Env:
    """A fresh virtual environment with the wheel installed, run from an empty folder."""

    def __init__(self, base: Path, wheel: Path):
        self.base = base
        self.work = base / "work"
        self.work.mkdir()
        venv.create(base / "venv", with_pip=True)
        bindir = base / "venv" / ("Scripts" if os.name == "nt" else "bin")
        self.python = bindir / ("python.exe" if os.name == "nt" else "python")
        self.crucible = bindir / ("crucible.exe" if os.name == "nt" else "crucible")
        self.env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
        self.env["PYTHONSAFEPATH"] = "1"
        self.run([str(self.python), "-m", "pip", "install", "--quiet", "--no-index", "--no-deps",
                  str(wheel)])

    def run(self, argv: list[str], stdin: str | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(argv, cwd=self.work, env=self.env, input=stdin, capture_output=True,
                              text=True, encoding="utf-8", timeout=TIMEOUT, check=False)

    def cli(self, *args: str) -> subprocess.CompletedProcess:
        return self.run([str(self.crucible), *args])


def wheel_version(wheel: Path) -> str:
    return wheel.name.split("-")[1]


def check_install(env: Env, version: str) -> list[str]:
    fails: list[str] = []
    probe = env.run([str(env.python), "-c",
                     "import crucible, json; print(json.dumps([crucible.__version__, crucible.__file__]))"])
    if probe.returncode != 0:
        return [f"import failed: {probe.stderr.strip()[-300:]}"]
    got, where = json.loads(probe.stdout)
    if got != version:
        fails.append(f"crucible.__version__ is {got}, wheel is {version}")
    if not Path(where).resolve().is_relative_to((env.base / "venv").resolve()):
        fails.append(f"crucible imported from outside the environment: {where}")
    shown = env.cli("--version")
    if shown.stdout.strip() != f"crucible {version}":
        fails.append(f"--version printed {shown.stdout.strip()!r}")
    if env.cli("--help").returncode != 0:
        fails.append("--help exited nonzero")
    return fails


def check_sealed_tolerance(env: Env, fixtures: Path) -> list[str]:
    fails: list[str] = []
    for measurements, expected in (("measurements-widened.json", ["UNVERIFIABLE"]),
                                   ("measurements-sealed.json", ["DRIFT"])):
        out = env.cli("assess", str(fixtures / "thesis.json"),
                      "--measurements", str(fixtures / measurements), "--json")
        try:
            statuses = [v["status"] for v in json.loads(out.stdout)["verdicts"]]
        except (ValueError, KeyError, TypeError):
            fails.append(f"assess {measurements}: no JSON verdicts (exit {out.returncode})")
            continue
        if statuses != expected:
            fails.append(f"assess {measurements}: got {statuses}, expected {expected}")
    return fails


def check_examples(env: Env) -> list[str]:
    made = env.cli("examples", "--out", "ex", "--json")
    if made.returncode != 0:
        return [f"examples exited {made.returncode}: {made.stderr.strip()[-200:]}"]
    ran = env.cli("run", "ex/thesis-binary-search.json",
                  "--measurements", "ex/measurements-binary-search.json",
                  "--registry", "reg", "--json")
    try:
        record = json.loads(ran.stdout)
        counts = record["assessment"]
        got = (counts["match"], counts["drift"], counts["unverifiable"])
    except (ValueError, KeyError, TypeError):
        return [f"first run gave no JSON record (exit {ran.returncode})"]
    fails = [] if got == (1, 1, 1) else [f"first run counts {got}, expected (1, 1, 1)"]
    if not all(record.get("checks", {}).values()):
        fails.append(f"first run did not re-derive: {record.get('checks')}")
    return fails


def _mcp_session(env: Env) -> dict[int, dict]:
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "smoke", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "crucible.status", "arguments": {}}},
    ]
    out = env.run([str(env.crucible), "mcp"],
                  stdin="".join(json.dumps(r) + "\n" for r in requests))
    replies = [json.loads(line) for line in out.stdout.splitlines() if line.strip()]
    return {r["id"]: r for r in replies if "id" in r} | {0: {"exit": out.returncode}}


def check_mcp(env: Env, version: str) -> list[str]:
    try:
        replies = _mcp_session(env)
        info = replies[1]["result"]["serverInfo"]
        tools = sorted(t["name"] for t in replies[2]["result"]["tools"])
        status = json.loads(replies[3]["result"]["content"][0]["text"])
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        return [f"mcp session incomplete: {type(exc).__name__}: {exc}"]
    fails: list[str] = []
    if info.get("version") != version:
        fails.append(f"mcp serverInfo.version is {info.get('version')}")
    named = sorted(status.get("native", {}).get("mcp_tools", []))
    if not tools or tools != named:
        fails.append(f"mcp lists {len(tools)} tools; status names {len(named)}")
    if replies[0]["exit"] != 0:
        fails.append(f"mcp exited {replies[0]['exit']} after stdin closed")
    return fails


def smoke(wheel: Path, fixtures: Path) -> dict:
    version = wheel_version(wheel)
    with tempfile.TemporaryDirectory(prefix="crucible-smoke-") as tmp:
        env = Env(Path(tmp), wheel.resolve())
        results = {
            "install": check_install(env, version),
            "sealed_tolerance": check_sealed_tolerance(env, fixtures.resolve()),
            "examples": check_examples(env),
            "mcp": check_mcp(env, version),
        }
    return {"wheel": wheel.name, "version": version,
            "ok": not any(results.values()), "failures": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("wheel", type=Path, help="path to a built crucible_bench wheel")
    parser.add_argument("--fixtures", type=Path, default=FIXTURES,
                        help="folder holding the sealed-tolerance probe inputs")
    parser.add_argument("--json", action="store_true", help="emit the full result as JSON")
    args = parser.parse_args(argv)
    report = smoke(args.wheel, args.fixtures)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for check, fails in report["failures"].items():
            print(f"{'ok  ' if not fails else 'FAIL'} {check}")
            for line in fails:
                print(f"     {line}")
        print(f"{report['wheel']}: {'all checks pass' if report['ok'] else 'checks failed'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
