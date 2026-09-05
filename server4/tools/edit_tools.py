from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP):
    from server4.main import bridge

    # NOTE All commands below operate purely on the *current* selection state
    # (tracks selected via select_tracks/select_all, time range via
    # select_region/select_all) - none of them take explicit track/time
    # arguments. Set the selection first.

    @mcp.tool()
    async def edit_cut() -> dict:
        """Cut the selected audio to clipboard. Select tracks and a time range first."""
        return await bridge.call("edit-cut", {})

    @mcp.tool()
    async def edit_copy() -> dict:
        """Copy the selected audio to clipboard. Select tracks and a time range first."""
        return await bridge.call("edit-copy", {})

    @mcp.tool()
    async def edit_paste() -> dict:
        """Paste audio from clipboard at the start of the current selection.
        Select the destination position first with select_region (or cursor_set)."""
        return await bridge.call("edit-paste", {})

    @mcp.tool()
    async def edit_delete() -> dict:
        """Delete the selected audio, closing the gap (does not copy to clipboard).
        Select tracks and a time range first."""
        return await bridge.call("edit-delete", {})

    @mcp.tool()
    async def edit_split() -> dict:
        """Split the selected clip(s) at the selection boundaries (in place, no new
        track). Select tracks and a time range first."""
        return await bridge.call("edit-split", {})

    @mcp.tool()
    async def edit_trim() -> dict:
        """Trim audio outside the selection (delete everything except the selected
        region). Select tracks and a time range first."""
        return await bridge.call("edit-trim", {})

    @mcp.tool()
    async def edit_silence() -> dict:
        """Replace the selected audio with silence. Select tracks and a time range first."""
        return await bridge.call("edit-silence", {})

    @mcp.tool()
    async def edit_duplicate() -> dict:
        """Duplicate the selected audio into a new track. Select tracks and a time
        range first."""
        return await bridge.call("edit-duplicate", {})

    @mcp.tool()
    async def edit_split_new() -> dict:
        """Split the selected audio into a new track at the selection boundaries,
        leaving the original track unchanged. Select tracks and a time range first."""
        return await bridge.call("edit-split-new", {})

    @mcp.tool()
    async def edit_split_cut() -> dict:
        """Cut the selected audio to clipboard WITHOUT closing the gap - leaves silence
        where the audio was. Select tracks and a time range first."""
        return await bridge.call("edit-split-cut", {})

    @mcp.tool()
    async def edit_split_delete() -> dict:
        """Delete the selected audio WITHOUT closing the gap - leaves silence where the
        audio was. Select tracks and a time range first."""
        return await bridge.call("edit-split-delete", {})

    @mcp.tool()
    async def edit_disjoin() -> dict:
        """Split the selected audio into separate clips at detected silences. Select
        tracks and a time range first."""
        return await bridge.call("edit-disjoin", {})

    @mcp.tool()
    async def edit_join() -> dict:
        """Join the selected clips into one clip. Select tracks and a time range first."""
        return await bridge.call("edit-join", {})

    @mcp.tool()
    async def edit_undo() -> dict:
        """Undo the last edit. Fails cleanly if there's nothing to undo."""
        return await bridge.call("edit-undo", {})

    @mcp.tool()
    async def edit_redo() -> dict:
        """Redo the last undone edit. Fails cleanly if there's nothing to redo."""
        return await bridge.call("edit-redo", {})
