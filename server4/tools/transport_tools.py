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
