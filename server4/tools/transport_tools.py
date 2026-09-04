from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def transport_play() -> dict:
        """Start playback from the current cursor position."""
        return await bridge.dispatch("action://playback/play")

    @mcp.tool()
    async def transport_stop() -> dict:
        """Stop playback or recording."""
        return await bridge.dispatch("action://playback/stop")

    @mcp.tool()
    async def transport_pause() -> dict:
        """Toggle pause during playback."""
        return await bridge.dispatch("action://playback/pause")

    @mcp.tool()
    async def transport_record() -> dict:
        """Start recording."""
        return await bridge.dispatch("action://record/start")

    @mcp.tool()
    async def transport_record_pause() -> dict:
        """Pause recording."""
        return await bridge.dispatch("action://record/pause")

    @mcp.tool()
    async def transport_record_stop() -> dict:
        """Stop recording."""
        return await bridge.dispatch("action://record/stop")

    @mcp.tool()
    async def transport_loop_toggle() -> dict:
        """Toggle loop playback on/off."""
        return await bridge.dispatch("toggle-loop-region")

    @mcp.tool()
    async def transport_rewind_to_start() -> dict:
        """Move cursor to the beginning of the project."""
        return await bridge.dispatch("action://playback/rewind-start")

    @mcp.tool()
    async def transport_forward_to_end() -> dict:
        """Move cursor to the end of the project."""
        return await bridge.dispatch("action://playback/rewind-end")

    @mcp.tool()
    async def transport_toggle_pinned_playhead() -> dict:
        """Toggle pinned play head mode."""
        return await bridge.dispatch("toggle-pinned-play-head")

    @mcp.tool()
    async def transport_toggle_input_monitoring() -> dict:
        """Toggle input monitoring for recording."""
        return await bridge.dispatch("action://record/toggle-input-monitoring")

    @mcp.tool()
    async def transport_toggle_mic_metering() -> dict:
        """Toggle microphone metering display."""
        return await bridge.dispatch("action://record/toggle-mic-metering")
