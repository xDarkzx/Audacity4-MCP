from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def clip_cut() -> dict:
        """Cut the selected clip to clipboard."""
        return await bridge.dispatch("clip-cut")

    @mcp.tool()
    async def clip_copy() -> dict:
        """Copy the selected clip to clipboard."""
        return await bridge.dispatch("clip-copy")

    @mcp.tool()
    async def clip_delete() -> dict:
        """Delete the selected clip."""
        return await bridge.dispatch("clip-delete")

    @mcp.tool()
    async def clip_split_cut() -> dict:
        """Split-cut the selected clip (cut without closing gap)."""
        return await bridge.dispatch("clip-split-cut")

    @mcp.tool()
    async def clip_split_delete() -> dict:
        """Split-delete the selected clip (delete without closing gap)."""
        return await bridge.dispatch("clip-split-delete")

    @mcp.tool()
    async def clip_gain() -> dict:
        """Open the clip gain control."""
        return await bridge.dispatch("clip-gain")

    @mcp.tool()
    async def clip_pitch_speed() -> dict:
        """Open the clip pitch and speed controls."""
        return await bridge.dispatch("clip-pitch-speed")

    @mcp.tool()
    async def clip_render_pitch_speed() -> dict:
        """Render pitch/speed changes permanently into the clip."""
        return await bridge.dispatch("clip-render-pitch-speed")

    @mcp.tool()
    async def clip_stretch_to_match_tempo() -> dict:
        """Stretch the clip to match the project tempo."""
        return await bridge.dispatch("stretch-clip-to-match-tempo")

    @mcp.tool()
    async def clip_group() -> dict:
        """Group selected clips together."""
        return await bridge.dispatch("group-clips")

    @mcp.tool()
    async def clip_ungroup() -> dict:
        """Ungroup grouped clips."""
        return await bridge.dispatch("ungroup-clips")

    @mcp.tool()
    async def clip_duplicate() -> dict:
        """Duplicate selected clips."""
        return await bridge.dispatch("duplicate-clips")

    @mcp.tool()
    async def clip_split_at_silences() -> dict:
        """Split clips at silent sections."""
        return await bridge.dispatch("split-clips-at-silences")

    @mcp.tool()
    async def clip_split_into_new_tracks() -> dict:
        """Split selected clips into new individual tracks."""
        return await bridge.dispatch("split-clips-into-new-tracks")
