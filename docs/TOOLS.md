# Tool Reference

All tools take/return plain JSON. Every tool listed here maps to a real command implemented and registered in `Audacity4-Dev`'s `src/mcp/` module — nothing here is aspirational. Where a tool has a genuinely non-obvious quirk (confirmed by live testing against a real running Audacity4-Dev instance), it's called out below; see each tool's own docstring for the full detail.

Jump to: [Transport](#transport) · [Project](#project) · [Track](#track) · [Selection](#selection) · [Edit](#edit) · [Effects](#effects) · [Realtime/VST3 Effects](#realtimevst3-effects) · [Generate](#generate) · [Labels](#labels) · [Analysis](#analysis) · [Transcription](#transcription-experimental) · [Cleanup Pipelines](#cleanup-pipelines)

## Transport

| Tool | Description |
|---|---|
| `transport_play_stop()` | Toggle playback (play if stopped, stop if playing). |
| `transport_pause()` | Pause playback. |
| `transport_stop()` | Stop playback. |
| `transport_rewind_start()` | Move the cursor to project start. |
| `transport_record()` | Start recording on a new track. Needs a working input device — dispatches without error but won't actually record if none is configured. |
| `transport_get_play_position()` | Get playhead position, whether playback is active, and current selection start/end. |
| `transport_play_region(start, end)` | Select and play a time region from its beginning. Uses the dedicated `play-selection` action — an earlier `select-time` + `play-stop` composition was tried and confirmed broken (ignored the just-set selection). |

## Project

| Tool | Description |
|---|---|
| `get_default_export_folder()` | User's Music folder (falls back to home). |
| `project_new()` | New project — only works with no project already open. |
| `project_open(path)` | Open a `.aup4` file. `.aup3` (v3 format) triggers an interactive conversion prompt, unsafe over MCP. |
| `project_import_audio(path)` | Import an audio file as a new track. |
| `project_close()` | Close the current project. Refuses if there are unsaved changes. |
| `project_save_as(path, overwrite=False)` | Save to a new `.aup4` file. Only call when the user explicitly asks. |
| `project_export_audio(path, overwrite=False)` | Export the full project (stereo, 44.1kHz WAV). Refuses paths directly in the home folder root. |
| `project_export_selection(path, overwrite=False)` | Export just the current selection (mono, 44.1kHz WAV). |
| `project_save()` | Save the current project. Refuses if never saved before or nothing changed. |
| `project_get_info()` | Path, display name, unsaved-changes state, duration, and the full track list (id/title/type/rate/mute/solo/clip count) — excludes label tracks. |
| `project_get_metadata()` / `project_set_metadata(artist=, track_title=, album=, track_number=, year=, comments=)` | Real ID3-style project tags. **A brand new project's `year` is not empty** — confirmed live it defaults to `"2018"` (a stale template default, not today's date). Only fields you pass to the setter are changed. |
| `recent_commands()` | List recently executed MCP commands with id/timestamp/success/message. |
| `command_status(command_id)` | Look up a previous command's recorded result by id. |

## Track

| Tool | Description |
|---|---|
| `track_add_mono()` / `track_add_stereo()` | Add a new track. |
| `track_remove()` | Remove the currently selected track(s). |
| `track_set_properties(track, name=, gain=, pan=, mute=, solo=)` | Set one or more properties by 0-based index; only passed fields change. |
| `track_duplicate()` | Duplicate the selected track(s). |
| `track_resample(rate)` | Resample selected track(s), 1–384000 Hz. |
| `track_get_info(track_id)` | Full detail for one track (title/type/rate/mute/solo + full clip or label list). Takes the real `track_id` from `project_get_info`, **not** the 0-based index used elsewhere. |
| `track_mute(track, mute=True)` | Convenience wrapper over `track_set_properties`. |

Not implemented, deliberately: `track_mix_and_render`, `track_stereo_to_mono`, `track_align_end_to_end` — no v4 engine support exists for these yet; shipping them would silently no-op or break.

## Selection

| Tool | Description |
|---|---|
| `select_all()` / `select_none()` | Select/deselect everything. |
| `select_region(start, end)` | Select a time region on whichever tracks are currently selected. |
| `select_tracks(track, count=1)` | Select one or more tracks by 0-based index. |
| `select_zero_crossing()` | Snap current selection boundaries to nearest zero crossings (avoids click artifacts at edit points). |
| `cursor_set(time)` | Move the cursor to an exact time. |
| `cursor_to_project_start()` / `cursor_to_project_end()` | Cursor to t=0 / project duration. |
| `cursor_to_track_start(track_id)` / `cursor_to_track_end(track_id)` | Cursor to a track's earliest/latest clip edge. Takes explicit `track_id` — v4 has no "currently selected track" query yet, unlike v3. |
| `select_clip(key)` | Select a specific clip (`"trackId:itemId"` from `track_get_info`) — its track, itself, and its time range. |
| `select_cursor_to_track_end(track_id)` | Select from the current cursor position to a track's end. |

## Edit

| Tool | Description |
|---|---|
| `edit_cut()` / `edit_copy()` / `edit_paste()` | Standard clipboard ops. `edit_paste` pastes at the start of the current selection. |
| `edit_delete()` | Delete selection, closing the gap. |
| `edit_split()` | Split clip(s) at selection boundaries in place. |
| `edit_trim()` | Delete everything outside the selection. |
| `edit_silence()` | Replace selection with silence. |
| `edit_duplicate()` | Duplicate selection into a new track. |
| `edit_split_new()` | Split into a new track, original unchanged. |
| `edit_split_cut()` / `edit_split_delete()` | Cut/delete WITHOUT closing the gap (leaves silence). |
| `edit_disjoin()` | Split into separate clips at detected silences. |
| `edit_join()` | Join selected clips into one. |
| `edit_undo()` / `edit_redo()` | Undo/redo one step. Fails cleanly if there's nothing to undo/redo. |

### Clip Editing (v4-exclusive, no v3 equivalent)

Per-clip operations addressed by key (from `track_get_info`), not the current selection — v3 never had non-destructive clip-level pitch/speed at all.

| Tool | Description |
|---|---|
| `clip_set_pitch(key, semitones)` / `clip_reset_pitch(key)` | Non-destructive pitch shift, no audio processing — pure playback-time transform, reversible. |
| `clip_set_speed(key, speed)` / `clip_reset_speed(key)` | Non-destructive speed/duration change. **CONFIRMED LIVE: `speed` is a duration multiplier, not a playback-rate multiplier** — `new_duration = original_duration * speed`. `speed=2.0` makes the clip take *twice as long* (slower), `speed=0.5` makes it *half as long* (faster) — the opposite of what "speed" implies elsewhere. |
| `clip_render_pitch_speed(key)` | Permanently bake pitch/speed changes into the audio. |
| `clip_reset_pitch_speed(key)` | Revert both pitch and speed in one call. |
| `clip_split_at_silences(key)` | Auto-split one specific clip at its detected silence boundaries (vs. `edit_disjoin`, which acts on the current selection). |
| `split_range_at_silences(start, end)` | Auto-split every clip on the selected track(s) within a time range. |
| `clip_trim(key, side, delta_sec, min_clip_duration=0)` / `clip_stretch(key, side, delta_sec, min_clip_duration=0)` | Trim (discard) or stretch (reveal/time-stretch) a clip edge. **CONFIRMED LIVE: for both, and for both `side` values, positive `delta_sec` shrinks the clip inward; negative grows it outward** — despite "stretch" suggesting the opposite. To restore 1s trimmed off the right edge: `clip_stretch(key, "right", -1.0)`, not `+1.0`. |
| `nearest_zero_crossing(time)` | Nearest zero-crossing to an arbitrary timestamp, independent of the current selection (unlike `select_zero_crossing`). |
| `clip_set_color(key, color_index)` / `track_set_color(color_index)` (track_tools) | Color tag for visual organization, 0 (inherit) to 9. |

## Effects

Destructive, permanently-applied effects — use [Realtime/VST3 Effects](#realtimevst3-effects) instead if the user wants something adjustable/tweakable rather than baked in.

| Tool | Description |
|---|---|
| `list_effects(category=, family=, search=, limit=100)` | List effects actually installed (Builtin/VST3/Nyquist/etc). **`category` only works for Builtin/Nyquist** — third-party VST3s all come back with category `"None"` regardless of what they actually are; use `family="VST3"` + `search="<vendor or name>"` instead. Returns both `title` (what `apply-effect` accepts, with fallback) and `id` (the real PluginID, required by realtime-effect tools). |
| `normalize(peak_level_db=-3.0, remove_dc=True, stereo_independent=False)` | Normalize to a target peak. |
| `get_noise_profile()` | Capture a noise profile from the current (noise-only) selection. Call before `noise_reduction`. |
| `noise_reduction(sensitivity=6.0, noise_gain_db=12.0, frequency_smoothing_bands=3)` | Apply noise reduction using the captured profile. |
| `compressor(threshold_db, ratio, attack_ms, release_ms, makeup_gain_db, knee_width_db)` | Dynamic range compression. |
| `limiter(threshold_db, makeup_target_db, release_ms, knee_width_db)` | Ceiling limiter. |
| `loudness_normalize(lufs_level=-16.0, ...)` | LUFS normalization. **Can boost quiet audio into clipping** — measure with `auto_analyze_audio` first. |
| `click_removal(threshold=200, spike_width=20)` | Remove clicks/pops (e.g. vinyl). |
| `bass_and_treble(bass=0, treble=0, gain=0)` | Simple tonal shaping. |
| `effect_amplify(ratio=1.0, allow_clipping=False)` | Linear amplitude scaling. |
| `effect_fade_in()` / `effect_fade_out()` | Fade the selected region. |
| `effect_reverb(...)` | Built-in reverb (room size, pre-delay, reverberance, damping, tone, wet/dry gain, stereo width). |
| `effect_change_pitch(semitones, use_high_quality_stretching=False)` | Change pitch without changing tempo. |
| `effect_paulstretch(stretch_factor=10.0, time_resolution=0.25)` | Extreme time-stretch. |
| `effect_reverse()` / `effect_invert()` | Reverse audio / invert phase. |
| `effect_repair()` | Repair a short damaged region (clicks, glitches). |
| `effect_sliding_stretch(...)` | Variable-rate time/pitch stretch. |
| `effect_remove_dc_offset()` | DC offset removal (composed from `Normalize` with volume untouched). |
| `effect_adjustable_fade(...)` | Custom fade curve. **Requires a single-clip selection** — confirmed to crash on a multi-clip selection (real engine bug, not this wrapper). |
| `truncate_silence(...)` | Shorten long silences. |
| `effect_clip_fix(threshold=95.0, gain_db=-9.0)` | Repair clipped samples (Nyquist). |
| `effect_crossfade_clips()` / `effect_crossfade_tracks(curve_type=0)` | Crossfade adjacent clips/tracks (Nyquist). |
| `effect_studio_fade_out()` | Studio-style fade out (Nyquist). |
| `effect_notch_filter(frequency_hz=60.0, q=1.0)` | Notch filter, e.g. mains hum removal (Nyquist). |
| `effect_tremolo(...)` | Tremolo effect (Nyquist). |

**Confirmed absent from this build**, not wrapped (source exists upstream but never links into this fork — verified against the real runtime plugin registry, not just source presence): Echo, Phaser, Wahwah, Distortion, Repeat, ChangeTempo, ChangeSpeed, Equalization, AutoDuck, StereoToMono, Contrast, Plot Spectrum, Find Clipping.

## Realtime/VST3 Effects

Non-destructive — stays adjustable, removable, and its native plugin GUI can still be opened live in Audacity. **This is the priority effects surface** — most users want to tweak a plugin (reverb amount, EQ curve, compressor ratio) rather than permanently bake it in.

| Tool | Description |
|---|---|
| `suggest_and_add_effect(track_id, category)` | Auto-pick a good *installed* plugin for a goal and add it as a realtime effect — no need to know which of your VSTs does reverb/compression/EQ/etc. `category`: one of `reverb`, `compressor`, `eq`, `delay`, `limiter`, `distortion`, `gate`, `chorus`, `phaser`, `flanger`, `deesser`. Matches by keyword against title/vendor (VST3 plugins don't reliably self-report a category), with a soft preference for a few well-regarded vendors — not an objective quality ranking, there isn't one. Returns `alternatives` too, so the pick isn't a black box. |
| `add_realtime_effect(track_id, effect_id)` | Add an effect to a track's chain, or the Master bus (`track_id=-2`). **Requires the real `id` from `list_effects`, not `title`** — no title fallback here, unlike destructive `apply-effect`. |
| `list_realtime_effects(track_id)` | List a chain's effects: index, name, active state. |
| `remove_realtime_effect(track_id, index)` | Remove by index. |
| `set_realtime_effect_active(track_id, index, active)` | Enable/bypass without removing. |
| `list_effect_parameters(track_id, index)` | Real, plugin-reported parameters — name, units, min/max/default/current value, formatted string. Works uniformly across Builtin/VST3/LV2/AudioUnit. |
| `set_effect_parameter(track_id, index, parameter_id, value)` | Set one parameter to an exact value. **VST3 min/max is typically normalized 0–1** for some plugins but real display units (e.g. log2-Hz, dB) for others — always re-read `currentValueString` after setting rather than assuming the input scale. See [Known Gaps](../README.md#known-gaps) for the discrete/list-parameter limitation. |
| `list_effect_presets(track_id, index)` | Real factory presets, if the plugin format exposes any via the standard VST3 API. Empty is a normal result for plugins (FabFilter, Valhalla) that keep presets in their own custom in-plugin browser instead. |
| `apply_effect_preset(track_id, index, preset_id)` | Apply a factory preset by id. |

## Generate

Fills the currently selected time range — call `select_region` first to control duration.

| Tool | Description |
|---|---|
| `generate_tone(waveform="Sine", frequency=440.0, amplitude=0.8)` | Tone generator. |
| `generate_chirp(waveform, start_freq, end_freq, start_amp, end_amp)` | Frequency sweep. |
| `generate_noise(noise_type="White", amplitude=0.8)` | White/Pink/Brownian noise. |
| `generate_dtmf(sequence="audacity", duty_cycle=55.0, amplitude=0.8)` | DTMF telephone tones. |
| `generate_silence()` | Silence, no parameters. |
| `generate_rhythm_track(tempo_bpm, beats_per_bar, swing, num_bars, duration_seconds, start_offset, click_type, strong_beat_pitch, weak_beat_pitch)` | Metronome/click track. |

## Labels

| Tool | Description |
|---|---|
| `label_list()` | List labels on the project's first label track. |
| `label_add_track()` | Create a new empty label track. |
| `label_add(text="")` | Add a label at the current selection/playback position. |
| `label_remove(key)` | Remove by key (`"trackId:itemId"`). |
| `label_update_text(key, text)` | Change a label's text. |
| `label_add_at(start, end, text="")` | Add a label at an exact time range regardless of current selection (changes selection as a side effect). |
| `label_add_batch(labels)` | Add multiple labels in one call: `[{"start", "end", "text"}, ...]`. |
| `label_get_all()` | Labels as structured data (key/text/start/end). |
| `label_find(query)` | Case-insensitive substring search over label text. |
| `label_regular_intervals(interval, duration, text_prefix="Marker")` | Labels at fixed spacing across a known duration (caller must supply duration — no query for it yet). |
| `label_delete_audio_at(key)` | Delete the audio under one label, closing the gap. |
| `label_cut_regions()` / `label_delete_regions()` | Cut/delete audio under every label (processes last-to-first so times stay valid). Only the last cut survives on the clipboard. |
| `label_silence_regions()` | Silence audio under every label, timeline length unchanged. |
| `label_split_regions()` | Split clips at every label boundary. |
| `label_join_regions()` | Join clips across every labeled region. |

## Analysis

| Tool | Description |
|---|---|
| `auto_analyze_audio()` | Export + measure current audio: peak, noise floor, RMS, clipping, DC offset, clicks, silence gaps, dynamic range — plus a plain-English recommendation for which cleanup pipeline to run. |
| `analyze_beat_finder(threshold_percent=65)` | Detect beats, add a label at each. |
| `analyze_label_sounds(threshold_db, measurement, min_silence_duration, min_label_interval, label_type)` | Detect sounds separated by silence, label each sound or gap. |
| `analyze_sample_data_export(path, limit=100, units="dB")` | Export raw sample values from the selection to a text/CSV/HTML file. |

**Confirmed absent from this build**: `analyze_contrast`, `analyze_plot_spectrum`, `analyze_find_clipping`.

## Transcription (Experimental)

Requires `pip install faster-whisper` separately — not a dependency of this package. Runs in the background; poll with `check_transcription_status`.

| Tool | Description |
|---|---|
| `get_default_transcription_folder()` | User's Documents folder. |
| `transcribe_audio(model_size="small", language=None, task="transcribe")` | Transcribe the full project. |
| `transcribe_selection(...)` | Transcribe just the current selection. |
| `transcribe_to_labels(...)` | Transcribe and add a label per segment. |
| `transcribe_to_file(...)` | Transcribe and write `.srt`/`.vtt`/`.txt`. |
| `transcription_set_model(model_size="base")` | Pre-load a Whisper model. |
| `check_transcription_status(job_id)` | Poll a running job (every 10–15s). |

Model sizes: `tiny` (75MB) · `base` (145MB) · `small` (488MB) · `medium` (1.5GB) · `large-v3` (3GB) — first use of a given size downloads it.

## Cleanup Pipelines

One-click, multi-step pipelines. All run in the background — call returns a `job_id` immediately, poll with `check_pipeline_status` every 15–30s. Only one pipeline (or transcription) may run at a time.

| Tool | Description |
|---|---|
| `auto_cleanup_podcast(remove_noise=True)` | DC offset → noise reduction → compress 4:1 → safe LUFS -16 (Apple Podcasts target) with clip-safe fallback. |
| `auto_audiobook_mastering(remove_noise=True)` | DC offset → noise reduction → compress 2.5:1 → RMS -20dB (clip-checked) → peak cap -3.5dB. Targets ACX/Audible spec. |
| `auto_cleanup_interview(remove_noise=True)` | Lighter-touch version of the podcast pipeline — preserves natural conversation dynamics. |
| `auto_cleanup_vocal(remove_noise=True)` | DC offset → noise reduction 10dB → compress 3:1 → presence EQ → safe LUFS loudness. |
| `auto_cleanup_live()` | Aggressive: DC offset → click removal → noise reduction 12dB (always on) → compress 5:1 → safe LUFS. First 0.5s must be room tone. |
| `auto_master_music(style="edm", noise_reduce=False)` | Genre-tuned mastering (`edm`/`hiphop`/`rock`/`pop`/`classical`/`acoustic`): compression + bass/treble sweetening + safe peak ceiling, no fixed loudness target. |
| `auto_lofi_effect(intensity="medium")` | `light`/`medium`/`heavy` lo-fi warmth + compression + peak ceiling. Not yet the full frequency-cutoff filtering v3 had. |
| `check_pipeline_status(job_id)` | Poll a running pipeline. |

All pipelines that use noise reduction require the **first 0.5 seconds of the selection to be room tone / ambient noise** for profiling.
