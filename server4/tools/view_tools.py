from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def view_toggle_effects() -> dict:
        """Toggle the effects panel visibility."""
        return await bridge.dispatch("toggle-effects")

    @mcp.tool()
    async def view_toggle_label_editor() -> dict:
        """Toggle the label editor panel."""
        return await bridge.dispatch("toggle-label-editor")

    @mcp.tool()
    async def view_toggle_vertical_rulers() -> dict:
        """Toggle vertical rulers on tracks."""
        return await bridge.dispatch("toggle-vertical-rulers")

    @mcp.tool()
    async def view_toggle_clipping() -> dict:
        """Toggle clipping indicators in waveform."""
        return await bridge.dispatch("toggle-clipping-in-waveform")

    @mcp.tool()
    async def view_toggle_rms() -> dict:
        """Toggle RMS display in waveform."""
        return await bridge.dispatch("toggle-rms-in-waveform")

    @mcp.tool()
    async def view_fullscreen() -> dict:
        """Toggle fullscreen mode."""
        return await bridge.dispatch("fullscreen")

    @mcp.tool()
    async def view_waveform() -> dict:
        """Switch the selected track to waveform view."""
        return await bridge.dispatch("action://trackedit/track-view-waveform")

    @mcp.tool()
    async def view_spectrogram() -> dict:
        """Switch the selected track to spectrogram view."""
        return await bridge.dispatch("action://trackedit/track-view-spectrogram")

    @mcp.tool()
    async def view_multi() -> dict:
        """Switch the selected track to multi-view (waveform + spectrogram)."""
        return await bridge.dispatch("action://trackedit/track-view-multi")

    @mcp.tool()
    async def view_beats_measures_ruler() -> dict:
        """Toggle beats and measures ruler."""
        return await bridge.dispatch("beats-measures-ruler")

    @mcp.tool()
    async def view_minutes_seconds_ruler() -> dict:
        """Toggle minutes and seconds ruler."""
        return await bridge.dispatch("minutes-seconds-ruler")

    @mcp.tool()
    async def view_spectrogram_preferences() -> dict:
        """Open spectrogram display preferences."""
        return await bridge.dispatch("spectrogram-preferences")
