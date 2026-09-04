import pytest
from unittest.mock import AsyncMock
import server4.tools.transport_tools as transport_tools


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


@pytest.mark.asyncio
async def test_transport_play_stop_calls_real_command(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [{"text": "play-stop: playing"}], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    transport_tools.register(fake_mcp)

    await fake_mcp.tools["transport_play_stop"]()

    fake_bridge.call.assert_called_once_with("play-stop", {})


@pytest.mark.asyncio
async def test_transport_pause_calls_real_command(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    transport_tools.register(fake_mcp)

    await fake_mcp.tools["transport_pause"]()

    fake_bridge.call.assert_called_once_with("pause", {})


@pytest.mark.asyncio
async def test_transport_stop_calls_real_command(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    transport_tools.register(fake_mcp)

    await fake_mcp.tools["transport_stop"]()

    fake_bridge.call.assert_called_once_with("stop", {})


@pytest.mark.asyncio
async def test_transport_rewind_start_calls_real_command(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    transport_tools.register(fake_mcp)

    await fake_mcp.tools["transport_rewind_start"]()

    fake_bridge.call.assert_called_once_with("rewind-start", {})
