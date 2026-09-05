# Installation

Audacity4MCP has two halves that both need to be running: this Python MCP server, and the companion `Audacity4-Dev` fork of Audacity 4 that actually hosts the automation surface. There is no packaged installer for either yet — both are built from source.

## 1. Build and run Audacity4-Dev

`Audacity4-Dev` is a fork of Audacity 4 with a `src/mcp/` module added that starts a TCP JSON-RPC server on `127.0.0.1:2212` as soon as Audacity launches. Follow its own [BUILDING.md](../../Audacity4-Dev/BUILDING.md) for the base Audacity build (currently tested on Windows with MSVC / Visual Studio + Ninja only).

Once built, launch the resulting `Audacity4.exe` (deployed under `src/app/bin/` in the build tree, not the raw CMake build directory) and open or create a project. The `mcp` module has no visible UI — you'll know it's up if this server can connect to it (step 3 below).

If you change anything under `src/mcp/`, a `cmake` reconfigure is required before rebuilding (CMakeLists.txt changes aren't picked up by an incremental build alone).

## 2. Install this server

```bash
git clone https://github.com/xDarkzx/Audacity4-MCP.git
cd Audacity4-MCP
pip install -e .
```

Requires Python 3.10+. The only runtime dependency is the `mcp` SDK — the bridge to Audacity4-Dev is a plain `asyncio` TCP client, nothing else to install.

## 3. Verify the connection

With Audacity4-Dev running and a project open:

```bash
python -c "
import asyncio
from server4.bridge_client import BridgeClient

async def main():
    bridge = BridgeClient()
    print(await bridge.call('project-get-info', {}))
    await bridge.close()

asyncio.run(main())
"
```

If this prints real project info (path, tracks, etc.) instead of a connection error, the bridge is working.

## 4. Point your MCP client at it

For Claude Desktop or Claude Code, add to your MCP config (`claude_desktop_config.json` or equivalent):

```json
{
  "mcpServers": {
    "audacity4": {
      "command": "audacity4-mcp"
    }
  }
}
```

Restart your client. It should now see the full tool list from [TOOLS.md](TOOLS.md).

## Troubleshooting

- **Connection refused**: Audacity4-Dev isn't running, or its `mcp` module failed to start — check the Audacity window/console for errors.
- **A command times out with a "dialog needs a human to click through it" message**: exactly what it says — some effects show a native modal dialog on precondition failure (e.g. wrong track/clip selection) that blocks Audacity's whole main thread. Check the Audacity window, dismiss the dialog, retry.
- **Audacity crashes or won't reopen cleanly after a bad session**: never force-kill it (`taskkill /F` or similar) — this corrupts session-recovery state and causes a recurring "convert project" popup on next launch. Close it from the window (or ask it to close) instead.
