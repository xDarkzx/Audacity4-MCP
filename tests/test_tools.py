import pytest
from server4.main import mcp


def test_tool_count():
    """Verify expected number of tools are registered.

    The old threshold (60) counted tools from 9 dead scaffolding files
    (transport/project/edit/track/selection/generate/clip/view/connection_tools.py)
    built against a bridge.dispatch() API that never existed on the real
    BridgeClient - they were leftover from a pre-discovery design where a
    custom bridge would talk to a hypothetical standalone MCP server, before
    finding that MCP is built directly into Audacity 4 with a specific,
    curated command surface. Those files were deleted; this threshold reflects
    the real, working tool count (4 files: label/effects/analysis/cleanup)."""
    tools = mcp._tool_manager._tools
    assert len(tools) >= 20, f"Expected at least 20 tools, got {len(tools)}"


def test_all_tools_have_descriptions():
    """Every tool must have a docstring description."""
    tools = mcp._tool_manager._tools
    for name, tool in tools.items():
        assert tool.description, f"Tool {name} missing description"


def test_no_duplicate_tool_names():
    """Tool names must be unique."""
    tools = mcp._tool_manager._tools
    names = list(tools.keys())
    assert len(names) == len(set(names)), "Duplicate tool names found"
