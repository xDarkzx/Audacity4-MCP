import pytest
from unittest.mock import AsyncMock
import server4.tools.project_tools as project_tools


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


@pytest.mark.asyncio
async def test_project_save_calls_real_command(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [{"text": "Project saved"}], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    project_tools.register(fake_mcp)

    await fake_mcp.tools["project_save"]()

    fake_bridge.call.assert_called_once_with("save-project", {})


@pytest.mark.asyncio
async def test_recent_commands_calls_real_command(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [{"text": "recent-commands"}, {"text": "[]"}], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    project_tools.register(fake_mcp)

    await fake_mcp.tools["recent_commands"]()

    fake_bridge.call.assert_called_once_with("recent-commands", {})


@pytest.mark.asyncio
async def test_command_status_passes_id_argument(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [{"text": "found"}], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    project_tools.register(fake_mcp)

    await fake_mcp.tools["command_status"]("42")

    fake_bridge.call.assert_called_once_with("command-status", {"id": "42"})
