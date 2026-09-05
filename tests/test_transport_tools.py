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
async def test_transport_play_starts_playback_when_stopped(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.side_effect = [
        {"content": [{"text": '{"isPlaying": false}'}], "isError": False},  # transport-get-play-position
        {"content": [{"text": "play-stop: playing"}], "isError": False},  # play-stop
    ]
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    transport_tools.register(fake_mcp)

    await fake_mcp.tools["transport_play"]()

    calls = fake_bridge.call.call_args_list
    assert calls[0].args == ("transport-get-play-position", {})
    assert calls[1].args == ("play-stop", {})


@pytest.mark.asyncio
async def test_transport_play_is_a_noop_when_already_playing(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [{"text": '{"isPlaying": true}'}], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    transport_tools.register(fake_mcp)

    await fake_mcp.tools["transport_play"]()

    fake_bridge.call.assert_called_once_with("transport-get-play-position", {})


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


@pytest.mark.asyncio
async def test_transport_record_calls_real_command(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [{"text": "transport-record: playback is now stopped"}], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    transport_tools.register(fake_mcp)

    await fake_mcp.tools["transport_record"]()

    fake_bridge.call.assert_called_once_with("transport-record", {})


@pytest.mark.asyncio
async def test_transport_get_play_position_calls_real_command(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    transport_tools.register(fake_mcp)

    await fake_mcp.tools["transport_get_play_position"]()

    fake_bridge.call.assert_called_once_with("transport-get-play-position", {})


@pytest.mark.asyncio
async def test_transport_play_region_selects_then_plays_selection(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.side_effect = [
        {"content": [{"text": "Selected time range"}], "isError": False},  # select-time
        {"content": [{"text": "play-selection: playing"}], "isError": False},  # play-selection
    ]
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    transport_tools.register(fake_mcp)

    await fake_mcp.tools["transport_play_region"](start=1.0, end=5.0)

    calls = fake_bridge.call.call_args_list
    assert calls[0].args == ("select-time", {"start": 1.0, "end": 5.0})
    assert calls[1].args == ("play-selection", {})


@pytest.mark.asyncio
async def test_transport_play_region_rejects_end_before_start(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    transport_tools.register(fake_mcp)

    with pytest.raises(ValueError):
        await fake_mcp.tools["transport_play_region"](start=5.0, end=1.0)

    fake_bridge.call.assert_not_called()
