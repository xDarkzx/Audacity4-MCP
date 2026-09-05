<h1 align="center">Audacity4MCP</h1>

<p align="center">
  <strong>AI-powered audio editing in Audacity 4 through the Model Context Protocol</strong>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-green.svg" alt="License" /></a>
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-compatible-purple.svg" alt="MCP Compatible" /></a>
  <img src="https://img.shields.io/badge/status-early%20alpha-orange.svg" alt="Early alpha" />
</p>

<p align="center">
  <a href="#status">Status</a> &bull;
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="#architecture">Architecture</a> &bull;
  <a href="docs/TOOLS.md">Tool Reference</a> &bull;
  <a href="#known-gaps">Known Gaps</a>
</p>

---

Audacity4MCP connects any MCP-compatible AI assistant to [Audacity 4](https://www.audacityteam.org/), giving it control over audio editing, effects, VST3 plugins, and cleanup pipelines through a locally-running TCP bridge. This is the sibling project to [AudacityMCP](https://github.com/xDarkzx/Audacity-MCP), which does the same thing for Audacity 3.x.

**No cloud. No API keys for audio processing. Everything runs locally** through a TCP JSON-RPC bridge built into a custom Audacity 4 fork ([`Audacity4-Dev`](../Audacity4-Dev)), since Audacity 4 shipped without any scripting/automation surface at all.

## Status

**This is early alpha, under active daily development. Expect gaps, and expect things to change.**

Unlike the v3 project (mature, 144 tools, used in production podcast/mastering workflows), Audacity4MCP exists because Audacity 4.0 removed scripting entirely (no more mod-script-pipe) and shipped no replacement. This project pairs with a custom Audacity 4 fork that adds one back in from scratch, command by command, verified live against a real running instance as each piece is built.

What that means in practice:

- Every command exposed here has been implemented against Audacity 4's *actual* current internals (not ported blindly from v3 — v4 renamed and restructured a lot) and live-tested against a running Audacity 4 instance, not just unit-tested against mocks.
- Some things genuinely don't work yet or have known limitations — see [Known Gaps](#known-gaps) below rather than assuming full v3 parity.
- There is no packaged installer yet. You need to build the companion `Audacity4-Dev` fork yourself (Windows/MSVC currently the only tested toolchain).

If you want the stable, production-ready version for Audacity 3.x, use [AudacityMCP](https://github.com/xDarkzx/Audacity-MCP) instead.

## Quick Start

1. Build and run the companion fork, [`Audacity4-Dev`](../Audacity4-Dev) — see its own build instructions. Its `mcp` module starts a TCP JSON-RPC server on `127.0.0.1:2212` as soon as Audacity launches.
2. Install this server:

   ```bash
   git clone https://github.com/xDarkzx/Audacity4-MCP.git
   cd Audacity4-MCP
   pip install -e .
   ```

3. Point your MCP client at it. For Claude Desktop / Claude Code, add to your MCP config:

   ```json
   {
     "mcpServers": {
       "audacity4": {
         "command": "audacity4-mcp"
       }
     }
   }
   ```

4. Launch Audacity4-Dev, open or create a project, and start talking to it through your AI assistant.

Full setup details: [docs/INSTALLATION.md](docs/INSTALLATION.md).

## Architecture

```
AI assistant (Claude, etc.)
      │  MCP (stdio)
      ▼
Audacity4MCP  (this repo — Python, FastMCP)
      │  TCP JSON-RPC, 127.0.0.1:2212
      ▼
Audacity4-Dev  (C++ fork — src/mcp/ module)
      │  dispatcher / interface calls
      ▼
Audacity 4 engine (tracks, effects, VST3 hosting, ...)
```

Audacity 4 has no scripting surface of its own, so the bridge is built directly into a fork: `src/mcp/internal/audacitycommandscontroller.cpp` registers each command against Audacity 4's real internal interfaces (`ITrackeditProject`, `ISelectionController`, `IEffectsProvider`, `IRealtimeEffectService`, `IEffectParametersProvider`, etc.), and `bridge_client.py` on this side is a plain `asyncio` TCP client — no WebSocket library involved despite what the fork's module name might suggest.

Tool count is real, not aspirational — every tool below maps to a command that has been implemented and registered on the C++ side; see [docs/TOOLS.md](docs/TOOLS.md) for the full, current list (130+ tools as of this writing, across transport, track, edit, selection, effects, realtime/VST3 effects, generators, labels, project lifecycle, analysis, transcription, and cleanup pipelines).

## Known Gaps

- **VST3 realtime discrete parameters don't stick.** Continuous parameters (frequency, gain, Q, threshold, ratio, attack/release, mix) on realtime VST3 effects (tested against FabFilter Pro-Q 3 / Pro-C 2, Valhalla VintageVerb) can be read and set correctly, verified via independent re-reads. But discrete/list-type parameters (e.g. Pro-Q 3's per-band "Shape" selector: Bell/Low Shelf/High Shelf/etc.) do not persist — root-caused to `VST3Wrapper::FlushParameters` in Audacity's own VST3 host code being a no-op for any realtime effect instance (which stays `mActive == true` for its whole life), confirmed live by testing with actual audio playback running. Fix would need to live in Audacity 4's core VST3 wrapper, not this server. Parked for now.
- **VST3 factory presets are usually empty.** `list_effect_presets` genuinely returns an empty list for plugins (FabFilter, Valhalla) that keep their presets inside their own custom in-plugin browser rather than the standard VST3 host-preset-list API — this matches their behavior in other DAWs too, not an Audacity-specific bug.
- Several v3-parity tools have no v4 engine support yet and are deliberately not implemented rather than shipped broken: `track_mix_and_render`, `track_stereo_to_mono`, `track_align_end_to_end`, `project_import_midi`.
- A handful of v3 effects (Echo, Phaser, Wahwah, Distortion, Repeat, ChangeTempo, ChangeSpeed, Equalization, AutoDuck) have source present in the v4 fork's tree but are confirmed, via the real runtime plugin registry, to never actually compile/link into this build — they are not wrapped here since wrapping a non-existent effect is worse than not having it.

See [CHANGELOG.md](CHANGELOG.md) for the full history of what's been found and fixed.

## Works With

Any MCP-compatible client: [Claude Desktop](https://claude.ai/download), [Claude Code](https://claude.com/claude-code), and any other assistant that speaks the [Model Context Protocol](https://modelcontextprotocol.io).

## License

[Apache 2.0](LICENSE)
