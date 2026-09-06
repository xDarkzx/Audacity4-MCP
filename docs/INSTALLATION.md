# Installation

Audacity4MCP has two halves that both need to be running: this Python MCP server, and the companion `Audacity4-Dev` fork of Audacity 4 that actually hosts the automation surface. There is no packaged installer for either yet — both are built from source.

## 1. Build and run Audacity4-Dev

`Audacity4-Dev` is a fork of Audacity 4 with a `src/mcp/` module added that starts a TCP JSON-RPC server on `127.0.0.1:2212` as soon as Audacity launches. It's built the same way as upstream Audacity 4 (see its own [BUILDING.md](../../Audacity4-Dev/BUILDING.md) for installing Qt/CMake/Ninja/etc. first) — this section covers only the exact commands that actually work on this project's tested setup (Windows, MSVC, Ninja) and the fork-specific gotchas that BUILDING.md doesn't mention.

**Prerequisite:** Visual Studio (2022 or newer) with the "Desktop development with C++" workload, plus Qt 6.10, CMake, and Ninja on PATH — see BUILDING.md. On Windows, the MSVC compiler environment must be loaded into the shell *before* running any `cmake`/build command below — a plain terminal won't have it. Do this once per terminal session:

```bat
"C:\Program Files\Microsoft Visual Studio\<year>\<edition>\VC\Auxiliary\Build\vcvars64.bat"
```

(Path varies by VS version/edition — find yours under `...\Microsoft Visual Studio\<version>\<edition>\VC\Auxiliary\Build\`.)

**Configure** (first time only, and again any time `CMakeLists.txt` under `src/mcp/` — or anywhere else — changes; an incremental build alone will not pick up CMakeLists changes):

```bash
cmake --preset audacity-debug
```

**Build** (every time, from the same vcvars-loaded shell):

```bash
cmake --build build/audacity-debug
```

**Install/deploy** — this is the step that actually produces a runnable `Audacity4.exe`; the raw build directory (`build/audacity-debug/`) does not contain a directly launchable app:

```bash
cmake --install build/audacity-debug
```

This deploys to `src/app/bin/Audacity4.exe` (per `CMAKE_INSTALL_PREFIX` in the preset). **Launch that binary**, not anything under `build/`.

Open or create a project. The `mcp` module has no visible UI — you'll know it's up if this server can connect to it (step 3 below).

**Closing it down:** always close Audacity4 cleanly from its own window (or ask it to close), never force-kill the process (`taskkill /F`, Task Manager "End Task", etc.). A force-kill corrupts session-recovery state and causes a recurring "convert project" popup on every subsequent launch until that state is cleared out.

**If a rebuild fails with a file-lock error (`LNK1168`)**: Audacity4.exe is still running and holding the binary open. Close it (cleanly, per above) before rebuilding.

## 2. Install this server

```bash
git clone https://github.com/xDarkzx/Audacity4-MCP.git
cd Audacity4-MCP
pip install -e .
```

Requires Python 3.10+. The only runtime dependency is the `mcp` SDK — the bridge to Audacity4-Dev is a plain `asyncio` TCP client, nothing else to install.

## 3. Authentication (nothing to configure)

The bridge requires a token on every request. Audacity generates one on first
run and writes it to its own profile directory; this server reads it from the
same place, so there is normally nothing to set up:

| Platform | Token file |
| --- | --- |
| Windows | `%LOCALAPPDATA%\Audacity\Audacity4Development\mcp_token` |
| macOS | `~/Library/Application Support/Audacity/Audacity4Development/mcp_token` |
| Linux | `~/.local/share/Audacity/Audacity4Development/mcp_token` |

The file is readable only by your own account, which is what keeps other users
and web pages out — a page you visit can reach the port, but cannot read a local
file. Set `AUDACITY4_MCP_TOKEN` to override the file, for setups where Audacity's
profile directory isn't reachable (containers, a bridge on another machine).

If Audacity has never been started, the token won't exist yet and this server
will say so, listing every path it looked in.

## 4. Verify the connection

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

## 5. Point your MCP client at it

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

**Optional — trim the tool list for a specific workflow.** By default every tool loads. To load only what one workflow needs (smaller schema footprint per session), add an `env` block picking a [profile](TOOLS.md#tool-profiles):

```json
{
  "mcpServers": {
    "audacity4": {
      "command": "audacity4-mcp",
      "env": { "AUDACITY4_MCP_PROFILE": "cleanup" }
    }
  }
}
```

## Troubleshooting

- **`unauthorized` / token errors**: the token this server read no longer matches the one Audacity is using. Restart Audacity, or unset `AUDACITY4_MCP_TOKEN` if it is pointing at a stale value. If the message says the token could not be read at all, start Audacity once so it can create the file.
- **`Connection refused`, or connections being dropped while it "should" work**: the bridge accepts one client at a time, so a second tool talking to port 2212 will be rejected while this server is connected.
- **Connection refused**: Audacity4-Dev isn't running, or its `mcp` module failed to start — check the Audacity window/console for errors.
- **A command times out with a "dialog needs a human to click through it" message**: exactly what it says — some effects show a native modal dialog on precondition failure (e.g. wrong track/clip selection) that blocks Audacity's whole main thread. Check the Audacity window, dismiss the dialog, retry.
- **Audacity crashes or won't reopen cleanly after a bad session**: never force-kill it (`taskkill /F` or similar) — this corrupts session-recovery state and causes a recurring "convert project" popup on next launch. Close it from the window (or ask it to close) instead.
