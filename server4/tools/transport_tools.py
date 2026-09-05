from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def transport_play_stop() -> dict:
        """Toggle playback of the current project (play if stopped, stop if playing)."""
        return await bridge.call("play-stop", {})

    @mcp.tool()
    async def transport_pause() -> dict:
        """Pause playback."""
        return await bridge.call("pause", {})

    @mcp.tool()
    async def transport_stop() -> dict:
        """Stop playback."""
        return await bridge.call("stop", {})

    @mcp.tool()
    async def transport_rewind_start() -> dict:
        """Move the playback cursor to the start of the project."""
        return await bridge.call("rewind-start", {})

    @mcp.tool()
    async def transport_record() -> dict:
        """Start recording on a new track. Requires a working audio input device -
        if none is configured, this dispatches without error but recording won't
        actually engage. Use transport_stop to stop recording."""
        return await bridge.call("transport-record", {})

    @mcp.tool()
    async def transport_get_play_position() -> dict:
        """Get the current playhead position, whether playback is active, and
        the current time selection (start/end)."""
        return await bridge.call("transport-get-play-position", {})

    @mcp.tool()
    async def transport_play_region(start: float, end: float) -> dict:
        """Select a time region and play it, starting from the region's beginning.

        Args:
            start: Start time in seconds
            end: End time in seconds (>= start)
        """
        if start < 0:
            raise ValueError("start must be >= 0")
        if end < start:
            raise ValueError("end must be >= start")

        await bridge.call("select-time", {"start": start, "end": end})

        # NOTE: play-stop is a TOGGLE that resumes from wherever playback last
        # was - confirmed LIVE that select-time + play-stop starts from t=0,
        # ignoring the selection entirely (playPosition tracked real elapsed
        # time from 0, not from the region start). play-selection is a
        # separate, dedicated action (PlaybackController::playSelectionAction)
        # that explicitly plays the current selection from its start - use
        # that instead, not play-stop.
        return await bridge.call("play-selection", {})
