from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def track_add_mono() -> dict:
        """Add a new mono audio track to the project."""
        return await bridge.dispatch("new-mono-track")

    @mcp.tool()
    async def track_add_stereo() -> dict:
        """Add a new stereo audio track to the project."""
        return await bridge.dispatch("new-stereo-track")

    @mcp.tool()
    async def track_add_label() -> dict:
        """Add a new label track to the project."""
        return await bridge.dispatch("new-label-track")

    @mcp.tool()
    async def track_delete() -> dict:
        """Delete the currently selected track(s)."""
        return await bridge.dispatch("track-delete")

    @mcp.tool()
    async def track_duplicate() -> dict:
        """Duplicate the currently selected track."""
        return await bridge.dispatch("track-duplicate")

    @mcp.tool()
    async def track_make_stereo() -> dict:
        """Combine two mono tracks into a stereo track."""
        return await bridge.dispatch("track-make-stereo")

    @mcp.tool()
    async def track_split_stereo() -> dict:
        """Split a stereo track into two mono tracks (left/right)."""
        return await bridge.dispatch("track-split-stereo-to-lr")

    @mcp.tool()
    async def track_split_stereo_center() -> dict:
        """Split a stereo track into two mono tracks panned center."""
        return await bridge.dispatch("track-split-stereo-to-center")

    @mcp.tool()
    async def track_swap_channels() -> dict:
        """Swap left and right channels of a stereo track."""
        return await bridge.dispatch("track-swap-channels")

    @mcp.tool()
    async def track_resample() -> dict:
        """Open the resample dialog for the selected track."""
        return await bridge.dispatch("track-resample")

    @mcp.tool()
    async def track_move_up() -> dict:
        """Move the selected track up in the track list."""
        return await bridge.dispatch("track-move-up")

    @mcp.tool()
    async def track_move_down() -> dict:
        """Move the selected track down in the track list."""
        return await bridge.dispatch("track-move-down")

    @mcp.tool()
    async def track_move_to_top() -> dict:
        """Move the selected track to the top of the track list."""
        return await bridge.dispatch("track-move-top")

    @mcp.tool()
    async def track_move_to_bottom() -> dict:
        """Move the selected track to the bottom of the track list."""
        return await bridge.dispatch("track-move-bottom")

    @mcp.tool()
    async def track_pan() -> dict:
        """Open the pan control for the selected track."""
        return await bridge.dispatch("pan")

    @mcp.tool()
    async def track_change_rate() -> dict:
        """Open the sample rate change dialog for the selected track."""
        return await bridge.dispatch("track-change-rate-custom")
