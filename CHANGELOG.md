# Changelog

All notable changes to Audacity4MCP will be documented in this file.

This is early alpha under active daily development.

## [Unreleased]

### Added: Tool Profiles, So a Session Doesn't Have to Load All 156 Tools

By default every tool still loads (nothing changes for existing configs). Set `AUDACITY4_MCP_PROFILE` in an MCP client's `env` block to register only a workflow-scoped subset instead, cutting the tool-schema footprint sent to the model every turn. Six built-in profiles: `full` (default, all 12 modules), `cleanup` (podcast/audiobook/vocal cleanup + mastering, no cutting/labeling), `editing` (cut/trim/split/label, no effects), `mastering` (music mastering + generators), `transcription` (transcribe-and-label only), `minimal` (bare transport/track/project). Fine-grained `AUDACITY4_MCP_INCLUDE_MODULES`/`EXCLUDE_MODULES`/`INCLUDE_TOOLS`/`EXCLUDE_TOOLS` env vars layer on top of whichever profile is picked. `audacity4-mcp --profile-info --profile <name> [--json]` reports a profile's real registered tool count and schema size without starting a session. Modeled directly on `reaper-mcp`'s existing `REAPER_MCP_PROFILE` system after reading its `tool_registry.py`.

### v4-Exclusive Clip Editing: Non-Destructive Pitch/Speed, Trim/Stretch, More

Surveyed `ITrackeditInteraction` (the interface everything already goes through) and found a batch of real, working, never-exposed capabilities that never existed in v3 at all: `clip_set_pitch`/`clip_reset_pitch`, `clip_set_speed`/`clip_reset_speed`, `clip_render_pitch_speed`, `clip_reset_pitch_speed` (non-destructive per-clip pitch/speed, no audio processing until explicitly rendered), `clip_split_at_silences`/`split_range_at_silences`, `clip_trim`/`clip_stretch`, `nearest_zero_crossing`, `clip_set_color`/`track_set_color`.

Two non-obvious behaviors found via live testing and documented rather than assumed: `clip_set_speed`'s `speed` is a **duration** multiplier, not a playback-rate multiplier (`speed=2.0` makes a clip take *twice as long*, the opposite of what "speed" implies elsewhere); and `clip_trim`/`clip_stretch` use the *same* sign convention on both edges — positive `delta_sec` always shrinks inward, negative always grows outward, despite "stretch" suggesting the opposite.

### suggest_and_add_effect: Auto-Pick and Apply a Plugin for a Stated Goal

Searches every installed, realtime-capable effect (Builtin and VST3) and picks a good match for a category (`reverb`, `compressor`, `eq`, `delay`, `limiter`, `distortion`, `gate`, `chorus`, `phaser`, `flanger`, `deesser`), applies it as a non-destructive realtime effect, and returns the alternatives too. Three real false-positive matching bugs found and fixed along the way — all naive-substring-match variants: "hall" matched inside vendor "Valhalla" (wrong pick for reverb), "eq" matched inside "Freq", "comp" matched inside vendor "ComposeAI". Fixed with camelCase-aware word-prefix matching (not bare substring, not exact-word — "compress" must match "Compressor" despite being only a prefix). Live-verified across 6 categories against the real installed plugin set.

### auto_master_music Grounded in Real, Cited Genre Loudness Targets

Previously only capped peaks at a fixed -3dB ceiling with no loudness target — discovered live this made an already-hot EDM track measurably *quieter* (RMS -13.3 → -16.1dB), the opposite of what a mastering pipeline should do for a track already below its genre's competitive loudness. Added real integrated-LUFS targets per genre (midpoint of published 2026 mastering-industry consensus ranges, sourced in `_mastering_pipeline`'s docstring): EDM -7.5, hip-hop -9.0, pop -9.5, rock -10.5, classical/acoustic -14.0. Pushed via the same clip-checked loudness step the podcast/audiobook pipelines use, falling back to peak-only reduction if hitting the target would clip. Peak ceiling tightened to -2dBFS sample peak (from -3dB), documented as a conservative proxy for the -1dBTP true-peak ceiling streaming platforms require (true peak can exceed sample peak by up to 3dB on inter-sample peaks — disclosed as a proxy, not real dBTP metering). Also fixed a real bug found along the way: the loudness step's clip-fallback ignored its own `peak_ceiling` parameter and always reduced to a hardcoded -3dB, silently wrong for every existing caller.

### Closed Remaining v3-Parity Gaps

- `project_get_metadata`/`project_set_metadata` — real ID3-style project tags (artist/title/album/track number/year/comments), backed by a genuine `IMetadata` C++ interface that an earlier pass in this project incorrectly logged as "confirmed absent." Live-confirmed a real quirk: a brand new project's `year` defaults to `"2018"`, not empty or today's date.
- `label_edit` — move a label's start/end and/or rename its text in one call.
- `track_mute_all`/`track_unmute_all` — previously blocked by a real index-mismatch risk (`track_set_properties` indexes through all tracks including label tracks, but the track list elsewhere excludes them); fixed with a new C++ command that iterates the real track list by id.
- `transport_play` — v4 only had a play/stop toggle, no unconditional "start playing"; composed from `transport_get_play_position` + a conditional `play-stop`.
- `auto_cleanup_audio` — the generic "clean without touching loudness" pipeline, distinct from the named ones (podcast/interview/etc).
- `label_import`/`label_export`/`label_export_chapters`/`label_export_audio_segments` — v4 has no `ImportLabels`/`ExportLabels` scripting command like v3 did; implemented in pure Python instead, reading/writing the same standard tab-separated label file format.
- Added real test coverage for `analyze_beat_finder`/`analyze_label_sounds` (previously zero, despite being built and shipped) — both live-verified: beat finder found 85 real beats on a real ambient track, label_sounds correctly labeled it as one continuous sound region.
- Confirmed genuine dead ends, not wrapped: `effect_vocal_reduction` (absent from the real plugin registry, same verification technique as the other known-missing effects).

## [0.1.0] - 2026-09-05

### Realtime/VST3 Effects: New Surface, Three Real Bugs Found Along the Way

Built the whole non-destructive effects path this session: `add_realtime_effect`, `list_realtime_effects`, `remove_realtime_effect`, `set_realtime_effect_active`, `list_effect_parameters`, `set_effect_parameter`, `list_effect_presets`, `apply_effect_preset`. This is now the priority effects surface — most users want to tweak a plugin's settings live (reverb decay, EQ curve, compressor ratio), not permanently bake an effect in.

Confirming this actually worked against a real VST3 (Valhalla VintageVerb, then FabFilter Pro-Q 3 / Pro-C 2) surfaced three separate, real bugs:

- **Realtime effect instances were never registered with `IEffectInstancesRegister`.** Only the UI's own settings-panel dialog does this registration today (`RealtimeEffectViewerDialogModel::reload()`) — headless MCP calls got "Effect instance not found" for every parameter read/write. Fixed by replicating that exact registration pattern (idempotent, checked on first use) in the C++ controller.
- **`setParameterValue()` silently failed to stick on VST3 plugins.** Calls reported success and even echoed a plausible-looking value, but an independent fresh re-read showed nothing had changed. Root cause: VST3 plugins require `beginParameterGesture()`/`setParameterValue()`/`endParameterGesture()` bracketing to distinguish real automation from a spurious write — a bare call silently no-ops. Fixed by wrapping every write in the gesture calls; verified via a second, independent parameter read after the fact, not just trusting the immediate response.
- **A Unity-build ambiguous-symbol compile error** (`C2872: 'TranslatableString'`) when linking `au3wrap` into the mcp module — a legacy AU3 header pulled in transitively declares its own non-`muse::` `TranslatableString`, colliding with `using namespace muse;` in the Unity-merged command registrar. Fixed with `SKIP_UNITY_BUILD_INCLUSION ON` on the affected file, matching an existing pattern already used elsewhere in the fork.

### Fixed: Bridge Read Buffer Silently Broke on Large Parameter Dumps

`bridge_client.py`'s `asyncio.open_connection()` used the default 64KB `StreamReader` line limit. FabFilter Pro-Q 3 (a 24-band EQ) reports 492 real automatable parameters in one response — comfortably over that limit — and the call raised `LimitOverrunError`. Fixed by passing `limit=16*1024*1024` explicitly.

### Fixed: `transport_play_region` Ignored the Region It Just Selected

Originally composed `select-time` + `play-stop` (a toggle). Live testing proved `play-stop` just resumes wherever playback last was, ignoring the just-set selection entirely. Root cause: `play-stop` and "play this specific selection" are genuinely different actions in Audacity 4 (`PlaybackController::playSelectionAction()`, `action://playback/play-selection`). Added the missing `play-selection` command and switched the tool to use it — verified live (a 60s-offset region reported `playPosition: 62.08` after ~2s of playback, matching offset + elapsed correctly).

### Known Limitation, Not Fixed Here: VST3 Discrete/List Parameters Don't Persist

Continuous VST3 parameters (frequency, gain, Q, threshold, ratio, attack/release, mix) work correctly through `set_effect_parameter` — verified via independent re-reads. Discrete/list-type parameters (e.g. FabFilter Pro-Q 3's per-band "Shape" selector) do not, even with correct value encoding (raw index and normalized fraction both tested). Root-caused to `VST3Wrapper::FlushParameters` — Audacity's own documented workaround for "plugins that read parameter values directly from the DSP model" — being a no-op for any realtime effect instance, since those stay `mActive == true` for their entire life (confirmed with actual audio playback running during the test, ruling out a "just needs a process() call" explanation). The fix, if pursued, lives in Audacity 4's own VST3 host code, not this server. See [README's Known Gaps](README.md#known-gaps).

### Verified Existing Effects Against the Real Plugin Registry, Not Source Presence

Several v3 effects were initially wrapped based on source files existing in the fork's tree (Echo, Phaser, Wahwah, Distortion, Repeat, ChangeTempo, ChangeSpeed, Equalization, AutoDuck) — all failed live with "Effect not found." Root cause: source presence in `au3/src/effects/*.cpp` does not mean an effect is actually compiled into this fork's build. Ground truth is the real runtime-generated `known_audio_plugins.json`. Removed all 11 wrappers rather than ship tools that can never succeed; same technique later confirmed `StereoToMono`, `project_edit_metadata`, `analyze_contrast`, `analyze_plot_spectrum`, and `analyze_find_clipping` as genuinely absent too.

### Added

- `project_get_info`, `track_get_info`, `select_clip`, `transport_get_play_position`, `list_effects` and the full realtime-effects surface above on the C++ side, plus matching Python wrappers.
- Analysis tools: `analyze_beat_finder`, `analyze_label_sounds`, `analyze_sample_data_export`.
- Generators: `generate_silence`, `generate_rhythm_track` (full real parameter set, not a v3 port — tempo/swing/click-type/pitch all confirmed against v4's actual Rhythm Track effect).
- Full label-region composite ops: `label_cut_regions`, `label_delete_regions`, `label_silence_regions`, `label_split_regions`, `label_join_regions`, plus `label_add_at`, `label_add_batch`, `label_get_all`, `label_find`, `label_regular_intervals`, `label_delete_audio_at`.
- Full edit/selection/track surfaces ported and verified against v4's real interfaces (not v3's parameter names, which don't carry over — v4 renamed and restructured extensively).

### Initial Commits

- `6cec293` — Initial commit: Audacity 4 MCP server with audio cleanup pipelines (podcast, audiobook, interview, vocal, live, music mastering, lo-fi).
- `c2e99a7` — Removed dead pre-discovery scaffolding, fixed a stale tool-count assertion.
- `ef22bf5` — Python wrappers for the first 7 playback/project MCP commands built on the C++ side.
