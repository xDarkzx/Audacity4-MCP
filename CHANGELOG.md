# Changelog

All notable changes to Audacity4MCP will be documented in this file.

This is early alpha under active daily development.

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
