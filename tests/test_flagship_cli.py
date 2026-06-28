import json

from crucible.cli import main


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
    contracts = payload["native"]["telos_contracts"]
    assert contracts["host_surfaces"] == ["CLI JSON", "MCP stdio", "plugins", "IDEs", "TUIs", "apps"]
    assert "project-telos.action-receipt/v1" in contracts["schemas"]
    assert "creative" in contracts["workflow_domains"]
    assert "scientific" in contracts["workflow_domains"]
    assert "re-checkable verdicts" in contracts["second_brain_role"]


def test_doctor_human_prints_next_action(capsys):
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("status=MATCH tool=crucible command=doctor")
    assert "next: gather docs" in out


def test_demo_json_names_assessment_command(capsys):
    assert main(["demo", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["native"]["command"].startswith("crucible assess")
