"""The plugin folder must run on its own: a directory install receives only client-plugin/."""
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "client-plugin"
sys.path.insert(0, str(ROOT / "scripts"))
package = __import__("build_client_package")
SYNC = "python scripts/build_client_package.py --sync-vendored"


def test_committed_vendored_server_matches_src():
    expected = package.vendored_payload()
    committed = {name: package.normalized(data) for name, data in package.entries(PLUGIN).items()
                 if name.startswith(package.VENDORED)}
    missing = sorted(set(expected) - set(committed))
    extra = sorted(set(committed) - set(expected))
    changed = sorted(name for name in set(expected) & set(committed) if expected[name] != committed[name])
    assert not (missing or extra or changed), (
        f"client-plugin/server/src/ drifted from src/ (missing {missing}, extra {extra}, "
        f"changed {changed}). Run: {SYNC}")


def test_source_zip_takes_server_code_from_src_once(tmp_path):
    archive = package.build(tmp_path / "build", "dev")[0]
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        served = {name for name in names if name.startswith(package.VENDORED)}
    assert len(names) == len(set(names))
    assert served == set(package.vendored_payload())
    assert not any(name.startswith(package.VENDORED) for name in package.plugin_entries())


def test_plugin_folder_fits_directory_limits():
    files = [path for path in PLUGIN.rglob("*") if path.is_file() and "__pycache__" not in path.parts]
    assert len(files) <= 512
    assert max(path.stat().st_size for path in files) < 256 * 1024
    assert not any(path.name == ".gitattributes" for path in files)


def _launch(root, workspace):
    server = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["crucible"]
    config = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))["userConfig"]
    values = {key: str(entry.get("default", "")).lower() if isinstance(entry.get("default"), bool)
              else str(entry.get("default", "")) for key, entry in config.items()}
    values["workspace"] = str(workspace)

    def fill(text):
        text = text.replace("${CLAUDE_PLUGIN_ROOT}", str(root))
        for key, value in values.items():
            text = text.replace("${user_config." + key + "}", value)
        assert "${" not in text, text
        return text
    assert server["command"] == "python3"
    env = {key: fill(value) for key, value in server.get("env", {}).items()}
    wire = "".join(json.dumps(row) + "\n" for row in (
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}))
    return subprocess.run([sys.executable, *[fill(arg) for arg in server["args"]]], input=wire,
                          capture_output=True, text=True, timeout=30, check=False, cwd=root,
                          env={**os.environ, **env})


def test_plugin_folder_alone_starts_with_the_claude_launch_command(tmp_path):
    root = tmp_path / "installed"
    shutil.copytree(PLUGIN, root, ignore=shutil.ignore_patterns("__pycache__"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    result = _launch(root, workspace)
    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    assert rows[0]["result"]["serverInfo"]["name"] == "crucible-local"
    assert {tool["name"] for tool in rows[1]["result"]["tools"]} == {"crucible.assess", "crucible.measurement_gate"}

    shutil.rmtree(root / "server" / "src")
    result = _launch(root, workspace)
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr.strip() == ("crucible: the server code is missing from the plugin folder. "
                                     "Reinstall the plugin.")
