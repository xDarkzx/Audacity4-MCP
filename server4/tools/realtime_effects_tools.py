from mcp.server.fastmcp import FastMCP

MASTER_TRACK_ID = -2


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def add_realtime_effect(track_id: int, effect_id: str) -> dict:
        """Add a non-destructive realtime effect to a track's (or the Master
        bus's) effect chain. Unlike apply-effect/effect_* tools, this stays
        adjustable and removable afterward - the actual VST/plugin GUI can
        still be opened live in Audacity to tweak it, same as adding it by
        hand via the Realtime Effects panel.

        Args:
            track_id: Track id, from project_get_info's track list. Use -2
                for the Master bus.
            effect_id: The real PluginID, from list_effects' "id" field - NOT
                "title". Confirmed live: passing a title here fails with
                "cannot load the effect" (this path has no title fallback,
                unlike apply-effect).
        """
        return await bridge.call("add-realtime-effect", {"track_id": track_id, "effect_id": effect_id})

    @mcp.tool()
    async def list_realtime_effects(track_id: int) -> dict:
        """List the realtime effect chain on a track or the Master bus, with
        each effect's index (for remove_realtime_effect/set_realtime_effect_active),
        name, and active state.

        Args:
            track_id: Track id, from project_get_info's track list. Use -2
                for the Master bus.
        """
        return await bridge.call("list-realtime-effects", {"track_id": track_id})

    @mcp.tool()
    async def remove_realtime_effect(track_id: int, index: int) -> dict:
        """Remove one effect from a track's (or the Master bus's) realtime
        effect chain by index.

        Args:
            track_id: Track id, from project_get_info's track list. Use -2
                for the Master bus.
            index: Position in the chain, from list_realtime_effects.
        """
        if index < 0:
            raise ValueError("index must be >= 0")
        return await bridge.call("remove-realtime-effect", {"track_id": track_id, "index": index})

    @mcp.tool()
    async def set_realtime_effect_active(track_id: int, index: int, active: bool) -> dict:
        """Enable or bypass one effect in a track's (or the Master bus's)
        realtime effect chain, without removing it.

        Args:
            track_id: Track id, from project_get_info's track list. Use -2
                for the Master bus.
            index: Position in the chain, from list_realtime_effects.
            active: True to enable, False to bypass.
        """
        if index < 0:
            raise ValueError("index must be >= 0")
        return await bridge.call("set-realtime-effect-active", {"track_id": track_id, "index": index, "active": active})

    @mcp.tool()
    async def list_effect_parameters(track_id: int, index: int) -> dict:
        """List a realtime effect's real, plugin-reported parameters - name,
        units, min/max/default/current value, and a human-formatted current
        value string. Works uniformly across Builtin/VST3/LV2/AudioUnit
        plugins via Audacity's own parameter-extraction layer - no need to
        guess a plugin's parameter names or ranges (e.g. a reverb's actual
        "Mix"/"Decay"/"Size" parameters, a compressor's "Threshold"/"Ratio").

        Args:
            track_id: Track id, from project_get_info's track list. Use -2
                for the Master bus.
            index: Position in the chain, from list_realtime_effects.
        """
        if index < 0:
            raise ValueError("index must be >= 0")
        return await bridge.call("list-effect-parameters", {"track_id": track_id, "index": index})

    @mcp.tool()
    async def set_effect_parameter(track_id: int, index: int, parameter_id: str, value: float) -> dict:
        """Set one real-time parameter on a realtime effect to an exact value -
        e.g. the actual wet/dry mix or decay time of a reverb, not just
        add/remove/bypass the whole effect.

        Args:
            track_id: Track id, from project_get_info's track list. Use -2
                for the Master bus.
            index: Position in the chain, from list_realtime_effects.
            parameter_id: Parameter id, from list_effect_parameters' "id" field.
            value: New value within [minValue, maxValue] from list_effect_parameters.
                CONFIRMED LIVE: for VST3 plugins this range is typically
                normalized 0-1, NOT real display units, even though
                list_effect_parameters' currentValueString shows a real unit
                (e.g. "21.26 s") - after setting, re-read currentValueString
                to see the actual resulting value, don't assume the input
                scale matches it.
        """
        if index < 0:
            raise ValueError("index must be >= 0")
        if not parameter_id:
            raise ValueError("parameter_id must not be empty")
        return await bridge.call(
            "set-effect-parameter",
            {"track_id": track_id, "index": index, "parameter_id": parameter_id, "value": value},
        )

    @mcp.tool()
    async def list_effect_presets(track_id: int, index: int) -> dict:
        """List a realtime effect's real factory presets (e.g. a reverb's named
        room/hall presets), if the plugin format exposes any. Not every plugin
        has factory presets - an empty list is a normal result, not an error.

        Args:
            track_id: Track id, from project_get_info's track list. Use -2
                for the Master bus.
            index: Position in the chain, from list_realtime_effects.
        """
        if index < 0:
            raise ValueError("index must be >= 0")
        return await bridge.call("list-effect-presets", {"track_id": track_id, "index": index})

    @mcp.tool()
    async def apply_effect_preset(track_id: int, index: int, preset_id: str) -> dict:
        """Apply one of a realtime effect's factory presets by id.

        Args:
            track_id: Track id, from project_get_info's track list. Use -2
                for the Master bus.
            index: Position in the chain, from list_realtime_effects.
            preset_id: Preset id, from list_effect_presets.
        """
        if index < 0:
            raise ValueError("index must be >= 0")
        if not preset_id:
            raise ValueError("preset_id must not be empty")
        return await bridge.call("apply-effect-preset", {"track_id": track_id, "index": index, "preset_id": preset_id})
