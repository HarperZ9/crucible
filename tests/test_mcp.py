import io
import json

from crucible.mcp import handle_request, serve


def _call(name, arguments=None):
    return handle_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments or {}},
    })


def test_initialize_announces_crucible():
    resp = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp["result"]["serverInfo"]["name"] == "crucible"
    assert resp["result"]["protocolVersion"]


def test_tools_list_uses_catalog_names():
    resp = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {tool["name"] for tool in resp["result"]["tools"]}
    assert {"crucible.status", "crucible.doctor", "crucible.assess"} <= names


def test_status_tool_returns_action_envelope():
    resp = _call("crucible.status")
    body = json.loads(resp["result"]["content"][0]["text"])
    assert body["schema"] == "project-telos.flagship-action/v1"
    assert body["tool"] == "crucible"
    assert body["next_actions"][0]["tool"] == "telos"


def test_assess_tool_returns_witnessed_counts(tmp_path):
    thesis = tmp_path / "thesis.json"
    measurements = tmp_path / "measurements.json"
    thesis.write_text(json.dumps({
        "title": "smoke",
        "claims": [
            {"text": "measured claim", "falsification": "measurement exceeds tolerance"},
            {"text": "unmeasured claim", "falsification": "no measurement exists"},
        ],
    }), encoding="utf-8")
    measurements.write_text(json.dumps({
        "measurements": [
            {
                "claim": "measured claim",
                "deviation": 0.0,
                "tolerance": 0.1,
                "method": "smoke",
                "evidence": ["fixture"],
            }
        ]
    }), encoding="utf-8")

    resp = _call("crucible.assess", {"thesis": str(thesis), "measurements": str(measurements)})
    body = json.loads(resp["result"]["content"][0]["text"])
    assert body["assessment"]["match"] == 1
    assert body["assessment"]["unverifiable"] == 1
    assert [verdict["status"] for verdict in body["verdicts"]] == ["MATCH", "UNVERIFIABLE"]


def test_unknown_tool_is_jsonrpc_error():
    resp = _call("crucible.nope")
    assert resp["error"]["code"] == -32602


def test_notification_returns_none():
    assert handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_serve_writes_responses():
    inp = io.StringIO(
        '{"jsonrpc":"2.0","id":1,"method":"initialize"}\n'
        '{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
        '{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n'
    )
    out = io.StringIO()
    assert serve(inp, out) == 0
    rows = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [row["id"] for row in rows] == [1, 2]
