import pytest
from unittest.mock import AsyncMock
import server4.tools.track_tools as track_tools


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
    track_tools.register(fake_mcp)
    return fake_mcp, fake_bridge


@pytest.mark.asyncio
async def test_track_add_mono_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Mono track added"}], "isError": False})

    await fake_mcp.tools["track_add_mono"]()

    fake_bridge.call.assert_called_once_with("track-add-mono", {})


@pytest.mark.asyncio
async def test_track_add_stereo_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Stereo track added"}], "isError": False})

    await fake_mcp.tools["track_add_stereo"]()

    fake_bridge.call.assert_called_once_with("track-add-stereo", {})


@pytest.mark.asyncio
async def test_track_remove_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Removed 1 track(s)"}], "isError": False})

    await fake_mcp.tools["track_remove"]()

    fake_bridge.call.assert_called_once_with("track-remove", {})


@pytest.mark.asyncio
async def test_track_set_properties_only_sends_given_fields(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Updated: name"}], "isError": False})

    await fake_mcp.tools["track_set_properties"](track=2, name="Vocals")

    fake_bridge.call.assert_called_once_with("track-set-properties", {"track": 2, "name": "Vocals"})


@pytest.mark.asyncio
async def test_track_set_properties_sends_all_given_fields(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["track_set_properties"](track=0, gain=-3.0, pan=0.5, mute=True, solo=False)

    fake_bridge.call.assert_called_once_with(
        "track-set-properties", {"track": 0, "gain": -3.0, "pan": 0.5, "mute": True, "solo": False}
    )


@pytest.mark.asyncio
async def test_track_set_properties_rejects_negative_track(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["track_set_properties"](track=-1)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_track_set_properties_rejects_out_of_range_gain(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["track_set_properties"](track=0, gain=100.0)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_track_set_properties_rejects_out_of_range_pan(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["track_set_properties"](track=0, pan=2.0)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_track_duplicate_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Duplicated 1 track(s)"}], "isError": False})

    await fake_mcp.tools["track_duplicate"]()

    fake_bridge.call.assert_called_once_with("track-duplicate", {})


@pytest.mark.asyncio
async def test_track_resample_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Resampled to 48000Hz"}], "isError": False})

    await fake_mcp.tools["track_resample"](rate=48000)

    fake_bridge.call.assert_called_once_with("track-resample", {"rate": 48000})


@pytest.mark.asyncio
async def test_track_resample_rejects_out_of_range_rate(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["track_resample"](rate=0)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_track_get_info_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["track_get_info"](track_id=1)

    fake_bridge.call.assert_called_once_with("track-get-info", {"track_id": 1})


@pytest.mark.asyncio
async def test_track_mute_calls_track_set_properties(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["track_mute"](track=2, mute=False)

    fake_bridge.call.assert_called_once_with("track-set-properties", {"track": 2, "mute": False})


@pytest.mark.asyncio
async def test_track_mute_defaults_to_true(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["track_mute"](track=0)

    fake_bridge.call.assert_called_once_with("track-set-properties", {"track": 0, "mute": True})


@pytest.mark.asyncio
async def test_track_mute_rejects_negative_index(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["track_mute"](track=-1)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_track_mute_all_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Muted 3 track(s)"}], "isError": False})

    await fake_mcp.tools["track_mute_all"]()

    fake_bridge.call.assert_called_once_with("track-mute-all", {})


@pytest.mark.asyncio
async def test_track_unmute_all_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Unmuted 3 track(s)"}], "isError": False})

    await fake_mcp.tools["track_unmute_all"]()

    fake_bridge.call.assert_called_once_with("track-unmute-all", {})


@pytest.mark.asyncio
async def test_track_set_color_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Track color set"}], "isError": False})

    await fake_mcp.tools["track_set_color"](color_index=5)

    fake_bridge.call.assert_called_once_with("set-track-color", {"color_index": 5})


@pytest.mark.asyncio
async def test_track_set_color_rejects_out_of_range(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError, match="0-9"):
        await fake_mcp.tools["track_set_color"](color_index=10)

    fake_bridge.call.assert_not_called()
