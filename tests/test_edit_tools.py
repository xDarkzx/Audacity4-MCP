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


@pytest.mark.parametrize(
    "tool_name,command_name,kwargs,expected_params",
    [
        ("clip_set_pitch", "set-clip-pitch", {"key": "0:1", "semitones": 3}, {"key": "0:1", "semitones": 3}),
        ("clip_reset_pitch", "reset-clip-pitch", {"key": "0:1"}, {"key": "0:1"}),
        ("clip_set_speed", "set-clip-speed", {"key": "0:1", "speed": 1.25}, {"key": "0:1", "speed": 1.25}),
        ("clip_reset_speed", "reset-clip-speed", {"key": "0:1"}, {"key": "0:1"}),
        ("clip_render_pitch_speed", "render-clip-pitch-speed", {"key": "0:1"}, {"key": "0:1"}),
        ("clip_reset_pitch_speed", "reset-clip-pitch-speed", {"key": "0:1"}, {"key": "0:1"}),
        ("clip_split_at_silences", "split-clip-at-silences", {"key": "0:1"}, {"key": "0:1"}),
        ("nearest_zero_crossing", "nearest-zero-crossing", {"time": 10.0}, {"time": 10.0}),
        ("clip_set_color", "set-clip-color", {"key": "0:1", "color_index": 3}, {"key": "0:1", "color_index": 3}),
    ],
)
@pytest.mark.asyncio
async def test_clip_tool_calls_real_command(monkeypatch, tool_name, command_name, kwargs, expected_params):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "ok"}], "isError": False})

    await fake_mcp.tools[tool_name](**kwargs)

    fake_bridge.call.assert_called_once_with(command_name, expected_params)


@pytest.mark.asyncio
async def test_split_range_at_silences_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "ok"}], "isError": False})

    await fake_mcp.tools["split_range_at_silences"](start=1.0, end=5.0)

    fake_bridge.call.assert_called_once_with("split-range-at-silences", {"start": 1.0, "end": 5.0})


@pytest.mark.asyncio
async def test_split_range_at_silences_rejects_end_before_start(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["split_range_at_silences"](start=5.0, end=1.0)

    fake_bridge.call.assert_not_called()


@pytest.mark.parametrize("tool_name,command_name", [("clip_trim", "trim-clip"), ("clip_stretch", "stretch-clip")])
@pytest.mark.asyncio
async def test_clip_trim_and_stretch_call_real_command(monkeypatch, tool_name, command_name):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "ok"}], "isError": False})

    await fake_mcp.tools[tool_name](key="0:1", side="right", delta_sec=1.0)

    fake_bridge.call.assert_called_once_with(
        command_name, {"key": "0:1", "side": "right", "delta_sec": 1.0, "min_clip_duration": 0.0}
    )


@pytest.mark.parametrize("tool_name", ["clip_trim", "clip_stretch"])
@pytest.mark.asyncio
async def test_clip_trim_and_stretch_reject_bad_side(monkeypatch, tool_name):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError, match='"left" or "right"'):
        await fake_mcp.tools[tool_name](key="0:1", side="up", delta_sec=1.0)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_clip_set_color_rejects_out_of_range(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError, match="0-9"):
        await fake_mcp.tools["clip_set_color"](key="0:1", color_index=10)

    fake_bridge.call.assert_not_called()
