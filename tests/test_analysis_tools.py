import struct
import wave
from server4.tools.analysis_tools import _measure_wav


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
