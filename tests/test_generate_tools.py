import pytest
from unittest.mock import AsyncMock
import server4.tools.generate_tools as generate_tools


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
    generate_tools.register(fake_mcp)
    return fake_mcp, fake_bridge


@pytest.mark.asyncio
async def test_generate_tone_builds_correct_params(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["generate_tone"](waveform="Sine", frequency=880.0, amplitude=0.5)

    fake_bridge.call.assert_called_once_with("apply-effect", {
        "effect_id": "Tone",
        "params": "Frequency=880.0 Amplitude=0.5 Waveform=Sine",
    })


@pytest.mark.asyncio
async def test_generate_tone_rejects_invalid_waveform(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError, match="waveform"):
        await fake_mcp.tools["generate_tone"](waveform="Hexagon")

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_generate_tone_rejects_out_of_range_amplitude(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError, match="amplitude"):
        await fake_mcp.tools["generate_tone"](amplitude=2.0)


@pytest.mark.asyncio
async def test_generate_chirp_builds_correct_params(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["generate_chirp"](start_freq=100.0, end_freq=2000.0)

    fake_bridge.call.assert_called_once_with("apply-effect", {
        "effect_id": "Chirp",
        "params": "StartFreq=100.0 EndFreq=2000.0 StartAmp=0.8 EndAmp=0.1 Waveform=Sine",
    })


@pytest.mark.asyncio
async def test_generate_noise_builds_correct_params(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["generate_noise"](noise_type="Pink", amplitude=0.6)

    fake_bridge.call.assert_called_once_with("apply-effect", {
        "effect_id": "Noise",
        "params": "Type=Pink Amplitude=0.6",
    })


@pytest.mark.asyncio
async def test_generate_noise_rejects_invalid_type(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError, match="noise_type"):
        await fake_mcp.tools["generate_noise"](noise_type="Purple")


@pytest.mark.asyncio
async def test_generate_dtmf_builds_correct_params(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["generate_dtmf"](sequence="12345", duty_cycle=50.0, amplitude=0.7)

    fake_bridge.call.assert_called_once_with("apply-effect", {
        "effect_id": "DTMF Tones",
        "params": 'Sequence=12345 "Duty Cycle"=50.0 Amplitude=0.7',
    })


@pytest.mark.asyncio
async def test_generate_dtmf_rejects_empty_sequence(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError, match="sequence"):
        await fake_mcp.tools["generate_dtmf"](sequence="")
