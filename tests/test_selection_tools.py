import json
import pytest
from unittest.mock import AsyncMock
import server4.tools.selection_tools as selection_tools


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
    selection_tools.register(fake_mcp)
    return fake_mcp, fake_bridge


@pytest.mark.asyncio
async def test_select_all_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Selected all"}], "isError": False})

    await fake_mcp.tools["select_all"]()

    fake_bridge.call.assert_called_once_with("select-all", {})


@pytest.mark.asyncio
async def test_select_none_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Selection cleared"}], "isError": False})

    await fake_mcp.tools["select_none"]()

    fake_bridge.call.assert_called_once_with("select-none", {})


@pytest.mark.asyncio
async def test_select_region_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Selected time range"}], "isError": False})

    await fake_mcp.tools["select_region"](start=0.5, end=2.5)

    fake_bridge.call.assert_called_once_with("select-time", {"start": 0.5, "end": 2.5})


@pytest.mark.asyncio
async def test_select_region_rejects_negative_start(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["select_region"](start=-1.0, end=2.0)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_select_region_rejects_end_before_start(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["select_region"](start=2.0, end=1.0)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_select_tracks_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Selected 1 track(s)"}], "isError": False})

    await fake_mcp.tools["select_tracks"](track=1, count=2)

    fake_bridge.call.assert_called_once_with("select-tracks", {"track": 1, "count": 2})


@pytest.mark.asyncio
async def test_select_tracks_rejects_negative_track(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["select_tracks"](track=-1)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_select_tracks_rejects_count_below_one(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["select_tracks"](track=0, count=0)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_select_zero_crossing_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Adjusted selection"}], "isError": False})

    await fake_mcp.tools["select_zero_crossing"]()

    fake_bridge.call.assert_called_once_with("select-zero-crossing", {})


@pytest.mark.asyncio
async def test_cursor_set_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Cursor set to 1.5s"}], "isError": False})

    await fake_mcp.tools["cursor_set"](time=1.5)

    fake_bridge.call.assert_called_once_with("cursor-set", {"time": 1.5})


@pytest.mark.asyncio
async def test_cursor_set_rejects_negative_time(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["cursor_set"](time=-1.0)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_select_clip_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Selected clip 0:2"}], "isError": False})

    await fake_mcp.tools["select_clip"](key="0:2")

    fake_bridge.call.assert_called_once_with("select-clip", {"key": "0:2"})


@pytest.mark.asyncio
async def test_cursor_to_project_start_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Cursor set to 0s"}], "isError": False})

    await fake_mcp.tools["cursor_to_project_start"]()

    fake_bridge.call.assert_called_once_with("cursor-set", {"time": 0.0})


@pytest.mark.asyncio
async def test_cursor_to_project_end_uses_project_duration(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    info_json = json.dumps({"durationSec": 225.6, "trackCount": 1})
    fake_bridge.call.side_effect = [
        {"content": [{"text": "project-get-info"}, {"text": info_json}], "isError": False},
        {"content": [{"text": "Cursor set to 225.6s"}], "isError": False},
    ]

    await fake_mcp.tools["cursor_to_project_end"]()

    assert fake_bridge.call.call_args_list[0].args == ("project-get-info", {})
    assert fake_bridge.call.call_args_list[1].args == ("cursor-set", {"time": 225.6})


@pytest.mark.asyncio
async def test_cursor_to_track_start_uses_earliest_clip_start(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    track_json = json.dumps({"clips": [{"start": 5.0, "end": 10.0}, {"start": 1.0, "end": 3.0}]})
    fake_bridge.call.side_effect = [
        {"content": [{"text": "track-get-info"}, {"text": track_json}], "isError": False},
        {"content": [{"text": "Cursor set to 1.0s"}], "isError": False},
    ]

    await fake_mcp.tools["cursor_to_track_start"](track_id=0)

    assert fake_bridge.call.call_args_list[0].args == ("track-get-info", {"track_id": 0})
    assert fake_bridge.call.call_args_list[1].args == ("cursor-set", {"time": 1.0})


@pytest.mark.asyncio
async def test_cursor_to_track_end_uses_latest_clip_end(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    track_json = json.dumps({"clips": [{"start": 5.0, "end": 10.0}, {"start": 1.0, "end": 3.0}]})
    fake_bridge.call.side_effect = [
        {"content": [{"text": "track-get-info"}, {"text": track_json}], "isError": False},
        {"content": [{"text": "Cursor set to 10.0s"}], "isError": False},
    ]

    await fake_mcp.tools["cursor_to_track_end"](track_id=0)

    assert fake_bridge.call.call_args_list[0].args == ("track-get-info", {"track_id": 0})
    assert fake_bridge.call.call_args_list[1].args == ("cursor-set", {"time": 10.0})


@pytest.mark.asyncio
async def test_cursor_to_track_start_rejects_track_with_no_clips(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    track_json = json.dumps({"clips": []})
    fake_bridge.call.side_effect = [
        {"content": [{"text": "track-get-info"}, {"text": track_json}], "isError": False},
    ]

    with pytest.raises(ValueError):
        await fake_mcp.tools["cursor_to_track_start"](track_id=0)


@pytest.mark.asyncio
async def test_select_cursor_to_track_end_uses_current_position_and_track_end(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    pos_json = json.dumps({"selectionStart": 3.0, "selectionEnd": 3.0})
    track_json = json.dumps({"clips": [{"start": 0.0, "end": 10.0}]})
    fake_bridge.call.side_effect = [
        {"content": [{"text": "transport-get-play-position"}, {"text": pos_json}], "isError": False},
        {"content": [{"text": "track-get-info"}, {"text": track_json}], "isError": False},
        {"content": [{"text": "Selected time range"}], "isError": False},
    ]

    await fake_mcp.tools["select_cursor_to_track_end"](track_id=0)

    assert fake_bridge.call.call_args_list[0].args == ("transport-get-play-position", {})
    assert fake_bridge.call.call_args_list[1].args == ("track-get-info", {"track_id": 0})
    assert fake_bridge.call.call_args_list[2].args == ("select-time", {"start": 3.0, "end": 10.0})


@pytest.mark.asyncio
async def test_select_cursor_to_track_end_rejects_when_cursor_past_track_end(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    pos_json = json.dumps({"selectionStart": 15.0, "selectionEnd": 15.0})
    track_json = json.dumps({"clips": [{"start": 0.0, "end": 10.0}]})
    fake_bridge.call.side_effect = [
        {"content": [{"text": "transport-get-play-position"}, {"text": pos_json}], "isError": False},
        {"content": [{"text": "track-get-info"}, {"text": track_json}], "isError": False},
    ]

    with pytest.raises(ValueError):
        await fake_mcp.tools["select_cursor_to_track_end"](track_id=0)
