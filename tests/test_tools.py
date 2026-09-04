import pytest
from server4.main import mcp


def test_tool_count():
    """Verify expected number of tools are registered."""
    tools = mcp._tool_manager._tools
    assert len(tools) >= 60, f"Expected at least 60 tools, got {len(tools)}"


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
