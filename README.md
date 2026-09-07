<h1 align="center">Audacity4MCP</h1>

<p align="center">
  <strong>AI-powered audio editing in Audacity 4 through the Model Context Protocol</strong>
</p>

<p align="center">
  <a href="https://github.com/xDarkzx/Audacity4-MCP/actions/workflows/ci.yml"><img src="https://github.com/xDarkzx/Audacity4-MCP/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-green.svg" alt="License" /></a>
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-compatible-purple.svg" alt="MCP Compatible" /></a>
  <a href="https://github.com/xDarkzx/Audacity4-Dev-MCP"><img src="https://img.shields.io/badge/fork-Audacity4--Dev--MCP-1f6feb" alt="Companion fork" /></a>
  <img src="https://img.shields.io/badge/tools-159-blueviolet" alt="159 tools" />
  <img src="https://img.shields.io/badge/status-early%20alpha-orange.svg" alt="Early alpha" />
</p>

<p align="center">
  <a href="#what-it-does">What It Does</a> &bull;
  <a href="#status">Status</a> &bull;
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="#building-the-companion-fork">Building the Fork</a> &bull;
  <a href="#features">Features</a> &bull;
  <a href="#pipelines">Pipelines</a> &bull;
  <a href="#architecture">Architecture</a> &bull;
  <a href="#known-gaps">Known Gaps</a> &bull;
  <a href="#troubleshooting">Troubleshooting</a>
</p>

---

Audacity 4.0 shipped with **no scripting surface at all**. `mod-script-pipe` is gone and nothing replaced it, so the automation that Audacity 3 users relied on simply does not exist.

Audacity4MCP puts one back. It connects any MCP-compatible AI assistant to Audacity 4 — editing, effects, VST3 plugins, labels, transcription and one-call mastering pipelines — over a local TCP bridge compiled into a companion fork of Audacity itself.

**Everything runs locally.** No cloud, no API keys for audio processing, no audio leaving your machine.

## What It Does

You talk to your AI assistant; it drives Audacity.

> **"Clean up this podcast recording and get it ready to publish."**
> Analyses the audio, picks the right pipeline, removes noise, evens out the levels, and lands it at broadcast loudness.

> **"Put a low cut at 80 Hz, a 3 dB dip at 400, and a gentle air shelf at 10k."**
> Sets real parameters on a real VST3 EQ — FabFilter, Valhalla, whatever you have installed — while its own window is open, and you watch the curve move.

> **"Transcribe this and label each sentence."**
> Local Whisper transcription, then every segment written back as a label in one call.

> **"Split this interview at the silences and export each answer as its own file."**
> Silence detection, region labels, per-segment export.

The point is not that these are macros. The assistant can read the project back — track layout, clip boundaries, plugin parameters, measured loudness — and decide what to do next based on what it finds.

## Status

**Early alpha, under active daily development. Expect gaps, and expect things to change.**

This is the sibling of [AudacityMCP](https://github.com/xDarkzx/Audacity-MCP) for Audacity 3.x, which is mature and used in production. Audacity 4 is a full rewrite, so nothing ported directly — every command here was built against v4's actual internals and tested live against a running instance.

What that means in practice:

- **Every tool listed is implemented and registered**, not aspirational. The count is taken from the code.
- Each was **verified against a real running Audacity**, not just unit-tested against mocks. This has repeatedly caught bugs that mocks cannot — crashes, wrong parameter scales, effects landing at the wrong position.
- Some things genuinely do not work yet. They are in [Known Gaps](#known-gaps) rather than quietly missing.
- **There is no packaged installer.** You build the companion fork yourself. Windows/MSVC is the only toolchain tested end to end so far.

### Bugs found in Audacity itself

Driving Audacity headlessly surfaces bugs that ordinary use does not. Where they are not MCP-specific, they go upstream rather than staying patched in a fork:

- **VST3 plugin meters and analysers never animated.** FabFilter Pro-L2, Pro-Q 3, TBProAudio dpMeter5 and mvMeter2 all showed a single frozen frame, because the host silently dropped every plugin message arriving from a non-UI thread. Measured on a playing track: 34 delivered, 4305 dropped — 6585 delivered and 4 dropped after the fix. Submitted as [audacity/audacity#11992](https://github.com/audacity/audacity/pull/11992) against issue [#8881](https://github.com/audacity/audacity/issues/8881). It affects Audacity 3 too; that code had not changed functionally since July 2022.

## Quick Start

Both halves have to be running: the modified Audacity that hosts the bridge, and this Python server that talks to it.

**1. Build the companion fork** — [see below](#building-the-companion-fork). This is the long part; there is no prebuilt binary yet.

**2. Install this server:**

```bash
git clone https://github.com/xDarkzx/Audacity4-MCP.git
cd Audacity4-MCP
pip install -e .
```

**3. Point your MCP client at it.** For Claude Desktop / Claude Code:

```json
{
  "mcpServers": {
    "audacity4": {
      "command": "audacity4-mcp"
    }
  }
}
```

**4. Launch the Audacity you built**, open or create a project, and start talking to it.

Nothing else to configure — the auth token is generated by Audacity on first run and read from its profile directory automatically.

Full setup, including how to verify the connection: **[docs/INSTALLATION.md](docs/INSTALLATION.md)**.

## Building the Companion Fork

Audacity 4 has no scripting surface, so the bridge is compiled into a fork of it: [**Audacity4-Dev-MCP**](https://github.com/xDarkzx/Audacity4-Dev-MCP). Build it once, then run it instead of stock Audacity.

Windows/MSVC is the only toolchain tested. macOS and Linux should work — the code is portable and its POSIX paths are exercised in tests — but they have not been built end to end.

**Prerequisites:** Visual Studio 2022+ with "Desktop development with C++", Qt 6.10, CMake and Ninja on `PATH`. Audacity's own [BUILDING.md](https://github.com/audacity/audacity/blob/master/BUILDING.md) covers installing those.

**Clone it — with submodules.** Part of the bridge lives in the `muse` submodule, so a plain `git clone` produces a tree that cannot configure:

```bash
git clone --recurse-submodules https://github.com/xDarkzx/Audacity4-Dev-MCP.git
cd Audacity4-Dev-MCP
git checkout feature/mcp-audio-cleanup-pipelines
git submodule update --init --recursive
```

Already cloned without `--recurse-submodules`? The last line alone is enough. Cloned before the submodule URL was corrected? Run `git submodule sync --recursive` first.

**Load the MSVC environment** — once per terminal. `cmake` will not find the compiler without it:

```bat
"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
```

(Adjust year/edition to match your install.)

**Configure, build and install:**

```bash
cmake --preset audacity-debug
cmake --build build/audacity-debug --target install
```

The `install` target is the one that matters — the build directory alone does not contain a launchable app. Re-run `cmake --preset` whenever a `CMakeLists.txt` changes; an incremental build will not pick that up.

**Run it:**

```
src/app/bin/Audacity4.exe
```

That binary — not anything under `build/`. The `mcp` module has no visible UI; it starts listening on `127.0.0.1:2212` as soon as Audacity launches.

**Two things worth knowing:**

- **Close Audacity from its own window, never with Task Manager or `taskkill /F`.** A force-kill corrupts session-recovery state and produces a recurring "convert project" prompt on every later launch.
- **`LNK1168` on rebuild** means Audacity is still running and holding the binary open. Close it first.

## Features

**159 tools across 12 categories.** Full reference: **[docs/TOOLS.md](docs/TOOLS.md)**.

| Category | Tools | What it covers |
|---|---:|---|
| **Effects** | 29 | Built-in effects, batched application, presets, parameter discovery |
| **Edit** | 27 | Cut, copy, paste, trim, split, join, silence, undo/redo, clip pitch & speed |
| **Labels** | 21 | Add, edit, batch-add, region cut/silence/export, chapters, import/export |
| **Project** | 14 | Open, save, import, export, metadata |
| **Selection** | 12 | Time ranges, tracks, clips, zero-crossings, cursor placement |
| **Realtime / VST3** | 11 | Non-destructive chains, live parameter control, effect discovery |
| **Track** | 11 | Add, remove, duplicate, mute, resample, colour, properties |
| **Cleanup pipelines** | 9 | One-call mastering and repair workflows — [see below](#pipelines) |
| **Transport** | 8 | Play, stop, record, pause, position |
| **Transcription** | 7 | Local Whisper, to labels, to SRT/VTT/TXT |
| **Generate** | 6 | Tone, noise, silence, chirp, DTMF, rhythm track |
| **Analysis** | 4 | Loudness, noise floor, clipping, content-aware recommendations |

### Real VST3 control

This is the part most audio automation cannot do. Plugins are addressed as themselves, not as opaque presets:

- **Discover** every installed VST3 and its real parameters, ranges and units
- **Set parameters by value** — with the plugin's own editor open, updating live
- **Batch a whole chain** in a single call, so a chain never audibly passes through a half-configured state
- **Non-destructive** realtime chains, adjustable and removable afterwards

Two long-standing Audacity bugs had to be fixed in the fork before this worked reliably: writes made while a plugin's editor was open were silently discarded, and parameter metadata misreported continuous controls as dropdowns. Both are fixed and verified against FabFilter Pro-Q 3 and ValhallaVintageVerb — see [Known Gaps](#known-gaps).

## Pipelines

One call, many steps, measured rather than guessed. Each analyses the audio first and adapts.

| Pipeline | For |
|---|---|
| `auto_analyze_audio` | Measures the audio and recommends which pipeline to use. **Start here.** |
| `auto_cleanup_audio` | Safe cleanup — removes noise and artifacts *without* changing loudness |
| `auto_cleanup_podcast` | Podcast / voiceover, ending at broadcast loudness |
| `auto_audiobook_mastering` | Audiobook, targeting ACX/Audible compliance |
| `auto_cleanup_interview` | Dialogue and interviews, light touch |
| `auto_cleanup_vocal` | Singing and studio vocals |
| `auto_cleanup_live` | Live, field and noisy recordings — aggressive |
| `auto_master_music` | Music mastering with per-genre loudness targets |
| `auto_lofi_effect` | Creative vintage/lo-fi colouring |

The long-running ones return a `job_id` immediately and report progress through `check_pipeline_status`, so a ten-minute master does not block the conversation.

`auto_analyze_audio` takes a `content_type` (`speech`, `music` or `auto`), because the same measurements mean different things for each — in continuous music the quietest passage *is* the music, so speech-tuned noise-floor advice would damage it.

## Tool Profiles

159 tool schemas are sent to the model on every turn (~16k tokens). If you only need one workflow, load only that:

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

| Profile | Tools | Tokens/turn |
|---|---:|---:|
| `full` (default) | 159 | ~16,400 |
| `mastering` | 100 | ~10,900 |
| `cleanup` | 98 | ~10,800 |
| `editing` | 93 | ~6,400 |
| `transcription` | 61 | ~5,200 |
| `minimal` | 33 | ~2,300 |

Finer control via `AUDACITY4_MCP_INCLUDE_MODULES` / `EXCLUDE_MODULES` / `INCLUDE_TOOLS` / `EXCLUDE_TOOLS`. Check a profile without starting a session:

```bash
audacity4-mcp --profile-info --profile cleanup
```

## Architecture

```
AI assistant (Claude, etc.)
      │  MCP (stdio)
      ▼
Audacity4MCP  (this repo — Python, FastMCP)
      │  TCP JSON-RPC, 127.0.0.1:2212, token-authenticated
      ▼
Audacity4-Dev-MCP  (C++ fork — src/mcp/ module)
      │  dispatcher / interface calls
      ▼
Audacity 4 engine (tracks, effects, VST3 hosting, ...)
```

The bridge is compiled into the fork: `src/mcp/internal/audacitycommandscontroller.cpp` registers each command against Audacity 4's real internal interfaces (`ITrackeditProject`, `ISelectionController`, `IEffectsProvider`, `IRealtimeEffectService`, `IEffectParametersProvider`). On this side, `bridge_client.py` is a plain `asyncio` TCP client.

### Security

- **Every request is authenticated.** Audacity generates a 256-bit token from the OS cryptographic source on first run and writes it to its own profile directory as an owner-only file. This client reads it from the same place, so there is nothing to configure. `AUDACITY4_MCP_TOKEN` overrides it for containers or remote setups.
- **Fails closed.** With no token established, every request is refused rather than served unauthenticated. Comparison is constant-time.
- **HTTP requests are rejected.** A web page can `fetch()` a localhost port with `Content-Type: text/plain` and no CORS preflight, and the request body is just another protocol line. That was verified to execute commands, then fixed.
- **Paths are validated in the C++ handlers**, not only in this client — anything that can authenticate can call the bridge directly, so a check only the Python layer applies is not a check. Relative paths, null bytes and system directories are refused, with `..` and symlinks resolved first.

## Known Gaps

- **VST3 realtime parameters — fixed.** Writing a parameter while the plugin's own GUI was open reported success and then silently reverted, for continuous and discrete parameters alike. The parameter cache belongs to the plugin wrapper rather than to any one settings object, and the read-back and notification that follow every write drained it into a different one before it could be committed. Writes now stick with the editor open — verified on FabFilter Pro-Q 3 (15 parameters in one call, including the per-band Shape dropdowns this project once recorded as impossible to set) and ValhallaVintageVerb.
- **VST3 parameter metadata — fixed.** Pro-Q 3's per-band Frequency reported `"units": "Band 2"` and `"type": "Dropdown"` despite being continuous. A VST3 *unit* is a grouping of parameters, not a unit of measurement, and the type classifier trusted the `kIsList` flag without checking anything was listable. 124 of Pro-Q 3's 492 parameters were dropdowns with no entries; that is now 0, and `stepCount` is reported.
- **VST3 factory presets are usually empty.** `list_effect_presets` genuinely returns nothing for plugins (FabFilter, Valhalla) that keep presets in their own in-plugin browser rather than the standard VST3 host-preset API. This matches their behaviour in other DAWs — not an Audacity bug.
- **Some v3 tools have no v4 engine support yet** and are deliberately not implemented rather than shipped broken: `track_mix_and_render`, `track_stereo_to_mono`, `track_align_end_to_end`, `project_import_midi`.
- **Some v3 effects do not exist in v4 builds.** Echo, Phaser, Wahwah, Distortion, Repeat, ChangeTempo, ChangeSpeed, Equalization and AutoDuck have source in the tree but never link into the build — confirmed against the runtime plugin registry. Wrapping an effect that isn't there is worse than not having it.

Full history of what has been found and fixed: **[CHANGELOG.md](CHANGELOG.md)**.

## Troubleshooting

**"Could not read Audacity's MCP token"** — Audacity has not been started yet, or was installed somewhere unexpected. It writes the token on first run. The error lists every path checked; set `AUDACITY4_MCP_TOKEN` to point at it directly if needed.

**"Audacity rejected the connection as unauthorized"** — the token no longer matches, usually after a profile reset. The client re-reads and retries automatically; if it persists, restart Audacity, or unset `AUDACITY4_MCP_TOKEN` if it points at a stale value.

**"Could not reach Audacity"** — the bridge only listens while Audacity is running. Check it is open, and that nothing else holds port 2212.

**A command hangs, then reports a dialog** — Audacity is showing a modal dialog that blocks its main thread, usually an effect refusing to run because its preconditions were not met (wrong track or clip selected). No client can dismiss it; check the Audacity window.

**`LNK1168` when rebuilding the fork** — Audacity is still running and holding the binary. Close it from its own window.

**A "convert project" prompt on every launch** — session-recovery state was corrupted by a force-kill. Always close Audacity from its own window.

## Works With

Any MCP-compatible client: [Claude Desktop](https://claude.ai/download), [Claude Code](https://claude.com/claude-code), and anything else that speaks the [Model Context Protocol](https://modelcontextprotocol.io).

## Contributing

Bug reports and pull requests welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Security issues: [SECURITY.md](SECURITY.md).

If you are reporting something audio-related, say which plugin and which Audacity build, and include what you measured rather than what it sounded like where you can. Most of the bugs fixed here were found that way.

## License

[Apache 2.0](LICENSE)
