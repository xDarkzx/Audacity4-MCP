from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def label_list() -> dict:
        """List all labels on the project's (first) label track, with key, text, and time range."""
        return await bridge.call("list-labels", {})

    @mcp.tool()
    async def label_add_track() -> dict:
        """Create a new, empty label track."""
        return await bridge.call("add-label-track", {})

    @mcp.tool()
    async def label_add(text: str = "") -> dict:
        """Add a label at the current selection/playback position. Creates a label
        track automatically if none exists yet.

        Args:
            text: Optional text for the new label.
        """
        return await bridge.call("add-label", {"text": text} if text else {})

    @mcp.tool()
    async def label_remove(key: str) -> dict:
        """Remove a label by its key.

        Args:
            key: The label's key, in "trackId:itemId" format (from label_list/label_add).
        """
        return await bridge.call("remove-label", {"key": key})

    @mcp.tool()
    async def label_update_text(key: str, text: str) -> dict:
        """Change the text of an existing label.

        Args:
            key: The label's key, in "trackId:itemId" format.
            text: The new text for the label.
        """
        return await bridge.call("update-label-text", {"key": key, "text": text})
