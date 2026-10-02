"""Client archive provenance, no-clobber, and boundary regression tests."""
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
package = __import__("build_client_package")


def test_source_bundle_is_deterministic_and_contains_runtime_source(tmp_path):
    first = package.build(tmp_path/"one", "dev")
    second = package.build(tmp_path/"two", "dev")
    assert first[0].read_bytes() == second[0].read_bytes()
    with zipfile.ZipFile(first[0]) as archive:
        names = archive.namelist()
        assert "server/src/" + package.SPEC["pkg"] + "/client_mcp.py" in names
        assert {"plugin.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json",
                ".claude-plugin/icon.png"} <= set(names)
        assert all(".." not in Path(name).parts and not Path(name).is_absolute() for name in names)
        assert json.loads(archive.read("plugin.json"))["version"] == package.version()
    with pytest.raises(ValueError, match="new directory"):
        package.build(tmp_path/"one", "dev")

PLUGIN = ROOT / "client-plugin"


def test_claude_manifest_carries_directory_listing_and_prompts_for_bindings():
    claude = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    portable = json.loads((PLUGIN / "plugin.json").read_text(encoding="utf-8"))
    codex = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    for key in ("homepage", "documentationUrl", "supportUrl", "privacyPolicyUrl", "termsOfServiceUrl"):
        assert claude[key].startswith("https://"), key
    assert claude["repository"] == "https://github.com/HarperZ9/crucible"
    assert claude["displayName"] == "Crucible" and 5 <= len(claude["keywords"]) <= 8
    assert all(word == word.lower() for word in claude["keywords"])
    assert claude["icon"] == "./.claude-plugin/icon.png"
    for key in ("name", "version", "license", "author", "description"):
        assert claude[key] == portable[key] == codex[key], key
    for shared in (portable, codex):
        assert not {"userConfig", "icon", "displayName", "keywords"} & set(shared)
    config = claude["userConfig"]
    assert set(config) == {"workspace", "process_consent", "measure_command"}
    allowed = {"type", "title", "description", "required", "default", "sensitive"}
    assert all(set(entry) <= allowed and entry["type"] in {"string", "number", "boolean", "directory", "file"}
               for entry in config.values())
    assert config["workspace"]["type"] == "directory" and config["workspace"]["required"] is True
    assert config["process_consent"]["default"] is False and config["measure_command"]["default"] == ""
    native = package.native_manifest("1.4.0", "crucible-local.exe")["user_config"]
    for key, entry in native.items():
        assert config[key]["type"] == entry["type"] and config[key].get("default") == entry.get("default"), key
    args = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["crucible"]["args"]
    assert [a for a in args if "${" in a] == ["${CLAUDE_PLUGIN_ROOT}/server/serve.py", "${user_config.workspace}",
        "--process-consent=${user_config.process_consent}", "--measure-command=${user_config.measure_command}"]
    assert not any("REPLACE_WITH" in a for a in args)
    assert "REPLACE_WITH_ABSOLUTE_WORKSPACE" in json.loads((PLUGIN / "mcp.json").read_text())["mcpServers"]["crucible"]["args"]
    assert not (PLUGIN / "CLAUDE.md").exists()


def test_claude_launch_values_parse_as_the_substituted_defaults(tmp_path):
    import subprocess
    wire = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n"
    result = subprocess.run([sys.executable, "-I", "-S", "-B", str(PLUGIN / "server/serve.py"),
                             "--workspace", str(tmp_path), "--process-consent=false", "--measure-command="],
                            input=wire, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    names = {tool["name"] for tool in json.loads(result.stdout)["result"]["tools"]}
    assert names == {"crucible.assess", "crucible.measurement_gate"}


def test_disclosure_section_names_the_exact_launch_and_environment():
    server = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["crucible"]
    launch = " ".join([server["command"], *server["args"]])
    for name in ("README.md", "PRIVACY.md"):
        text = (PLUGIN / name).read_text(encoding="utf-8")
        section = text.split("## What this plugin runs and handles", 1)[1]
        assert launch in section, name
        assert "This plugin has no hooks." in section
        for variable in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "USERPROFILE",
                         "LANG", "LANGUAGE", "LC_ALL", "LC_MESSAGES", "COLUMNS", "LINES"):
            assert "`" + variable + "`" in section, (name, variable)
    assert not (PLUGIN / "hooks").exists()


def test_committed_icon_is_a_square_png_the_directory_accepts():
    data = (PLUGIN / ".claude-plugin/icon.png").read_bytes()
    assert data[:8] == bytes([137, 80, 78, 71, 13, 10, 26, 10]) and data[12:16] == b"IHDR"
    width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    assert width == height and 512 <= width <= 2048 and len(data) < 2 * 1024 * 1024


def test_release_refuses_unqualified_working_source(monkeypatch):
    monkeypatch.setattr(package, "git", lambda *args: " M source.py" if args[0] == "status" else "a" * 40)
    with pytest.raises(ValueError):
        package.qualify("release")

def test_version_mismatch_stops_before_output(monkeypatch, tmp_path):
    monkeypatch.setitem(package.SPEC, "version", "999.0.0")
    with pytest.raises(ValueError, match="version mismatch"):
        package.build(tmp_path/"absent", "dev")
    assert not (tmp_path/"absent").exists()

def test_archive_rejects_symlink(tmp_path):
    target = tmp_path/"target"
    target.mkdir()
    (target/"safe.py").write_text("x = 1")
    path = tmp_path/"payload"
    path.mkdir()
    try:
        (path/"link").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink privilege unavailable")
    with pytest.raises(ValueError, match="link"):
        package.entries(path)

def test_ignored_credentials_never_enter_package(tmp_path):
    (tmp_path / ".env").write_text("DO_NOT_PACKAGE=synthetic", encoding="utf-8")
    with pytest.raises(ValueError, match="credential"):
        package.entries(tmp_path)

def test_native_validator_rejects_duplicate_keys():
    from check_native_client import strict_json
    with pytest.raises(ValueError, match="duplicate"):
        strict_json('{"isError":true,"isError":false}')

def test_native_validator_rejects_non_text_content():
    from check_native_client import payload_of
    with pytest.raises(ValueError):
        payload_of({"content": [{"type": "text", "text": {"pretend": "success"}}]})

def test_release_collection_rejects_ignored_payload_even_if_git_is_clean(tmp_path, monkeypatch):
    tracked = []
    for folder in ("src", "scripts", "client-plugin"):
        directory = tmp_path / folder
        directory.mkdir()
        (directory / "reviewed.py").write_text("# reviewed source", encoding="utf-8")
        tracked.append(folder + "/reviewed.py")
    (tmp_path / "src" / "ignored-private.txt").write_text("synthetic private sentinel", encoding="utf-8")
    monkeypatch.setattr(package, "ROOT", tmp_path)
    monkeypatch.setattr(package, "qualify", lambda mode: {"mode": mode, "version": "1.0.0", "commit": "a"*40})
    monkeypatch.setattr(package, "git", lambda *args: "\n".join(tracked) if args == ("ls-files",) else "")
    with pytest.raises(ValueError, match="untracked or ignored"):
        package.build(tmp_path.parent / (tmp_path.name + "-output"), "release")

def test_extracted_source_plugin_runs_without_installed_project(tmp_path):
    import subprocess
    archive = package.build(tmp_path / "build", "dev")[0]
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(extracted)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "sample.md").write_text("A synthetic source contains 14 records.", encoding="utf-8")
    (workspace / "thesis.json").write_text(json.dumps({"title": "Synthetic", "claims": [
        {"text": "14 records exist", "falsification": "a count other than 14"}]}), encoding="utf-8")
    wire = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": package.SPEC["tool"], "arguments": package.SPEC["args"]}}) + "\n"
    result = subprocess.run([sys.executable, "-I", "-S", "-B", str(extracted / "server/serve.py"),
                             "--workspace", str(workspace)], input=wire, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    row = json.loads(result.stdout)
    assert row["result"]["isError"] is False, row
    assert isinstance(row["result"]["content"][0]["text"], str)
