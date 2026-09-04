from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def ping() -> dict:
        """Test connection to Audacity 4. Returns 'pong' if connected."""
        return await bridge.ping()

    @mcp.tool()
    async def bridge_info() -> dict:
        """Get information about the Audacity 4 MCP bridge (version, name)."""
        return await bridge.info()
