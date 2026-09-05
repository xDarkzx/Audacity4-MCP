from mcp.server.fastmcp import FastMCP

from server4.tools.effects_tools import _params

# NOTE Duration is NOT an automation parameter for any generator in this v4 fork -
# verified against GeneratorEffect (src/effects/builtin_collection/common/generatoreffect.h),
# whose duration()/setDuration() are plain C++ methods, not wired through the
# EffectParameter/Parameters() system that the classic Key=Value automation string
# feeds into. Generators fill whatever time range is currently selected - call
# select_region (or select_all) first to control how long the generated audio is.

_WAVEFORMS = {"Sine", "Square", "Sawtooth", "Square, no alias", "Triangle"}
_NOISE_TYPES = {"White", "Pink", "Brownian"}


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def generate_tone(
        waveform: str = "Sine",
        frequency: float = 440.0,
        amplitude: float = 0.8,
    ) -> dict:
        """Generate a tone. Fills the currently selected time range - call select_region
        first to control duration.

        Args:
            waveform: "Sine", "Square", "Sawtooth", "Square, no alias", or "Triangle". Default: "Sine"
            frequency: Frequency in Hz (>= 1). Default: 440
            amplitude: Amplitude (0-1). Default: 0.8
        """
        if waveform not in _WAVEFORMS:
            raise ValueError(f"waveform must be one of: {', '.join(sorted(_WAVEFORMS))}")
        if frequency < 1:
            raise ValueError("frequency must be >= 1")
        if not 0 <= amplitude <= 1:
            raise ValueError("amplitude must be 0-1")
        params = _params(Frequency=frequency, Amplitude=amplitude, Waveform=waveform)
        return await bridge.call("apply-effect", {"effect_id": "Tone", "params": params})

    @mcp.tool()
    async def generate_chirp(
        waveform: str = "Sine",
        start_freq: float = 440.0,
        end_freq: float = 1320.0,
        start_amp: float = 0.8,
        end_amp: float = 0.1,
    ) -> dict:
        """Generate a chirp (frequency sweep). Fills the currently selected time range -
        call select_region first to control duration.

        Args:
            waveform: "Sine", "Square", "Sawtooth", "Square, no alias", or "Triangle". Default: "Sine"
            start_freq: Starting frequency in Hz (>= 1). Default: 440
            end_freq: Ending frequency in Hz (>= 1). Default: 1320
            start_amp: Starting amplitude (0-1). Default: 0.8
            end_amp: Ending amplitude (0-1). Default: 0.1
        """
        if waveform not in _WAVEFORMS:
            raise ValueError(f"waveform must be one of: {', '.join(sorted(_WAVEFORMS))}")
        if start_freq < 1 or end_freq < 1:
            raise ValueError("start_freq/end_freq must be >= 1")
        if not 0 <= start_amp <= 1 or not 0 <= end_amp <= 1:
            raise ValueError("start_amp/end_amp must be 0-1")
        params = _params(
            StartFreq=start_freq, EndFreq=end_freq,
            StartAmp=start_amp, EndAmp=end_amp, Waveform=waveform,
        )
        return await bridge.call("apply-effect", {"effect_id": "Chirp", "params": params})

    @mcp.tool()
    async def generate_noise(noise_type: str = "White", amplitude: float = 0.8) -> dict:
        """Generate noise. Fills the currently selected time range - call select_region
        first to control duration.

        Args:
            noise_type: "White", "Pink", or "Brownian". Default: "White"
            amplitude: Amplitude (0-1). Default: 0.8
        """
        if noise_type not in _NOISE_TYPES:
            raise ValueError(f"noise_type must be one of: {', '.join(sorted(_NOISE_TYPES))}")
        if not 0 <= amplitude <= 1:
            raise ValueError("amplitude must be 0-1")
        params = _params(Type=noise_type, Amplitude=amplitude)
        return await bridge.call("apply-effect", {"effect_id": "Noise", "params": params})

    @mcp.tool()
    async def generate_dtmf(
        sequence: str = "audacity",
        duty_cycle: float = 55.0,
        amplitude: float = 0.8,
    ) -> dict:
        """Generate DTMF (telephone) tones. Fills the currently selected time range -
        call select_region first to control duration.

        Args:
            sequence: Text to encode as DTMF tones. Default: "audacity" (Audacity's own default)
            duty_cycle: Tone vs silence ratio percentage (0-100). Default: 55
            amplitude: Amplitude (0-1). Default: 0.8
        """
        if not sequence:
            raise ValueError("sequence must not be empty")
        if not 0 <= duty_cycle <= 100:
            raise ValueError("duty_cycle must be 0-100")
        if not 0 <= amplitude <= 1:
            raise ValueError("amplitude must be 0-1")
        params = _params(Sequence=sequence, **{"Duty Cycle": duty_cycle}, Amplitude=amplitude)
        return await bridge.call("apply-effect", {"effect_id": "DTMF Tones", "params": params})

    @mcp.tool()
    async def generate_silence() -> dict:
        """Generate silence. Fills the currently selected time range - call
        select_region first to control duration. Takes no parameters."""
        return await bridge.call("apply-effect", {"effect_id": "Silence", "params": ""})

    _CLICK_TYPES = {
        "Metronome": 0, "Ping (short)": 1, "Ping (long)": 2, "Cowbell": 3,
        "ResonantNoise": 4, "NoiseClick": 5, "Drip (short)": 6, "Drip (long)": 7,
    }

    @mcp.tool()
    async def generate_rhythm_track(
        tempo_bpm: float = 120.0, beats_per_bar: int = 4, swing: float = 0.0,
        num_bars: int = 16, duration_seconds: float = 0.0, start_offset: float = 0.0,
        click_type: str = "Metronome", strong_beat_pitch: int = 84, weak_beat_pitch: int = 80,
    ) -> dict:
        """Generate a metronome/click rhythm track.

        Args:
            tempo_bpm: Tempo, 30-300 beats/minute. Default: 120.0
            beats_per_bar: Time signature numerator, 1-20. Default: 4
            swing: Swing amount, -1 to 1. Default: 0.0
            num_bars: Number of bars to generate, 0-1000. Set to 0 to use
                duration_seconds instead. Default: 16
            duration_seconds: Duration to fill, used only when num_bars is 0. Default: 0.0
            start_offset: Silence before the first beat, in seconds. Default: 0.0
            click_type: One of: Metronome, Ping (short), Ping (long), Cowbell,
                ResonantNoise, NoiseClick, Drip (short), Drip (long). Default: "Metronome"
            strong_beat_pitch: MIDI pitch of the strong (first) beat, 18-116. Default: 84
            weak_beat_pitch: MIDI pitch of weak beats, 18-116. Default: 80
        """
        if not 30 <= tempo_bpm <= 300:
            raise ValueError("tempo_bpm must be 30 to 300")
        if not 1 <= beats_per_bar <= 20:
            raise ValueError("beats_per_bar must be 1 to 20")
        if not -1 <= swing <= 1:
            raise ValueError("swing must be -1 to 1")
        if not 0 <= num_bars <= 1000:
            raise ValueError("num_bars must be 0 to 1000")
        if click_type not in _CLICK_TYPES:
            raise ValueError(f"click_type must be one of: {', '.join(_CLICK_TYPES)}")
        if not 18 <= strong_beat_pitch <= 116 or not 18 <= weak_beat_pitch <= 116:
            raise ValueError("strong_beat_pitch/weak_beat_pitch must be 18 to 116")
        params = _params(**{
            "TEMPO": tempo_bpm, "TIMESIG": beats_per_bar, "SWING": swing,
            "BARS": num_bars, "CLICK-TRACK-DUR": duration_seconds, "OFFSET": start_offset,
            "CLICK-TYPE": _CLICK_TYPES[click_type], "HIGH": strong_beat_pitch, "LOW": weak_beat_pitch,
        })
        return await bridge.call("apply-effect", {"effect_id": "Rhythm track", "params": params})
