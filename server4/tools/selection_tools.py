from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def selection_all() -> dict:
        """Select all audio in the project."""
        return await bridge.dispatch("select-all")

    @mcp.tool()
    async def selection_none() -> dict:
        """Clear the current selection."""
        return await bridge.dispatch("clear-selection")

    @mcp.tool()
    async def selection_all_tracks() -> dict:
        """Select all tracks in the project."""
        return await bridge.dispatch("select-all-tracks")

    @mcp.tool()
    async def selection_cursor_to_track_end() -> dict:
        """Extend selection from cursor to end of track."""
        return await bridge.dispatch("select-cursor-to-track-end")

    @mcp.tool()
    async def selection_track_start_to_cursor() -> dict:
        """Extend selection from start of track to cursor."""
        return await bridge.dispatch("select-track-start-to-cursor")

    @mcp.tool()
    async def selection_track_start_to_end() -> dict:
        """Select from start to end of track."""
        return await bridge.dispatch("select-track-start-to-end")

    @mcp.tool()
    async def selection_left_of_playback() -> dict:
        """Select audio to the left of playback position."""
        return await bridge.dispatch("select-left-of-playback-position")

    @mcp.tool()
    async def selection_right_of_playback() -> dict:
        """Select audio to the right of playback position."""
        return await bridge.dispatch("select-right-of-playback-position")

    @mcp.tool()
    async def selection_set_loop_region() -> dict:
        """Set loop region to current selection."""
        return await bridge.dispatch("set-loop-region-to-selection")

    @mcp.tool()
    async def selection_set_from_loop() -> dict:
        """Set selection from current loop region."""
        return await bridge.dispatch("set-selection-to-loop")
