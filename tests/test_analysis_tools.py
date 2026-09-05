import struct
import wave
import pytest
from unittest.mock import AsyncMock
import server4.tools.analysis_tools as analysis_tools
from server4.tools.analysis_tools import _measure_wav


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
    analysis_tools.register(fake_mcp)
    return fake_mcp, fake_bridge


def _write_test_wav(path, samples, rate=44100):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def test_measure_wav_detects_peak_level(tmp_path):
    path = tmp_path / "test.wav"
    # Half-scale peak (16384 / 32768 = -6.02 dB)
    _write_test_wav(path, [16384, -16384] * 1000)

    result = _measure_wav(str(path))

    assert result is not None
    assert -6.5 < result["peak_db"] < -5.5


def test_measure_wav_returns_none_for_missing_file():
    result = _measure_wav("does_not_exist.wav")
    assert result is None


def test_measure_wav_detects_silence_gap(tmp_path):
    path = tmp_path / "test.wav"
    # 1 second of loud signal, 1 second of silence, 1 second of loud signal
    loud = [16384, -16384] * 22050
    silence = [0] * 44100
    _write_test_wav(path, loud + silence + loud)

    result = _measure_wav(str(path))

    assert result is not None
    assert result["silence_gap_count"] >= 1


@pytest.mark.asyncio
async def test_analyze_beat_finder_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "ok"}], "isError": False})

    await fake_mcp.tools["analyze_beat_finder"](threshold_percent=50)

    fake_bridge.call.assert_called_once_with(
        "apply-effect", {"effect_id": "Beat finder", "params": "THRESVAL=50"}
    )


@pytest.mark.asyncio
async def test_analyze_beat_finder_default_threshold(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "ok"}], "isError": False})

    await fake_mcp.tools["analyze_beat_finder"]()

    fake_bridge.call.assert_called_once_with(
        "apply-effect", {"effect_id": "Beat finder", "params": "THRESVAL=65"}
    )


@pytest.mark.asyncio
async def test_analyze_beat_finder_rejects_out_of_range(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError, match="5 to 100"):
        await fake_mcp.tools["analyze_beat_finder"](threshold_percent=200)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_analyze_label_sounds_calls_real_command_with_defaults(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "ok"}], "isError": False})

    await fake_mcp.tools["analyze_label_sounds"]()

    fake_bridge.call.assert_called_once_with(
        "apply-effect",
        {
            "effect_id": "Label sounds",
            "params": "THRESHOLD=-30.0 MEASUREMENT=0 SIL-DUR=1.0 SND-DUR=1.0 TYPE=3",
        },
    )


@pytest.mark.asyncio
async def test_analyze_label_sounds_maps_measurement_and_label_type(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "ok"}], "isError": False})

    await fake_mcp.tools["analyze_label_sounds"](measurement="rms", label_type="around")

    fake_bridge.call.assert_called_once_with(
        "apply-effect",
        {
            "effect_id": "Label sounds",
            "params": "THRESHOLD=-30.0 MEASUREMENT=2 SIL-DUR=1.0 SND-DUR=1.0 TYPE=2",
        },
    )


@pytest.mark.asyncio
async def test_analyze_label_sounds_rejects_bad_measurement(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError, match="measurement must be one of"):
        await fake_mcp.tools["analyze_label_sounds"](measurement="not-a-real-measurement")

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_analyze_label_sounds_rejects_bad_label_type(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError, match="label_type must be one of"):
        await fake_mcp.tools["analyze_label_sounds"](label_type="not-a-real-type")

    fake_bridge.call.assert_not_called()
