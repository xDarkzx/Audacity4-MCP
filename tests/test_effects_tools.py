import pytest
from unittest.mock import AsyncMock
import server4.tools.effects_tools as effects_tools


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


@pytest.mark.asyncio
async def test_list_effects_default_call(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    await fake_mcp.tools["list_effects"]()

    fake_bridge.call.assert_called_once_with("list-effects", {"limit": 100})


@pytest.mark.asyncio
async def test_list_effects_with_filters(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    await fake_mcp.tools["list_effects"](category="reverb", family="VST3", search="hall", limit=10)

    fake_bridge.call.assert_called_once_with(
        "list-effects",
        {"category": "reverb", "family": "VST3", "search": "hall", "limit": 10},
    )


@pytest.mark.asyncio
async def test_list_effects_rejects_bad_limit(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    with pytest.raises(ValueError):
        await fake_mcp.tools["list_effects"](limit=0)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_normalize_builds_correct_params(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    await fake_mcp.tools["normalize"](peak_level_db=-3.0, remove_dc=True, stereo_independent=False)

    fake_bridge.call.assert_called_once_with("apply-effect", {
        "effect_id": "Normalize",
        "params": 'PeakLevel=-3.0 RemoveDcOffset=1 ApplyVolume=1 StereoIndependent=0',
    })


@pytest.mark.asyncio
async def test_normalize_rejects_out_of_range_peak_level(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    with pytest.raises(ValueError, match="peak_level_db"):
        await fake_mcp.tools["normalize"](peak_level_db=10.0)


@pytest.mark.asyncio
async def test_compressor_builds_v4_param_names(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    await fake_mcp.tools["compressor"](threshold_db=-18.0, ratio=4.0)

    call_args = fake_bridge.call.call_args
    assert call_args[0][0] == "apply-effect"
    assert call_args[0][1]["effect_id"] == "Compressor"
    assert "thresholdDb=-18.0" in call_args[0][1]["params"]
    assert "compressionRatio=4.0" in call_args[0][1]["params"]


@pytest.mark.asyncio
async def test_noise_reduction_rejects_out_of_range_sensitivity(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    with pytest.raises(ValueError, match="sensitivity"):
        await fake_mcp.tools["noise_reduction"](sensitivity=100.0)


@pytest.mark.asyncio
async def test_click_removal_builds_correct_params(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    await fake_mcp.tools["click_removal"](threshold=200, spike_width=20)

    fake_bridge.call.assert_called_once_with("apply-effect", {
        "effect_id": "Click removal", "params": "Threshold=200 Width=20",
    })


@pytest.mark.asyncio
async def test_bass_and_treble_rejects_out_of_range(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    with pytest.raises(ValueError, match="bass"):
        await fake_mcp.tools["bass_and_treble"](bass=50.0)


def test_params_formats_bools_as_numeric_not_text():
    # Regression test: wxFileConfig's bool Read() parses the stored value as a
    # NUMBER (ToLong()) - "True"/"False" silently fail that parse and fall back
    # to the parameter's default instead of erroring. Confirmed via a crash dump
    # this caused NoiseReduction's GetProfile=True to be silently ignored.
    result = effects_tools._params(Flag=True, Other=False)
    assert result == "Flag=1 Other=0"


@pytest.mark.asyncio
async def test_get_noise_profile_sends_numeric_bool(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    await fake_mcp.tools["get_noise_profile"]()

    fake_bridge.call.assert_called_once_with("apply-effect", {
        "effect_id": "Noise reduction",
        "params": "GetProfile=1",
    })


@pytest.mark.asyncio
async def test_effect_amplify_builds_correct_params(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    await fake_mcp.tools["effect_amplify"](ratio=2.0, allow_clipping=True)

    fake_bridge.call.assert_called_once_with("apply-effect", {
        "effect_id": "Amplify", "params": "Ratio=2.0 AllowClipping=1",
    })


@pytest.mark.asyncio
async def test_effect_amplify_rejects_out_of_range_ratio(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    with pytest.raises(ValueError, match="ratio"):
        await fake_mcp.tools["effect_amplify"](ratio=1000.0)


@pytest.mark.asyncio
async def test_effect_fade_in_calls_real_command(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    await fake_mcp.tools["effect_fade_in"]()

    fake_bridge.call.assert_called_once_with("apply-effect", {"effect_id": "Fade In", "params": ""})


@pytest.mark.asyncio
async def test_effect_fade_out_calls_real_command(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    await fake_mcp.tools["effect_fade_out"]()

    fake_bridge.call.assert_called_once_with("apply-effect", {"effect_id": "Fade Out", "params": ""})


@pytest.mark.asyncio
async def test_effect_reverb_builds_correct_wire_keys(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    await fake_mcp.tools["effect_reverb"](pre_delay=15.0)

    call_args = fake_bridge.call.call_args
    assert call_args[0][1]["effect_id"] == "Reverb"
    # Real v4 wire key is "Delay", not "PreDelay" - confirmed against ReverbEffect's
    # EffectParameter PreDelay{..., L"Delay", ...} declaration.
    assert "Delay=15.0" in call_args[0][1]["params"]
    assert "PreDelay" not in call_args[0][1]["params"]


@pytest.mark.asyncio
async def test_effect_reverb_rejects_out_of_range(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    with pytest.raises(ValueError, match="wet_gain"):
        await fake_mcp.tools["effect_reverb"](wet_gain=50.0)


@pytest.mark.asyncio
async def test_effect_change_pitch_converts_semitones_to_percentage(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    await fake_mcp.tools["effect_change_pitch"](semitones=12.0)

    call_args = fake_bridge.call.call_args
    assert call_args[0][1]["effect_id"] == "Change pitch"
    assert "Percentage=100.0" in call_args[0][1]["params"]


@pytest.mark.asyncio
async def test_effect_paulstretch_uses_spaced_wire_keys(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    await fake_mcp.tools["effect_paulstretch"](stretch_factor=5.0, time_resolution=0.1)

    fake_bridge.call.assert_called_once_with("apply-effect", {
        "effect_id": "Paulstretch",
        "params": '"Stretch Factor"=5.0 "Time Resolution"=0.1',
    })


@pytest.mark.asyncio
async def test_effect_paulstretch_rejects_stretch_below_one(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    with pytest.raises(ValueError, match="stretch_factor"):
        await fake_mcp.tools["effect_paulstretch"](stretch_factor=0.5)


@pytest.mark.asyncio
async def test_effect_reverse_calls_real_command(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    await fake_mcp.tools["effect_reverse"]()

    fake_bridge.call.assert_called_once_with("apply-effect", {"effect_id": "Reverse", "params": ""})


@pytest.mark.asyncio
async def test_effect_invert_calls_real_command(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    await fake_mcp.tools["effect_invert"]()

    fake_bridge.call.assert_called_once_with("apply-effect", {"effect_id": "Invert", "params": ""})


@pytest.mark.asyncio
async def test_effect_repair_calls_real_command(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    await fake_mcp.tools["effect_repair"]()

    fake_bridge.call.assert_called_once_with("apply-effect", {"effect_id": "Repair", "params": ""})


@pytest.mark.asyncio
async def test_effect_sliding_stretch_is_disabled(monkeypatch):
    """Live-tested and confirmed this effect reliably crashes/hangs the app (a
    pre-existing engine bug in how SBSMS-family effects trigger extension reload
    on first invocation - see the comment in effects_tools.py). Disabled at the
    Python layer rather than left to crash a live session."""
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)

    with pytest.raises(RuntimeError, match="disabled"):
        await fake_mcp.tools["effect_sliding_stretch"](rate_change_start=10.0)

    fake_bridge.call.assert_not_called()


def _apply_effects_mcp(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    effects_tools.register(fake_mcp)
    return fake_mcp, fake_bridge


@pytest.mark.asyncio
async def test_apply_effects_encodes_pipe_separated_lists(monkeypatch):
    fake_mcp, fake_bridge = _apply_effects_mcp(monkeypatch)
    await fake_mcp.tools["apply_effects"]([
        {"effect_id": "Normalize", "params": "PeakLevel=-1.0 RemoveDcOffset=1"},
        {"effect_id": "Compressor", "params": "Threshold=-12 Ratio=4"},
        {"effect_id": "Click removal"},
    ])
    name, args = fake_bridge.call.call_args[0]
    assert name == "apply-effects"
    assert args["effect_ids"] == "Normalize|Compressor|Click removal"
    assert args["params_list"] == "PeakLevel=-1.0 RemoveDcOffset=1|Threshold=-12 Ratio=4|"
    assert args["select_all"] is True


@pytest.mark.asyncio
async def test_apply_effects_rejects_empty_list(monkeypatch):
    fake_mcp, _ = _apply_effects_mcp(monkeypatch)
    with pytest.raises(ValueError):
        await fake_mcp.tools["apply_effects"]([])


@pytest.mark.asyncio
async def test_apply_effects_rejects_missing_effect_id(monkeypatch):
    fake_mcp, _ = _apply_effects_mcp(monkeypatch)
    with pytest.raises(ValueError, match="effect_id"):
        await fake_mcp.tools["apply_effects"]([{"params": "X=1"}])


@pytest.mark.asyncio
async def test_apply_effects_rejects_pipe_in_values(monkeypatch):
    fake_mcp, _ = _apply_effects_mcp(monkeypatch)
    with pytest.raises(ValueError):
        await fake_mcp.tools["apply_effects"]([{"effect_id": "A|B"}])


@pytest.mark.asyncio
async def test_apply_effects_honours_select_all_false(monkeypatch):
    fake_mcp, fake_bridge = _apply_effects_mcp(monkeypatch)
    await fake_mcp.tools["apply_effects"]([{"effect_id": "Normalize"}], select_all=False)
    assert fake_bridge.call.call_args[0][1]["select_all"] is False
