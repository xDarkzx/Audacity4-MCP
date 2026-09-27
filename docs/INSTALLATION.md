# Installation

Audacity4MCP has two halves that both need to be running: this Python MCP server, and the companion `Audacity4-Dev` fork of Audacity 4 that actually hosts the automation surface. There is no packaged installer for either yet — both are built from source.

## 1. Build and run Audacity4-Dev

[**Audacity4-Dev-MCP**](https://github.com/xDarkzx/Audacity4-Dev-MCP/tree/feature/mcp-audio-cleanup-pipelines) is a fork of Audacity 4 with a `src/mcp/` module added that starts a TCP JSON-RPC server on `127.0.0.1:2212` as soon as Audacity launches. It's built the same way as upstream Audacity 4 (see Audacity's own [BUILDING.md](https://github.com/audacity/audacity/blob/master/BUILDING.md) for installing Qt/CMake/Ninja first) — this section covers the exact commands that work on the tested setup (Windows, MSVC, Ninja) and the fork-specific gotchas BUILDING.md doesn't mention.

**Prerequisite:** Visual Studio (2022 or newer) with the "Desktop development with C++" workload, plus **Qt 6.8 or newer** (tested on 6.10), CMake, and Ninja on PATH — see BUILDING.md.

### Qt components (the usual first failure)

Getting the Qt *version* right is not enough. The build asks for a specific set of modules (`find_package(Qt6 6.8 REQUIRED COMPONENTS ...)` in `muse/buildscripts/cmake/SetupQt6.cmake`), and several are separate tick-boxes in the Qt online installer that are **not selected by default**. A missing one stops `cmake --preset` with a `find_package` error naming the module, which is easy to misread as a broken checkout.

Make sure these are installed for your Qt version:

| Component | Qt installer name |
| --- | --- |
| `Core5Compat` | Qt 5 Compatibility Module |
| `ShaderTools` | Qt Shader Tools |
| `NetworkAuth` | Qt Network Authorization |
| `DBus` (Linux only) | Qt D-Bus |

These come with a normal desktop Qt install and rarely need attention: Core, Gui, Widgets, Network, Qml, Quick, QuickControls2, QuickWidgets, Xml, Svg, PrintSupport.

### Clone it, with submodules

Part of the bridge lives in the `muse` submodule (`muse/framework/rcontrol/mcp/`), so a plain `git clone` leaves a tree that cannot configure:

```bash
git clone --recurse-submodules https://github.com/xDarkzx/Audacity4-Dev-MCP.git
cd Audacity4-Dev-MCP
git checkout feature/mcp-audio-cleanup-pipelines
git submodule update --init --recursive
```

If you already cloned without `--recurse-submodules`, the last line alone is enough. If you cloned before the submodule URL was corrected, run `git submodule sync --recursive` first — an older `.gitmodules` pointed `muse` at upstream MuseScore, where the pinned commit does not exist, and the checkout fails with a confusing "reference is not a tree" error.

### Load the MSVC environment

On Windows the compiler environment must be loaded into the shell *before* any `cmake`/build command below — a plain terminal won't have it. Do this once per terminal session:

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

The first build takes roughly 20 minutes, give or take depending on your machine. After that it is incremental and much faster.

**Install/deploy** — this is the step that actually produces a runnable `Audacity4.exe`; the raw build directory (`build/audacity-debug/`) does not contain a directly launchable app:

```bash
cmake --install build/audacity-debug
```

This deploys to `src/app/bin/Audacity4.exe` (per `CMAKE_INSTALL_PREFIX` in the preset). **Launch that binary**, not anything under `build/`.

Open or create a project. The `mcp` module has no visible UI — you'll know it's up if this server can connect to it (step 3 below).

### What the install step is for: the DLLs Audacity needs to boot

`Audacity4.exe` is dynamically linked. On its own it is not a runnable program — it imports around two dozen DLLs directly and pulls in about seventy-six once their own dependencies are resolved, and it will not reach a window without all of them plus Qt's plugin directories laid out in the right shape beside it.

This is why the build directory is a dead end rather than just an inconvenient path. `build/audacity-debug/` ends up holding the Qt DLLs and a `platforms/` folder but **no `Audacity4.exe` at all** — the executable only ever appears at the install prefix. Running `cmake --build` and then hunting for something to double-click is the wrong shape of the problem; the install step is what assembles an app.

What `cmake --install` puts in `src/app/bin/`:

| Group | Files |
| --- | --- |
| The app | `Audacity4.exe` (~100 MB in a debug build), `qt.conf` |
| Qt 6 core runtime | `Qt6Cored`, `Qt6Guid`, `Qt6Widgetsd`, `Qt6Qmld`, `Qt6Quickd`, `Qt6Networkd`, `Qt6NetworkAuthd`, `Qt6Svgd`, `Qt6Concurrentd`, `Qt6Core5Compatd`, `Qt6OpenGLd`, `Qt6ShaderToolsd` |
| Qt Quick / Controls | `Qt6QuickTemplates2d`, `Qt6QuickControls2d` and its per-style pairs (Basic, Fusion, Material, Universal, Imagine, FluentWinUI3, Windows), `Qt6QuickLayoutsd`, `Qt6QuickShapesd`, `Qt6QuickEffectsd`, `Qt6QmlModelsd`, `Qt6QmlMetad`, `Qt6QmlWorkerScriptd`, `Qt6LabsPlatformd`, `Qt6LabsQmlModelsd`, `Qt6Quick3DUtilsd` |
| MSVC runtime (debug) | `msvcp140d`, `msvcp140d_atomic_wait`, `msvcp140d_codecvt_ids`, `msvcp140_1d`, `msvcp140_2d`, `vcruntime140d`, `vcruntime140_1d`, `vcruntime140_threadsd`, `vccorlib140d`, `concrt140d` (release-named copies ship alongside them) |
| Audio and codecs | `portaudio_x64`, `sndfile`, `FLAC`, `FLAC++`, `ogg`, `vorbis`, `vorbisenc`, `vorbisfile`, `opus`, `mpg123`, `syn123`, `wavpackdll` |
| Support libraries | `freetyped`, `harfbuzz`, `libpng16d`, `libexpatd`, `zlibd1`, `icuuc`, `d3dcompiler_47`, `opengl32sw`, `wxbase32ud_vc_x64_custom`, `wxbase32ud_net_vc_x64_custom` |
| Qt plugin folders | `platforms/qwindowsd.dll` (required — the app cannot start without it), `imageformats/`, `iconengines/`, `tls/`, `networkinformation/`, `generic/` |
| Qt/app data | `qml/`, `translations/`, `nyquist-plug-ins/`, `nyquist-runtime/` |

The plugin folders have to stay folders. Qt discovers `platforms/qwindowsd.dll` by directory, so flattening everything into one pile is the usual way a hand-copied build fails.

A full recursive scan of the installed tree (115 binaries, 149 distinct imports) resolves entirely inside `src/app/bin/` plus Windows' own system DLLs — with exactly one exception.

**`ucrtbased.dll` is the one the install step cannot give you.** A debug build links against the *debug* Universal C Runtime, which is not part of Windows and is not redistributable, so it is not in the deployed folder and will not be on a machine that only has the MSVC redistributable. It is installed into `C:\Windows\System32` by the Windows SDK's debug runtime component, and the SDK also keeps copies at:

```
C:\Program Files (x86)\Windows Kits\10\bin\<sdk-version>\x64\ucrt\ucrtbased.dll
```

If Audacity dies instantly with `ucrtbased.dll was not found`, install the Windows SDK (the "Debugging Tools for Windows" / Universal CRT debug runtime component), or copy that file next to `Audacity4.exe`. Building the release preset avoids the problem entirely — release links against `ucrtbase.dll`, which *is* part of Windows.

**Checking a deployment before blaming the app.** From the `bin` directory:

```powershell
foreach ($f in "Audacity4.exe", "Qt6Cored.dll", "Qt6Quickd.dll", "qt.conf", "platforms\qwindowsd.dll", "qml") {
  "{0,-28} {1}" -f $f, (Test-Path $f)
}
```

All six must be `True`. If `Audacity4.exe` is missing you skipped `cmake --install`; if only the Qt pieces are missing the install ran against the wrong directory.

| Symptom on launch | Cause |
| --- | --- |
| `Qt6Cored.dll was not found` (or any `Qt6*d.dll`) | Running the exe from somewhere other than `src/app/bin`, or the install step never ran |
| `ucrtbased.dll was not found` | Windows SDK debug runtime not installed — see above |
| `This application failed to start because no Qt platform plugin could be initialized` | `platforms/qwindowsd.dll` is missing, or the plugin folders were flattened |
| Window opens blank or unstyled | `qml/` or the QuickControls2 style DLLs did not deploy |
| `VCRUNTIME140D.dll was not found` | Debug CRT missing — install the Visual Studio C++ workload, or build the release preset |

**Closing it down:** always close Audacity4 cleanly from its own window (or ask it to close), never force-kill the process (`taskkill /F`, Task Manager "End Task", etc.). A force-kill corrupts session-recovery state and causes a recurring "convert project" popup on every subsequent launch until that state is cleared out.

**If a rebuild fails with a file-lock error (`LNK1168`)**: Audacity4.exe is still running and holding the binary open. Close it (cleanly, per above) before rebuilding.

### Keeping the fork up to date

The fork is a shallow clone of upstream Audacity, so it has no full history and no merge base with `audacity/audacity`. A plain `git pull` from upstream will not behave the way it does in a normal clone. To pick up upstream changes, fetch what you need explicitly:

```bash
git remote add upstream https://github.com/audacity/audacity.git   # once
git fetch --unshallow upstream                                     # first time only, this is a big fetch
git fetch upstream master
```

Then rebase or merge the MCP branch onto it as you would normally. If you only want to build what is known to work, skip this entirely — the branch is self-contained.

## 2. Install this server

Requires Python 3.10+. The only runtime dependency is the `mcp` SDK — the bridge to Audacity4-Dev is a plain `asyncio` TCP client, nothing else to install.

```bash
pip install audacity4-mcp
```

To work on the server itself, install it from source instead:

```bash
git clone https://github.com/xDarkzx/Audacity4-MCP.git
cd Audacity4-MCP
pip install -e ".[dev]"
```

### Linux and macOS

The server half is plain Python and `asyncio`, with no OS-specific code, so it runs the same everywhere — the untested part is building the fork, not this. Three things differ in practice.

**A system Python will refuse to install into.** Debian, Ubuntu and Fedora mark their Python as externally managed, so `pip install` fails with `error: externally-managed-environment`. Use a virtual environment:

```bash
python3 -m venv ~/.venvs/audacity4-mcp
~/.venvs/audacity4-mcp/bin/pip install audacity4-mcp
```

or install it as a standalone tool with `pipx install audacity4-mcp`.

**The executable may not be on your `PATH`.** A venv install puts it in that venv's `bin/`, and `pip install --user` or `pipx` put it in `~/.local/bin`, which many distributions do not add to `PATH` for non-login shells. Use the absolute path in your MCP client config (see step 5) rather than fighting it:

```bash
~/.venvs/audacity4-mcp/bin/audacity4-mcp --help   # confirm it runs
```

**Both halves must run as the same user, on the same machine.** The token file is created readable only by its owner, so a server running as a different user cannot read it. The host and port are not configurable — the client always connects to `127.0.0.1:2212`, and the bridge itself listens only on loopback (`QHostAddress::LocalHost`) — so Audacity and this server have to be on the same host. Running the server inside WSL or a container while Audacity runs on the Windows host will not work as-is.

### Driving Audacity on another machine

If you do need the server and Audacity on different hosts, tunnel rather than exposing the port. An SSH tunnel makes the remote bridge appear on your own loopback, which is exactly what the client expects, and it encrypts the connection — which plain TCP would not, token included:

```bash
ssh -L 2212:127.0.0.1:2212 user@host-running-audacity
```

Then, in the shell where the server runs, supply the token from that machine (its token file is not local, so the normal lookup cannot find it):

```bash
AUDACITY4_MCP_TOKEN=<contents of the token file on that host> audacity4-mcp
```

The same applies to WSL and containers: forward the port in rather than changing where the bridge listens. Nothing on either side needs modifying.

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
file. Set `AUDACITY4_MCP_TOKEN` to override the file, for the cases where the
lookup cannot find it — an unusual profile location, or a sandboxed client that
cannot read outside its own directory. It does not enable a bridge on another
machine: the host and port are fixed at `127.0.0.1:2212`.

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

To check the bridge is listening at all, before involving Python:

```bash
netstat -an | findstr 2212        # Windows
ss -tlnp | grep 2212              # Linux
lsof -nP -iTCP:2212 -sTCP:LISTEN  # macOS
```

A listening socket on `127.0.0.1:2212` means the `mcp` module started. Nothing there means you are running stock Audacity rather than the build you made, or it failed to start — check the Audacity window or console.

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

**If the client cannot start the server**, this is almost always `PATH`. `"command": "audacity4-mcp"` only resolves if that executable is on the `PATH` your MCP client inherits, which is not the case when it lives in a virtual environment — and the client usually reports little more than a failure to connect. Find the real path and use it verbatim:

```bash
where audacity4-mcp      # Windows
which audacity4-mcp      # macOS / Linux
```

```json
{
  "mcpServers": {
    "audacity4": {
      "command": "C:\\path\\to\\venv\\Scripts\\audacity4-mcp.exe"
    }
  }
}
```

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
