import json
import sys

from mcp.server.fastmcp import FastMCP

from server4.bridge_client import BridgeClient
from server4.tool_registry import describe_profile, register_all_tools, resolve_profile

_active_profile = resolve_profile()
mcp = FastMCP("Audacity4MCP")
bridge = BridgeClient()

register_all_tools(mcp, _active_profile)


def main():
    args = sys.argv[1:]
    if "--profile-info" in args:
        profile_target = None
        for i, a in enumerate(args):
            if a in ("--profile", "-p") and i + 1 < len(args):
                profile_target = args[i + 1]
            elif a.startswith("--profile="):
                profile_target = a.split("=", 1)[1]

        info = describe_profile(profile_target)
        if "--json" in args:
            print(json.dumps(info.to_dict(), indent=2))
        else:
            print(f"Profile: {info.name}")
            print(f"Tools registered: {info.tool_count}")
            print(f"Tool schema chars: {info.tool_schema_chars}")
            print(f"Modules ({len(info.modules)}): {', '.join(info.modules)}")
            print(f"Tools ({len(info.tools)}): {', '.join(info.tools)}")
        return

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
