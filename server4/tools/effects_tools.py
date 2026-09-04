from mcp.server.fastmcp import FastMCP


def _params(**kwargs) -> str:
    """Format kwargs as Audacity's Key=Value automation string, quoting values
    containing spaces (matches au3-components/EffectAutomationParameters.h's
    shell-tokenized SetParameters() format).

    NOTE: bool values are formatted as "1"/"0", not "True"/"False". Confirmed via
    a crash dump: ShuttleSetAutomation's bool Define() reads through
    wxFileConfig's bool Read(), which parses the stored string as a NUMBER
    (ToLong()) - "True"/"False" fail that parse and silently fall back to the
    parameter's registered default instead of erroring, which is what caused
    NoiseReduction's GetProfile=True to be silently ignored (stayed false) and
    crash on a null mStatistics dereference. This bites every boolean param, not
    just that one - always format bools this way."""
    parts = []
    for key, value in kwargs.items():
        if isinstance(value, bool):
            s = "1" if value else "0"
        else:
            s = str(value)
            if " " in s:
                s = f'"{s}"'
        parts.append(f"{key}={s}")
    return " ".join(parts)


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def normalize(
        peak_level_db: float = -3.0,
        remove_dc: bool = True,
        stereo_independent: bool = False,
    ) -> dict:
        """Normalize the selected audio to a target peak level.

        Args:
            peak_level_db: Target peak level in dB (-145 to 0). Default: -3.0
            remove_dc: Remove DC offset before normalizing. Default: True
            stereo_independent: Normalize L/R channels separately. Default: False
        """
        if not -145 <= peak_level_db <= 0:
            raise ValueError("peak_level_db must be -145 to 0")
        params = _params(
            PeakLevel=peak_level_db, RemoveDcOffset=remove_dc,
            ApplyVolume=True, StereoIndependent=stereo_independent,
        )
        return await bridge.call("apply-effect", {"effect_id": "Normalize", "params": params})

    @mcp.tool()
    async def get_noise_profile() -> dict:
        """Capture a noise profile from the currently selected audio region.
        IMPORTANT: Select a region of pure noise (e.g. 0.5-2 seconds of silence/background
        noise) before calling this. This profile is used by the noise_reduction tool.

        Sets NoiseReductionEffect's GetProfile flag and runs it - the same call the
        "Get Noise Profile" button in Audacity's Noise Reduction dialog makes.
        """
        params = _params(GetProfile=True)
        return await bridge.call("apply-effect", {"effect_id": "Noise reduction", "params": params})

    @mcp.tool()
    async def noise_reduction(
        sensitivity: float = 6.0,
        noise_gain_db: float = 12.0,
        frequency_smoothing_bands: int = 3,
    ) -> dict:
        """Apply noise reduction to the selected audio. You MUST call get_noise_profile
        first on a region of pure noise, then select the audio you want to clean, then
        call this.

        Args:
            sensitivity: Detection sensitivity (0.01-24). Default: 6.0
            noise_gain_db: Amount of noise reduction in dB (0-48). Default: 12.0
            frequency_smoothing_bands: Frequency smoothing bands (0-12). Default: 3
        """
        if not 0.01 <= sensitivity <= 24:
            raise ValueError("sensitivity must be 0.01 to 24")
        if not 0 <= noise_gain_db <= 48:
            raise ValueError("noise_gain_db must be 0 to 48")
        if not 0 <= frequency_smoothing_bands <= 12:
            raise ValueError("frequency_smoothing_bands must be 0 to 12")
        params = _params(**{
            "Sensitivity": sensitivity,
            "Noise Gain": noise_gain_db,
            "Frequency Smoothing Bands": frequency_smoothing_bands,
            "GetProfile": False,
        })
        return await bridge.call("apply-effect", {"effect_id": "Noise reduction", "params": params})

    @mcp.tool()
    async def compressor(
        threshold_db: float = -12.0,
        ratio: float = 4.0,
        attack_ms: float = 3.0,
        release_ms: float = 100.0,
        makeup_gain_db: float = -3.0,
        knee_width_db: float = 6.0,
    ) -> dict:
        """Apply dynamic range compression to the selected audio.

        Args:
            threshold_db: Level above which compression starts (dB). Default: -12
            ratio: Compression ratio (e.g. 4.0 = 4:1). Default: 4.0
            attack_ms: Attack time in milliseconds. Default: 3.0
            release_ms: Release time in milliseconds. Default: 100.0
            makeup_gain_db: Makeup gain applied after compression (dB). Default: -3.0
            knee_width_db: Soft-knee width in dB. Default: 6.0
        """
        params = _params(
            thresholdDb=threshold_db, compressionRatio=ratio, attackMs=attack_ms,
            releaseMs=release_ms, makeupGainDb=makeup_gain_db, kneeWidthDb=knee_width_db,
        )
        return await bridge.call("apply-effect", {"effect_id": "Compressor", "params": params})

    @mcp.tool()
    async def limiter(
        threshold_db: float = -6.0,
        makeup_target_db: float = -1.0,
        release_ms: float = 20.0,
        knee_width_db: float = 2.0,
    ) -> dict:
        """Apply a limiter to prevent audio from exceeding a ceiling.

        Args:
            threshold_db: Level above which limiting starts (dB). Default: -6
            makeup_target_db: Output ceiling (dB) - the industry-standard streaming
                ceiling is -1.0. Default: -1.0
            release_ms: Release time in milliseconds. Default: 20.0
            knee_width_db: Soft-knee width in dB. Default: 2.0
        """
        params = _params(
            thresholdDb=threshold_db, makeupTargetDb=makeup_target_db,
            releaseMs=release_ms, kneeWidthDb=knee_width_db,
        )
        return await bridge.call("apply-effect", {"effect_id": "Limiter", "params": params})

    @mcp.tool()
    async def loudness_normalize(
        lufs_level: float = -16.0,
        stereo_independent: bool = False,
        dual_mono: bool = True,
    ) -> dict:
        """Normalize audio to a target LUFS loudness. DANGER: can boost quiet/badly
        recorded audio by 20-30dB causing clipping - measure levels with
        auto_analyze_audio first. Targets: -16 LUFS (Apple Podcasts), -14 LUFS
        (Spotify/YouTube), -11 LUFS (loud masters).

        Args:
            lufs_level: Target loudness in LUFS (-145 to 0). Default: -16.0
            stereo_independent: Normalize L/R channels independently. Default: False
            dual_mono: Treat mono as dual-mono for correct LUFS measurement. Default: True
        """
        if not -145 <= lufs_level <= 0:
            raise ValueError("lufs_level must be -145 to 0")
        params = _params(
            NormalizeTo=0, StereoIndependent=stereo_independent,
            LUFSLevel=lufs_level, DualMono=dual_mono,
        )
        return await bridge.call("apply-effect", {"effect_id": "Loudness Normalization", "params": params})

    @mcp.tool()
    async def click_removal(threshold: int = 200, spike_width: int = 20) -> dict:
        """Remove clicks and pops from the selected audio (e.g. vinyl recordings).

        Args:
            threshold: Click detection threshold (0-900). Higher = fewer clicks removed. Default: 200
            spike_width: Maximum width of a click in samples (0-40). Default: 20
        """
        if not 0 <= threshold <= 900:
            raise ValueError("threshold must be 0-900")
        if not 0 <= spike_width <= 40:
            raise ValueError("spike_width must be 0-40")
        params = _params(Threshold=threshold, Width=spike_width)
        return await bridge.call("apply-effect", {"effect_id": "Click removal", "params": params})

    @mcp.tool()
    async def bass_and_treble(
        bass: float = 0.0,
        treble: float = 0.0,
        gain: float = 0.0,
    ) -> dict:
        """Adjust bass and treble frequencies with a simple tonal shaping tool.

        Args:
            bass: Bass adjustment in dB (-30 to 30). Default: 0
            treble: Treble adjustment in dB (-30 to 30). Default: 0
            gain: Output gain in dB (-30 to 30). Default: 0
        """
        for name, val in [("bass", bass), ("treble", treble), ("gain", gain)]:
            if not -30 <= val <= 30:
                raise ValueError(f"{name} must be -30 to 30")
        params = _params(Bass=bass, Treble=treble, Gain=gain)
        return await bridge.call("apply-effect", {"effect_id": "Bass and Treble", "params": params})
