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


def _analyze_with_measurements(monkeypatch, measurements, **kwargs):
    """Runs auto_analyze_audio against fixed measurements, bypassing the real export."""
    import asyncio
    fake_mcp, _ = _fake_mcp_with(monkeypatch, {"ok": True})
    monkeypatch.setattr(analysis_tools.os.path, "exists", lambda p: True)
    monkeypatch.setattr(analysis_tools.os.path, "getsize", lambda p: 1_000_000)
    monkeypatch.setattr(analysis_tools, "_measure_wav", lambda p: measurements)
    return asyncio.run(fake_mcp.tools["auto_analyze_audio"](**kwargs))


# Measurements taken from a real 50s ambient music mix. Read as speech these look
# alarming (SNR 14.3 dB, floor -15.7 dB) but the "noise" is the music itself.
_AMBIENT_MIX = {
    "peak_db": -1.4,
    "noise_floor_db": -15.7,
    "overall_rms_db": -16.3,
    "clipped_samples": 0,
    "dc_offset": -0.000015,
    "click_count": 44,
    "silence_gaps": [],
    "silence_gap_count": 0,
    "dynamic_range_db": 3.5,
    "duration": 50.57,
}


def test_continuous_music_is_not_reported_as_noisy(monkeypatch):
    result = _analyze_with_measurements(monkeypatch, _AMBIENT_MIX)
    assert result["content_type_used"] == "music"
    joined = " ".join(result["issues"])
    assert "NOISY" not in joined
    assert "HIGH NOISE FLOOR" not in joined
    assert "CLICKS" not in joined
    assert "auto_master_music" in result["recommendation"]


def test_same_audio_read_as_speech_still_flags_noise(monkeypatch):
    result = _analyze_with_measurements(monkeypatch, _AMBIENT_MIX, content_type="speech")
    assert result["content_type_used"] == "speech"
    joined = " ".join(result["issues"])
    assert "HIGH NOISE FLOOR" in joined
    assert "auto_cleanup_podcast" in result["recommendation"]


def test_speech_with_pauses_is_detected_as_speech(monkeypatch):
    speech = dict(_AMBIENT_MIX)
    speech.update({"silence_gaps": [(1.0, 0.8)], "silence_gap_count": 1})
    result = _analyze_with_measurements(monkeypatch, speech)
    assert result["content_type_used"] == "speech"


def test_music_recommendation_lists_every_music_pipeline(monkeypatch):
    rec = _analyze_with_measurements(monkeypatch, _AMBIENT_MIX)["recommendation"]
    for tool in ("auto_master_music", "auto_lofi_effect", "auto_cleanup_audio"):
        assert tool in rec


def test_speech_recommendation_lists_pipelines_that_were_previously_hidden(monkeypatch):
    rec = _analyze_with_measurements(monkeypatch, _AMBIENT_MIX, content_type="speech")["recommendation"]
    for tool in ("auto_cleanup_interview", "auto_cleanup_vocal", "auto_cleanup_live"):
        assert tool in rec
