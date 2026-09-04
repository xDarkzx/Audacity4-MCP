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
