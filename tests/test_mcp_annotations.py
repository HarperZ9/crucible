"""Every MCP tool states its title and read/write hints.

The Anthropic Software Directory Policy requires readOnlyHint, destructiveHint
and title on every tool a listed server exposes.
"""
from crucible import client_mcp
from crucible.client_process import definition
from crucible.mcp import handle_request
from crucible.mcp_tools import ANNOTATIONS, tool_defs

HINTS = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")


def _assert_complete(tools):
    assert tools
    for tool in tools:
        notes = tool["annotations"]
        assert notes["title"] and tool["title"] == notes["title"], tool["name"]
        assert all(isinstance(notes[key], bool) for key in HINTS), tool["name"]
        assert len(tool["name"]) <= 64
        if notes["readOnlyHint"]:
            assert notes["destructiveHint"] is False, tool["name"]


def test_full_surface_tools_are_annotated():
    tools = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
    _assert_complete(tools)
    assert {tool["name"] for tool in tools} == set(ANNOTATIONS)


def test_client_profile_tools_are_annotated(tmp_path):
    tools = client_mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, tmp_path)
    _assert_complete(tools["result"]["tools"])
    _assert_complete([definition()])


def test_hints_match_tool_effects():
    by_name = {tool["name"]: tool["annotations"] for tool in tool_defs()}
    assert by_name["crucible.assess"]["readOnlyHint"] is True
    assert by_name["crucible.registry"]["destructiveHint"] is True
    assert by_name["crucible.run"]["readOnlyHint"] is False
    assert definition()["annotations"]["openWorldHint"] is True
