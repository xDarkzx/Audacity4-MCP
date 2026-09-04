from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def project_save() -> dict:
        """Save the current project. Refuses if the project has never been saved
        before (has no file path yet) or has no unsaved changes - check the
        returned message for why, if isError is true."""
        return await bridge.call("save-project", {})

    @mcp.tool()
    async def recent_commands() -> dict:
        """List recently executed MCP commands with their id, timestamp, success,
        and result message. Useful for checking what an earlier command actually
        did, or finding a command's id to look up with command_status."""
        return await bridge.call("recent-commands", {})

    @mcp.tool()
    async def command_status(command_id: str) -> dict:
        """Look up the recorded result of a previously executed command by its id.

        Args:
            command_id: The command id, as returned in a recent_commands entry.
        """
        return await bridge.call("command-status", {"id": command_id})
