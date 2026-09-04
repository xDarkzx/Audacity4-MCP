from mcp.server.fastmcp import FastMCP

from server4.bridge_client import BridgeClient
from server4.tool_registry import register_all_tools

mcp = FastMCP("Audacity4MCP")
bridge = BridgeClient()

register_all_tools(mcp)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
