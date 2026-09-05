import pytest
from unittest.mock import AsyncMock
import server4.tools.edit_tools as edit_tools


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def _fake_mcp_with(monkeypatch, result):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = result
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    edit_tools.register(fake_mcp)
    return fake_mcp, fake_bridge


@pytest.mark.parametrize(
    "tool_name,command_name",
    [
        ("edit_cut", "edit-cut"),
        ("edit_copy", "edit-copy"),
        ("edit_paste", "edit-paste"),
        ("edit_delete", "edit-delete"),
        ("edit_split", "edit-split"),
        ("edit_trim", "edit-trim"),
        ("edit_silence", "edit-silence"),
        ("edit_duplicate", "edit-duplicate"),
        ("edit_undo", "edit-undo"),
        ("edit_redo", "edit-redo"),
        ("edit_split_new", "edit-split-new"),
        ("edit_split_cut", "edit-split-cut"),
        ("edit_split_delete", "edit-split-delete"),
        ("edit_disjoin", "edit-disjoin"),
        ("edit_join", "edit-join"),
    ],
)
@pytest.mark.asyncio
async def test_edit_tool_calls_real_command_with_no_args(monkeypatch, tool_name, command_name):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "ok"}], "isError": False})

    await fake_mcp.tools[tool_name]()

    fake_bridge.call.assert_called_once_with(command_name, {})
