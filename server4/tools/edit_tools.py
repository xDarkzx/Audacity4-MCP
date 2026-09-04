from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def edit_undo() -> dict:
        """Undo the last action."""
        return await bridge.dispatch("action://undo")

    @mcp.tool()
    async def edit_redo() -> dict:
        """Redo the last undone action."""
        return await bridge.dispatch("action://redo")

    @mcp.tool()
    async def edit_cut() -> dict:
        """Cut the selected audio to clipboard."""
        return await bridge.dispatch("action://cut")

    @mcp.tool()
    async def edit_copy() -> dict:
        """Copy the selected audio to clipboard."""
        return await bridge.dispatch("action://copy")

    @mcp.tool()
    async def edit_paste() -> dict:
        """Paste audio from clipboard at the cursor position."""
        return await bridge.dispatch("action://paste")

    @mcp.tool()
    async def edit_delete() -> dict:
        """Delete the selected audio (does not copy to clipboard)."""
        return await bridge.dispatch("action://delete")

    @mcp.tool()
    async def edit_select_all() -> dict:
        """Select all audio in the project."""
        return await bridge.dispatch("select-all")

    @mcp.tool()
    async def edit_clear_selection() -> dict:
        """Clear the current selection."""
        return await bridge.dispatch("clear-selection")

    @mcp.tool()
    async def edit_trim() -> dict:
        """Trim audio outside the selection (keep only selected region)."""
        return await bridge.dispatch("trim-audio-outside-selection")

    @mcp.tool()
    async def edit_silence() -> dict:
        """Replace the selected audio region with silence."""
        return await bridge.dispatch("silence-audio-selection")

    @mcp.tool()
    async def edit_duplicate() -> dict:
        """Duplicate the selected audio into a new track."""
        return await bridge.dispatch("duplicate")

    @mcp.tool()
    async def edit_split() -> dict:
        """Split the clip at the selection boundaries."""
        return await bridge.dispatch("split")

    @mcp.tool()
    async def edit_split_into_new_track() -> dict:
        """Split the selected audio into a new track."""
        return await bridge.dispatch("split-into-new-track")

    @mcp.tool()
    async def edit_join() -> dict:
        """Join selected clips into one clip."""
        return await bridge.dispatch("join")

    @mcp.tool()
    async def edit_disjoin() -> dict:
        """Detach audio at silences (split into separate clips)."""
        return await bridge.dispatch("disjoin")

    @mcp.tool()
    async def edit_repeat_last_effect() -> dict:
        """Repeat the last applied effect with the same settings."""
        return await bridge.dispatch("repeat-last-effect")

    @mcp.tool()
    async def edit_zero_cross() -> dict:
        """Move selection edges to nearest zero crossings (prevents clicks)."""
        return await bridge.dispatch("zero-cross")
