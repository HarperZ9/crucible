"""Actual stdio/process permission tests with a deterministic local oracle."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

LAUNCHER = Path(__file__).resolve().parents[1] / "client-plugin/server/serve.py"


def launch(tmp_path, flags=(), requests=()):
    env = dict(os.environ, CRUCIBLE_ALLOW_PROCESS="1", OPENAI_API_KEY="synthetic-do-not-inherit")
    return subprocess.run([sys.executable, "-I", "-S", "-B", str(LAUNCHER),
                           "--workspace", str(tmp_path), *flags],
                          input="".join(json.dumps(r) + "\n" for r in requests),
                          capture_output=True, text=True, timeout=20, env=env)


def call(args):
    return {"id": 1, "method": "tools/call", "params": {
        "name": "crucible.benchmark", "arguments": args}}


def fixture(tmp_path):
    script = tmp_path / "oracle.py"
    script.write_text("import json, os, sys\n"
                      "assert 'OPENAI_API_KEY' not in os.environ\n"
                      "request = json.load(sys.stdin)\n"
                      "value = sum(range(5))\n"
                      "print(json.dumps({'deviation': abs(value - 10), 'tolerance': 0.1, "
                      "'evidence': ['sum(range(5))=' + str(value)]}))\n", encoding="utf-8")
    (tmp_path / "thesis.json").write_text(json.dumps({"title": "Synthetic arithmetic",
        "claims": [{"text": "sum(range(5)) equals 10", "falsification": "sum differs from 10",
                    "tolerance": 0.1}]}), encoding="utf-8")
    return ("--allow-process", "--measure-command", json.dumps([sys.executable, "-I", "-S", str(script)]))


def test_default_denies_even_ambient_grants(tmp_path):
    fixture(tmp_path)
    result = launch(tmp_path, requests=[call({"thesis": "thesis.json"})])
    assert result.returncode == 0, result.stderr
    assert "TOOL_NOT_GRANTED" in result.stdout


@pytest.mark.parametrize("extra", [{"command": ["other"]}, {"allow_process": True}, {"network": True}])
def test_tool_cannot_widen_launch_grant(tmp_path, extra):
    result = launch(tmp_path, fixture(tmp_path), [call({"thesis": "thesis.json", **extra})])
    assert "ARGUMENTS_DENIED" in result.stdout


def test_actual_benchmark_reuses_witnessed_assessment(tmp_path):
    result = launch(tmp_path, fixture(tmp_path), [call({"thesis": "thesis.json"})])
    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)["result"]
    assert response["isError"] is False, response
    data = json.loads(response["content"][0]["text"])
    assert data["verdicts"][0]["status"] == "MATCH"
    assert data["assessment"]["match"] == 1
    assert data["measurements"][0]["evidence"] == ["sum(range(5))=10"]


@pytest.mark.parametrize("flags", [("--allow-process",), ("--measure-command", '["python"]'),
    ("--allow-process", "--measure-command", '"python oracle.py"'),
    ("--allow-process", "--measure-command", '["python"]')])
def test_incomplete_or_ambiguous_grant_refused(tmp_path, flags):
    result = launch(tmp_path, flags)
    assert result.returncode == 2


def test_failed_oracle_never_reports_match(tmp_path):
    flags = fixture(tmp_path)
    (tmp_path / "oracle.py").write_text("raise SystemExit(7)\n", encoding="utf-8")
    result = launch(tmp_path, flags, [call({"thesis": "thesis.json"})])
    response = json.loads(result.stdout)["result"]
    assert response["isError"] is True
    assert "MATCH" not in response["content"][0]["text"]


def test_inaccurate_measurement_is_drift(tmp_path):
    flags = fixture(tmp_path)
    script = tmp_path / "oracle.py"
    script.write_text(script.read_text().replace("abs(value - 10)", "abs(value - 14)"), encoding="utf-8")
    result = launch(tmp_path, flags, [call({"thesis": "thesis.json"})])
    response = json.loads(result.stdout)["result"]
    assert response["isError"] is False
    data = json.loads(response["content"][0]["text"])
    assert data["verdicts"][0]["status"] == "DRIFT"


def test_parent_network_and_other_processes_remain_denied(tmp_path):
    source = str(LAUNCHER.parents[2] / "src")
    code = f"""
import sys, socket, subprocess
sys.path.insert(0, {source!r})
from crucible.client_mcp import install_process_boundary
install_process_boundary((sys.executable, '-c', 'pass'))
for action in [lambda: socket.socket(), lambda: subprocess.run([sys.executable, '-c', 'print(1)'])]:
    try:
        action()
    except PermissionError:
        pass
    else:
        raise AssertionError('unexpected grant')
"""
    result = subprocess.run([sys.executable, "-I", "-S", "-c", code], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("consent,command_kind,expected", [
    (False, "empty", "denied"), (True, "valid", "allowed"),
    (False, "valid", "invalid"), (True, "empty", "invalid"),
    (True, "malformed", "invalid"), ("yes", "valid", "invalid")])
def test_expanded_mcpb_setup_arguments(tmp_path, consent, command_kind, expected):
    sys.path.insert(0, str(LAUNCHER.parents[2] / "scripts"))
    from build_client_package import native_manifest
    manifest = native_manifest("1.4.0", "crucible-local.exe")
    assert manifest["user_config"]["process_consent"]["default"] is False
    assert manifest["user_config"]["measure_command"]["default"] == ""
    flags = fixture(tmp_path)
    values = {"workspace": str(tmp_path), "process_consent":
              str(consent).lower(), "measure_command": {"empty": "", "valid": flags[2],
                                                        "malformed": "not-json"}[command_kind]}
    argv = manifest["server"]["mcp_config"]["args"]
    for key, value in values.items():
        argv = [arg.replace("${user_config." + key + "}", value) for arg in argv]
    # The helper adds --workspace, so use the exact remaining expanded argv.
    assert argv[:2] == ["--workspace", str(tmp_path)]
    result = launch(tmp_path, argv[2:], [call({"thesis": "thesis.json"})])
    if expected == "invalid":
        assert result.returncode == 2, result.stdout
    else:
        assert result.returncode == 0, result.stderr
        response = json.loads(result.stdout)["result"]
        assert response["isError"] is (expected == "denied")
        if expected == "allowed":
            assert json.loads(response["content"][0]["text"])["verdicts"][0]["status"] == "MATCH"


def test_manual_flag_cannot_override_explicit_false_consent(tmp_path):
    result = launch(tmp_path, (*fixture(tmp_path), "--process-consent", "false"))
    assert result.returncode == 2
