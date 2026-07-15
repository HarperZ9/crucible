import json

from crucible.cli import main

VERDICT_TOKENS = {"MATCH", "DRIFT", "UNVERIFIABLE"}


def test_operator_commands_emit_no_verdict_token(capsys):
    """status, doctor, and demo measure nothing, so they must not render a verdict token. Emitting
    MATCH for a check that never opened a registry is a verdict without a measurement behind it
    (no receipt, no accept). The envelope status and every doctor check status must be operational
    tokens, never the MATCH/DRIFT/UNVERIFIABLE verdict vocabulary."""
    for command in ("status", "doctor", "demo"):
        assert main([command, "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] not in VERDICT_TOKENS, command
        for check in payload["native"].get("checks", []):
            assert check["status"] not in VERDICT_TOKENS, (command, check)


def test_status_json_is_action_envelope(capsys):
    assert main(["status", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "project-telos.flagship-action/v1"
    assert payload["tool"] == "crucible"
    assert payload["native"]["role"] == "verification-pressure"
    assert payload["native"]["commands"][:4] == ["register", "steelman", "measure", "assess"]
    assert payload["native"]["presentation"]["readme"] == "current"
    assert "MCP stdio" in payload["native"]["integration_surfaces"]
    assert "crucible.recheck" in payload["native"]["mcp_tools"]
    assert "crucible.measurement_gate" in payload["native"]["mcp_tools"]
    assert "measurement-gate" in payload["native"]["commands"]
    assert "creative_measurement_gate" in payload["native"]["capabilities"]
    contracts = payload["native"]["telos_contracts"]
    assert contracts["host_surfaces"] == ["CLI JSON", "MCP stdio", "plugins", "IDEs", "TUIs", "apps"]
    assert "project-telos.action-receipt/v1" in contracts["schemas"]
    assert "creative" in contracts["workflow_domains"]
    assert "scientific" in contracts["workflow_domains"]
    assert "re-checkable verdicts" in contracts["second_brain_role"]


def test_doctor_human_prints_next_action(capsys):
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("status=OK tool=crucible command=doctor")
    assert "next: gather docs" in out


def test_demo_json_names_assessment_command(capsys):
    assert main(["demo", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["native"]["command"].startswith("crucible assess")
