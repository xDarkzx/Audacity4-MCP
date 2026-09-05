import pytest
from unittest.mock import AsyncMock
import server4.tools.realtime_effects_tools as realtime_effects_tools


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
    realtime_effects_tools.register(fake_mcp)
    return fake_mcp, fake_bridge


@pytest.mark.asyncio
async def test_add_realtime_effect_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(
        monkeypatch, {"content": [{"text": "Added realtime effect ValhallaVintageVerb"}], "isError": False}
    )

    await fake_mcp.tools["add_realtime_effect"](track_id=0, effect_id="ValhallaVintageVerb")

    fake_bridge.call.assert_called_once_with(
        "add-realtime-effect", {"track_id": 0, "effect_id": "ValhallaVintageVerb"}
    )


@pytest.mark.asyncio
async def test_add_realtime_effect_supports_master_track_id(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["add_realtime_effect"](track_id=-2, effect_id="Compressor")

    fake_bridge.call.assert_called_once_with(
        "add-realtime-effect", {"track_id": -2, "effect_id": "Compressor"}
    )


@pytest.mark.asyncio
async def test_list_realtime_effects_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["list_realtime_effects"](track_id=0)

    fake_bridge.call.assert_called_once_with("list-realtime-effects", {"track_id": 0})


@pytest.mark.asyncio
async def test_remove_realtime_effect_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["remove_realtime_effect"](track_id=0, index=1)

    fake_bridge.call.assert_called_once_with("remove-realtime-effect", {"track_id": 0, "index": 1})


@pytest.mark.asyncio
async def test_remove_realtime_effect_rejects_negative_index(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["remove_realtime_effect"](track_id=0, index=-1)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_set_realtime_effect_active_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["set_realtime_effect_active"](track_id=0, index=0, active=False)

    fake_bridge.call.assert_called_once_with(
        "set-realtime-effect-active", {"track_id": 0, "index": 0, "active": False}
    )


@pytest.mark.asyncio
async def test_set_realtime_effect_active_rejects_negative_index(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["set_realtime_effect_active"](track_id=0, index=-1, active=True)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_list_effect_parameters_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["list_effect_parameters"](track_id=0, index=0)

    fake_bridge.call.assert_called_once_with("list-effect-parameters", {"track_id": 0, "index": 0})


@pytest.mark.asyncio
async def test_list_effect_parameters_rejects_negative_index(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["list_effect_parameters"](track_id=0, index=-1)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_set_effect_parameter_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["set_effect_parameter"](track_id=0, index=0, parameter_id="Mix", value=50.0)

    fake_bridge.call.assert_called_once_with(
        "set-effect-parameter", {"track_id": 0, "index": 0, "parameter_id": "Mix", "value": 50.0}
    )


@pytest.mark.asyncio
async def test_set_effect_parameter_rejects_negative_index(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["set_effect_parameter"](track_id=0, index=-1, parameter_id="Mix", value=50.0)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_set_effect_parameter_rejects_empty_parameter_id(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["set_effect_parameter"](track_id=0, index=0, parameter_id="", value=50.0)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_list_effect_presets_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["list_effect_presets"](track_id=0, index=0)

    fake_bridge.call.assert_called_once_with("list-effect-presets", {"track_id": 0, "index": 0})


@pytest.mark.asyncio
async def test_list_effect_presets_rejects_negative_index(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["list_effect_presets"](track_id=0, index=-1)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_apply_effect_preset_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["apply_effect_preset"](track_id=0, index=0, preset_id="Large Hall")

    fake_bridge.call.assert_called_once_with(
        "apply-effect-preset", {"track_id": 0, "index": 0, "preset_id": "Large Hall"}
    )


@pytest.mark.asyncio
async def test_apply_effect_preset_rejects_negative_index(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["apply_effect_preset"](track_id=0, index=-1, preset_id="Large Hall")

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_apply_effect_preset_rejects_empty_preset_id(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["apply_effect_preset"](track_id=0, index=0, preset_id="")

    fake_bridge.call.assert_not_called()
