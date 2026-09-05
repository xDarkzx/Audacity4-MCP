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
    just that one - always format bools this way.

    NOTE: keys containing spaces (e.g. Paulstretch's "Stretch Factor") must also
    be quoted. SetParameters() tokenizes the whole string via
    wxCmdLineParser::ConvertStringToArgs BEFORE splitting each token on "=" -
    an unquoted "Stretch Factor=5.0" tokenizes as two separate args ("Stretch"
    and "Factor=5.0"), silently losing the parameter. Quoting just the key
    ("Stretch Factor"=5.0, quote immediately followed by = with no space)
    keeps it one token while leaving the "=value" part outside the quotes,
    exactly like SetParameters' own tokenizer expects."""
    parts = []
    for key, value in kwargs.items():
        if isinstance(value, bool):
            s = "1" if value else "0"
        else:
            s = str(value)
            if " " in s:
                s = f'"{s}"'
        k = f'"{key}"' if " " in key else key
        parts.append(f"{k}={s}")
    return " ".join(parts)


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def list_effects(
        category: str = "",
        family: str = "",
        search: str = "",
        limit: int = 100,
    ) -> dict:
        """List available effects/plugins actually installed in this Audacity -
        builtin, VST3, Nyquist, etc. Each result's "title" is the effect_id to
        pass to apply-effect (or any effect_* tool's underlying command) - that
        path resolves by title with a fallback. Its "id" is the real internal
        PluginID, which add_realtime_effect REQUIRES instead - confirmed live
        that passing a title there fails ("cannot load the effect"), since
        RealtimeEffectService::addRealtimeEffect has no title fallback.

        IMPORTANT (confirmed live): "category" only works for Builtin/Nyquist
        effects - third-party VST3 plugins are NOT auto-categorized by
        Audacity's discovery (they all come back with category "None", even
        real reverbs/delays like Valhalla's whole lineup). To find VST
        effects, use family="VST3" combined with a search keyword (plugin
        name or vendor, e.g. search="valhalla" for reverb/delay VSTs) -
        category filtering will silently miss them.

        Args:
            category: Category substring filter (case-insensitive), e.g.
                "reverb", "eq", "compression", "distortion", "pitch", "fading".
                Only matches Builtin/Nyquist effects - see note above.
            family: Exact family filter: "Builtin", "VST3", "Nyquist", "LV2",
                "AudioUnit", or "Extension". Default: no filter.
            search: Title substring filter (case-insensitive).
            limit: Max results to return, 1+. Default: 100. Check
                "totalMatched" in the response to see if results were capped.
        """
        if limit < 1:
            raise ValueError("limit must be >= 1")
        params = {}
        if category:
            params["category"] = category
        if family:
            params["family"] = family
        if search:
            params["search"] = search
        params["limit"] = limit
        return await bridge.call("list-effects", params)

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

    @mcp.tool()
    async def effect_amplify(ratio: float = 1.0, allow_clipping: bool = False) -> dict:
        """Amplify (or attenuate) the selected audio by a linear ratio.

        Args:
            ratio: Amplification ratio (e.g. 2.0 = +6dB, 0.5 = -6dB). Range: 0.003162-316.227766. Default: 1.0
            allow_clipping: Allow the result to clip instead of being limited. Default: False
        """
        if not 0.003162 <= ratio <= 316.227766:
            raise ValueError("ratio must be 0.003162 to 316.227766")
        params = _params(Ratio=ratio, AllowClipping=allow_clipping)
        return await bridge.call("apply-effect", {"effect_id": "Amplify", "params": params})

    @mcp.tool()
    async def effect_fade_in() -> dict:
        """Apply a fade-in to the selected audio. Select the region to fade first."""
        return await bridge.call("apply-effect", {"effect_id": "Fade In", "params": ""})

    @mcp.tool()
    async def effect_fade_out() -> dict:
        """Apply a fade-out to the selected audio. Select the region to fade first."""
        return await bridge.call("apply-effect", {"effect_id": "Fade Out", "params": ""})

    @mcp.tool()
    async def effect_reverb(
        room_size: float = 75.0,
        pre_delay: float = 10.0,
        reverberance: float = 50.0,
        hf_damping: float = 50.0,
        tone_low: float = 100.0,
        tone_high: float = 100.0,
        wet_gain: float = -1.0,
        dry_gain: float = -1.0,
        stereo_width: float = 100.0,
        wet_only: bool = False,
    ) -> dict:
        """Apply reverb to the selected audio.

        Args:
            room_size: Room size percentage (0-100). Default: 75
            pre_delay: Pre-delay in ms (0-200). Default: 10
            reverberance: Reverberance percentage (0-100). Default: 50
            hf_damping: High frequency damping percentage (0-100). Default: 50
            tone_low: Tone low percentage (0-100). Default: 100
            tone_high: Tone high percentage (0-100). Default: 100
            wet_gain: Wet signal gain in dB (-20 to 10). Default: -1.0
            dry_gain: Dry signal gain in dB (-20 to 10). Default: -1.0
            stereo_width: Stereo width percentage (0-100). Default: 100
            wet_only: Output only the wet (reverb) signal. Default: False
        """
        for name, val, lo, hi in [
            ("room_size", room_size, 0, 100), ("pre_delay", pre_delay, 0, 200),
            ("reverberance", reverberance, 0, 100), ("hf_damping", hf_damping, 0, 100),
            ("tone_low", tone_low, 0, 100), ("tone_high", tone_high, 0, 100),
            ("wet_gain", wet_gain, -20, 10), ("dry_gain", dry_gain, -20, 10),
            ("stereo_width", stereo_width, 0, 100),
        ]:
            if not lo <= val <= hi:
                raise ValueError(f"{name} must be {lo} to {hi}")
        params = _params(
            RoomSize=room_size, Delay=pre_delay, Reverberance=reverberance,
            HfDamping=hf_damping, ToneLow=tone_low, ToneHigh=tone_high,
            WetGain=wet_gain, DryGain=dry_gain, StereoWidth=stereo_width, WetOnly=wet_only,
        )
        return await bridge.call("apply-effect", {"effect_id": "Reverb", "params": params})

    @mcp.tool()
    async def effect_change_pitch(semitones: float = 0.0, use_high_quality_stretching: bool = False) -> dict:
        """Change the pitch of the selected audio without changing tempo.

        Args:
            semitones: Number of semitones to shift (negative = lower, positive = higher)
            use_high_quality_stretching: Use the higher-quality SBSMS algorithm (slower). Default: False
        """
        # v4's ChangePitch effect's real automation param is Percentage (percent change of
        # frequency), not Semitones - verified against ChangePitchBase.h's EffectParameter
        # Percentage declaration. Convert: a semitone shift multiplies frequency by
        # 2^(semitones/12); percent change is that multiplier expressed as (multiplier-1)*100.
        percentage = 100.0 * (2.0 ** (semitones / 12.0) - 1.0)
        if not -99.0 <= percentage <= 3000.0:
            raise ValueError("semitones out of range - resulting percentage must be -99 to 3000")
        params = _params(Percentage=round(percentage, 6), SBSMS=use_high_quality_stretching)
        return await bridge.call("apply-effect", {"effect_id": "Change pitch", "params": params})

    @mcp.tool()
    async def effect_paulstretch(stretch_factor: float = 10.0, time_resolution: float = 0.25) -> dict:
        """Extreme time-stretch effect (creates ambient/drone textures). Select audio first.

        Args:
            stretch_factor: How much to stretch (1.0 = no change, 10.0 = 10x longer). Default: 10.0
            time_resolution: Time resolution in seconds - smaller = better quality, slower (>= 0.00099). Default: 0.25
        """
        if stretch_factor < 1.0:
            raise ValueError("stretch_factor must be >= 1.0")
        if time_resolution < 0.00099:
            raise ValueError("time_resolution must be >= 0.00099")
        params = _params(**{"Stretch Factor": stretch_factor, "Time Resolution": time_resolution})
        return await bridge.call("apply-effect", {"effect_id": "Paulstretch", "params": params})

    @mcp.tool()
    async def effect_reverse() -> dict:
        """Reverse the selected audio. Select a region first."""
        return await bridge.call("apply-effect", {"effect_id": "Reverse", "params": ""})

    @mcp.tool()
    async def effect_invert() -> dict:
        """Invert (flip phase) the selected audio. Useful for phase cancellation."""
        return await bridge.call("apply-effect", {"effect_id": "Invert", "params": ""})

    @mcp.tool()
    async def effect_repair() -> dict:
        """Repair a very short damaged section of audio (a few dozen samples at most).
        Select the damaged region first - it must be extremely short, or the effect
        will refuse to run."""
        return await bridge.call("apply-effect", {"effect_id": "Repair", "params": ""})

    @mcp.tool()
    async def effect_sliding_stretch(
        rate_change_start: float = 0.0,
        rate_change_end: float = 0.0,
        pitch_change_start_semitones: float = 0.0,
        pitch_change_end_semitones: float = 0.0,
    ) -> dict:
        """Change tempo and/or pitch gradually across the selection (sliding time stretch).

        Args:
            rate_change_start: Tempo change at start in % (-90 to 500). Default: 0
            rate_change_end: Tempo change at end in % (-90 to 500). Default: 0
            pitch_change_start_semitones: Pitch change at start in semitones (-12 to 12). Default: 0
            pitch_change_end_semitones: Pitch change at end in semitones (-12 to 12). Default: 0
        """
        # DISABLED - live-tested and confirmed this reliably crashes/hangs the app.
        # SlidingStretchEffect is built on SBSMSBase (au3-builtin-effects/SBSMSBase.h),
        # which is part of the "extension effects" family - invoking it the first time
        # in a session triggers ExtensionEffectsModule::reloadExtensions(), which
        # re-runs EVERY module's onInit() (confirmed via app log: the same
        # "CommandsRegister::reg | ASSERT FAILED: m_modules.find(moduleName) ==
        # m_modules.end()" pattern fires again right as this effect is invoked, the
        # same bug class fixed for the mcp module itself in mcpmodule.cpp - but other
        # modules besides mcp aren't guarded against re-entrant init, and one of them
        # crashes). This is a real, structural, pre-existing engine issue - not
        # something fixable from the Python/MCP layer, and auditing every module in
        # the app for idempotent init is out of scope here. Reproduced twice: once
        # with a 2s selection (app hang, killed by Windows after ~10s unresponsive),
        # once with a 0.2s selection (crashed within 6s) - ruling out "just slow".
        raise RuntimeError(
            "effect_sliding_stretch is currently disabled - live-testing confirmed it "
            "reliably crashes/hangs the app (a pre-existing engine bug where this "
            "SBSMS-family effect's first invocation triggers an extension reload that "
            "isn't safe across all modules, not something fixable at the MCP layer). "
            "Use effect_change_pitch for pitch-only changes instead."
        )
        for name, val in [("rate_change_start", rate_change_start), ("rate_change_end", rate_change_end)]:
            if not -90 <= val <= 500:
                raise ValueError(f"{name} must be -90 to 500")
        for name, val in [
            ("pitch_change_start_semitones", pitch_change_start_semitones),
            ("pitch_change_end_semitones", pitch_change_end_semitones),
        ]:
            if not -12 <= val <= 12:
                raise ValueError(f"{name} must be -12 to 12")
        params = _params(
            RatePercentChangeStart=rate_change_start, RatePercentChangeEnd=rate_change_end,
            PitchHalfStepsStart=pitch_change_start_semitones, PitchHalfStepsEnd=pitch_change_end_semitones,
        )
        return await bridge.call("apply-effect", {"effect_id": "Sliding stretch", "params": params})

    # NOTE: v3 also had echo, change_tempo, change_speed, equalization, phaser,
    # wahwah, distortion, repeat, high_pass_filter, low_pass_filter, and auto_duck.
    # Confirmed via this build's actual runtime plugin registry
    # (known_audio_plugins.json, cross-checked against the live "Effect not found"
    # errors these produced) that NONE of these are registered as builtin effects
    # in this fork - only 27 builtin effects exist total (Amplify, Bass and Treble,
    # Change pitch, Chirp, Click removal, Compressor, DTMF Tones, Fade In/Out,
    # Filter Curve EQ, Graphic EQ, Invert, Limiter, Loudness Normalization, Noise,
    # Noise reduction, Normalize, Nyquist prompt, Paulstretch, Remove DC offset,
    # Repair, Reverb, Reverse, Silence, Sliding stretch, Tone, Truncate silence).
    # The au3/src/effects/*.cpp source for Echo/Repeat/ChangeTempo/etc. still
    # exists in the tree but its BuiltinEffectsModule::Registration<T> static
    # instances never link into this build - source presence does not imply
    # availability, verify against the real registry, not just the source tree.
    # "Equalization" was NOT simply renamed - v4 split it into two separate,
    # different effects ("Filter Curve EQ" and "Graphic EQ"), not a drop-in
    # substitute for v3's curve_name-based API - not wrapped here, would need
    # its own design pass.

    @mcp.tool()
    async def effect_remove_dc_offset() -> dict:
        """Remove DC offset from the selected audio without changing its peak level.

        v4's "Remove DC offset" is invoked here as Normalize with only the DC
        checkbox on and level-normalization off (ApplyVolume=0) - confirmed the
        same parameter set as the already-verified normalize() tool, just with
        volume application disabled. Takes no parameters."""
        params = _params(RemoveDcOffset=True, ApplyVolume=False, StereoIndependent=False)
        return await bridge.call("apply-effect", {"effect_id": "Normalize", "params": params})

    _FADE_TYPES = {"Up": 0, "Down": 1, "SCurveUp": 2, "SCurveDown": 3}

    @mcp.tool()
    async def effect_adjustable_fade(
        fade_type: str = "Up", mid_fade_adjust_percent: float = 0.0, units: str = "Percent",
        start_level: float = 0.0, end_level: float = 100.0,
    ) -> dict:
        """Apply a customizable fade to the selected audio.

        Requires a SINGLE-clip selection - confirmed live that a selection
        spanning multiple clips triggers an unguarded assert/crash
        (Au3SelectionController::rightMostSelectedClipEndTime). A clean
        single-clip selection was also confirmed live to work correctly
        (isError: false, no crash). Normalize has the same "single clip only"
        precondition but fails gracefully with a normal error instead of
        crashing when violated - this one does not, so get the selection right.

        Args:
            fade_type: "Up", "Down", "SCurveUp", or "SCurveDown". Default: "Up"
            mid_fade_adjust_percent: Adjusts the fade curve's midpoint, -100 to 100. Default: 0.0
            units: Interpret start_level/end_level as "Percent" (of original) or "dB" gain. Default: "Percent"
            start_level: Level at the start of the fade. Default: 0.0
            end_level: Level at the end of the fade. Default: 100.0
        """
        if fade_type not in _FADE_TYPES:
            raise ValueError(f"fade_type must be one of: {', '.join(_FADE_TYPES)}")
        if not -100 <= mid_fade_adjust_percent <= 100:
            raise ValueError("mid_fade_adjust_percent must be -100 to 100")
        if units not in ("Percent", "dB"):
            raise ValueError('units must be "Percent" or "dB"')
        params = _params(**{
            "TYPE": _FADE_TYPES[fade_type], "CURVE": mid_fade_adjust_percent,
            "UNITS": 0 if units == "Percent" else 1,
            "GAIN0": start_level, "GAIN1": end_level, "PRESET": 0,
        })
        return await bridge.call("apply-effect", {"effect_id": "Adjustable fade", "params": params})

    @mcp.tool()
    async def truncate_silence(
        threshold_db: float = -20.0, minimum_silence: float = 0.5,
        truncate_to: float = 0.5, compress_ratio: float = 50.0, independent_channels: bool = False,
    ) -> dict:
        """Find and shorten runs of silence in the selected audio.

        Args:
            threshold_db: Silence threshold in dB, -80 to -20. Default: -20.0
            minimum_silence: Minimum silence duration to detect, in seconds, >= 0.001. Default: 0.5
            truncate_to: Duration to truncate silence down to, in seconds. Default: 0.5
            compress_ratio: Percent to compress the remaining silence by, 0-99.9. Default: 50.0
            independent_channels: Detect silence independently per channel. Default: False
        """
        params = _params(
            Threshold=threshold_db, Minimum=minimum_silence, Truncate=truncate_to,
            Compress=compress_ratio, Independent=independent_channels,
        )
        return await bridge.call("apply-effect", {"effect_id": "Truncate silence", "params": params})

    # --- Nyquist plugins below, all live-verified: effect_id resolution and
    # actual execution confirmed against the running app for clip_fix,
    # crossfade_clips, studio_fade_out, notch_filter, tremolo.
    #
    # NOTE on preconditions: an effect call that fails its own precondition
    # check (e.g. crossfade_clips called without 2+ overlapping clips selected)
    # opens a native modal error dialog that blocks the ENTIRE app - including
    # further TCP command processing - until a human dismisses it. An MCP-only
    # caller has no way to dismiss this itself, so a bad-precondition call can
    # stall the session indefinitely. Always ensure real preconditions are met
    # (right number of tracks/clips selected, overlap exists, etc.) before
    # calling these - don't rely on the error response to fail fast.

    @mcp.tool()
    async def effect_clip_fix(threshold: float = 95.0, gain_db: float = -9.0) -> dict:
        """Repair clipped (distorted) peaks in the selected audio.

        Args:
            threshold: Clipping threshold percent, 0-100. Default: 95.0
            gain_db: Gain adjustment in dB, -30 to 0. Default: -9.0
        """
        params = _params(THRESHOLD=threshold, GAIN=gain_db)
        return await bridge.call("apply-effect", {"effect_id": "Clip fix", "params": params})

    @mcp.tool()
    async def effect_crossfade_clips() -> dict:
        """Crossfade the overlap between two adjacent, overlapping clips. Select the
        overlapping region across both clips first. Takes no parameters."""
        return await bridge.call("apply-effect", {"effect_id": "Crossfade clips", "params": ""})

    @mcp.tool()
    async def effect_crossfade_tracks(curve_type: int = 0) -> dict:
        """Crossfade the selected region between two overlapping tracks.

        Args:
            curve_type: 0=Constant Gain, 1=Constant Power (1), 2=Constant Power (2),
                3=Custom Curve. Default: 0
        """
        if not 0 <= curve_type <= 3:
            raise ValueError("curve_type must be 0-3")
        params = _params(TYPE=curve_type)
        return await bridge.call("apply-effect", {"effect_id": "Crossfade tracks", "params": params})

    @mcp.tool()
    async def effect_studio_fade_out() -> dict:
        """Apply a smoother, more natural fade-out than effect_fade_out to the
        selected audio. Takes no parameters."""
        return await bridge.call("apply-effect", {"effect_id": "Studio fade out", "params": ""})

    @mcp.tool()
    async def effect_notch_filter(frequency_hz: float = 60.0, q: float = 1.0) -> dict:
        """Apply a notch filter to remove a narrow frequency band (e.g. mains hum)
        from the selected audio.

        Args:
            frequency_hz: Center frequency to notch out in Hz, > 0. Default: 60.0
            q: Q (narrowness) of the notch, 0.1-1000. Default: 1.0
        """
        if frequency_hz <= 0:
            raise ValueError("frequency_hz must be > 0")
        if not 0.1 <= q <= 1000:
            raise ValueError("q must be 0.1 to 1000")
        params = _params(FREQUENCY=frequency_hz, Q=q)
        return await bridge.call("apply-effect", {"effect_id": "Notch filter", "params": params})

    @mcp.tool()
    async def effect_tremolo(
        wave_type: int = 0, phase_degrees: int = 0, wet_percent: int = 40, lfo_hz: float = 4.0,
    ) -> dict:
        """Apply a tremolo (amplitude modulation) effect to the selected audio.

        Args:
            wave_type: 0=Sine, 1=Triangle, 2=Sawtooth, 3=Inverse Sawtooth, 4=Square. Default: 0
            phase_degrees: LFO starting phase, -180 to 180. Default: 0
            wet_percent: Wet mix percent, 1-100. Default: 40
            lfo_hz: LFO rate in Hz, 0.001-1000. Default: 4.0
        """
        if not 0 <= wave_type <= 4:
            raise ValueError("wave_type must be 0-4")
        params = _params(WAVE=wave_type, PHASE=phase_degrees, WET=wet_percent, LFO=lfo_hz)
        return await bridge.call("apply-effect", {"effect_id": "Tremolo", "params": params})
