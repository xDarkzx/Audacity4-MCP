# Audacity 4 — Reverse Engineering Research
# Conducted March 2026 (Alpha Build)
# PRIVATE — Do not publish

## Overview
Audacity 4 is a complete rewrite on the MuseScore/Muse framework (Qt6/QML).
The old wxWidgets codebase is gone. mod-script-pipe is gone.
New architecture uses a JavaScript scripting engine with dispatcher actions.

## Source Code
- Main repo: https://github.com/audacity/audacity.git
- Muse framework (submodule): https://github.com/musescore/framework_tmp.git

---

## 1. Dispatcher Action System

Central command system. All operations go through `dispatcher()->dispatch()`.

### Action URI Pattern
```
action://<module>/<verb>?param=value
```

### Complete Action Map (200+ actions)

#### Playback (25+ actions)
- `action://playback/play` — Play
- `action://playback/pause` — Pause
- `action://playback/stop` — Stop
- `action://playback/rewind-start` — Rewind to start
- `action://playback/rewind-end` — Rewind to end
- `action://playback/seek` — Seek to position
- `action://playback/level` — Set playback level
- `toggle-loop-region` — Loop playback
- `metronome` — Toggle metronome
- `playback-time` — Set playback time
- `playback-bpm` — Set tempo
- `playback-time-signature` — Set time signature
- `action://playback/change-api` — Change audio host
- `action://playback/change-playback-device` — Change playback device
- `action://playback/change-recording-device` — Change recording device
- `action://playback/change-input-channels` — Change input channels
- `rescan-devices` — Rescan audio devices
- `clear-loop-region` — Clear loop region
- `set-loop-region-to-selection` — Set loop to selection
- `set-selection-to-loop` — Set selection to loop

#### Record (6 actions)
- `action://record/start` — Record
- `action://record/pause` — Pause recording
- `action://record/stop` — Stop recording
- `action://record/level` — Set record level
- `action://record/toggle-mic-metering` — Show mic metering
- `action://record/toggle-input-monitoring` — Input monitoring

#### Track Edit (60+ actions)
##### Clipboard
- `action://trackedit/copy` — Copy
- `action://trackedit/cut` — Cut
- `action://trackedit/paste-default` — Paste
- `action://trackedit/paste-insert` — Paste (pushes clips)
- `action://trackedit/paste-overlap` — Paste (overlaps)
- `action://trackedit/paste-insert-all-tracks-ripple` — Paste (preserves sync)
- `action://trackedit/delete` — Delete
- `action://trackedit/undo` — Undo
- `action://trackedit/redo` — Redo

##### Clip Operations
- `split` — Split
- `join` — Join selected clips
- `disjoin` — Split at silences
- `duplicate` — Duplicate
- `merge-selected-on-tracks` — Merge selected clips
- `clip-export` — Export clip
- `clip-pitch-speed-open` — Open pitch/speed dialog
- `clip-render-pitch-speed` — Render pitch/speed
- `trim-audio-outside-selection` — Trim
- `silence-audio-selection` — Silence
- `group-clips` / `ungroup-clips` — Group/ungroup
- `stretch-clip-to-match-tempo` — Stretch with tempo

##### Ripple Editing
- `cut-per-clip-ripple` / `cut-per-track-ripple` / `cut-all-tracks-ripple`
- `delete-per-track-ripple` / `delete-all-tracks-ripple`

##### Track Management
- `track-rename` — Rename track
- `track-duplicate` — Duplicate track
- `track-delete` — Delete track
- `track-move-up` / `track-move-down` / `track-move-top` / `track-move-bottom`
- `track-change-rate-custom` — Change sample rate
- `track-make-stereo` — Make stereo
- `track-swap-channels` — Swap L/R
- `track-split-stereo-to-lr` / `track-split-stereo-to-center`
- `track-resample` — Resample
- `new-mono-track` / `new-stereo-track` / `new-label-track`

##### Track View
- `action://trackedit/track-view-waveform` — Waveform view
- `action://trackedit/track-view-spectrogram` — Spectrogram view
- `action://trackedit/track-view-multi` — Multi view
- `action://trackedit/global-view-spectrogram` — Toggle spectral
- `action://trackedit/clip/change-color-auto` — Auto clip color
- `action://trackedit/track/change-format?format=N` — Change format
- `action://trackedit/track/change-rate?rate=N` — Change rate

##### Labels
- `label-add` / `label-delete` / `label-cut` / `label-copy`

##### Track View Navigation
- `track-view-item-move-left/right/up/down`
- `track-view-item-extend-left/right`
- `track-view-item-reduce-left/right`
- `track-view-next-panel/prev-panel/next-item/prev-item`
- `track-view-next-track/prev-track/first-track/last-track`
- `track-view-toggle-selection/range-selection`
- `track-view-item-context-menu`

#### Project (80+ actions)
##### File
- `file-new` / `file-open` / `file-save` / `file-save-as` / `file-save-backup`
- `file-close` / `clear-recent`
- `project-import` — Import
- `export-audio` — Export audio
- `export-labels` — Export labels
- `export-midi` — Export MIDI

##### Edit
- `duplicate` / `insert` / `rename-item` / `trim-clip`
- `split-into-new-track` / `silence-audio`
- Label operations: `cut-labels`, `copy-labels`, `delete-labels`, `split-labels`, `join-labels`, `silence-labels`, `disjoin-labels`
- `manage-labels` / `manage-metadata`

##### Selection
- `select-all` / `select-all-tracks` / `clear-selection`
- `select-left-of-playback-position` / `select-right-of-playback-position`
- `select-track-start-to-cursor` / `select-cursor-to-track-end`
- `select-previous-clip` / `select-next-clip`
- `toggle-spectral-selection` / `zero-cross`

##### View
- `zoom-in` / `zoom-out` / `zoom-to-selection` / `zoom-toggle` / `zoom-reset`
- `fit-project-to-window` / `fit-view-to-project`
- `collapse-all-tracks` / `expand-all-tracks`
- `toggle-effects` / `toggle-metadata-editor` / `toggle-history`

##### Record Menu
- `record-on-current-track` / `record-on-new-track`
- `set-up-timed-recording` / `punch-and-roll-record`
- `toggle-sound-activated-recording` / `set-sound-activation-level`

##### Track Menu
- `duplicate-track` / `remove-tracks` / `mixdown-to`
- Alignment: `align-end-to-end`, `align-together`, `align-start-to-zero`, `align-start-to-playhead`, etc.
- `sort-by-time` / `sort-by-name` / `keep-tracks-synchronised`

##### Effects/Generate/Analyze Menu
- `effect-plugin-manager` / `generate-plugin-manager` / `analyze-plugin-manager`
- `add-realtime-effects`
- `favourite-effect-1/2/3`
- `contrast-analyzer` / `plot-spectrum`

##### Tools
- `manage-macros` / `apply-macros-palette`
- `nyquist-prompt` / `nyquist-plugin-installer`
- `sample-data-export` / `sample-data-import` / `raw-data-import`
- `reset-configuration`

#### Effects (8 static + dynamic per-effect)
- `repeat-last-effect` — Repeat last effect
- `realtimeeffect-remove` — Remove realtime effect
- `action://effects/presets/apply` — Apply preset
- `action://effects/presets/save` — Save preset
- `action://effects/presets/delete` — Delete preset
- `action://effects/presets/import` / `export` — Import/export preset
- `action://effects/toggle_vendor_ui` — Toggle vendor UI
- `action://effects/open?effectId=<id>` — Open effect (dynamic)
- `action://effects/realtime-add?effectId=<id>` — Add realtime effect (dynamic)
- `action://effects/realtime-replace?effectId=<id>` — Replace realtime effect (dynamic)

#### App Shell (25+ actions)
- `quit` / `restart` / `fullscreen`
- `preference-dialog` / `audio-settings`
- Layout toggles: `toggle-transport`, `toggle-tracks`, `toggle-instruments`, `inspector`, etc.
- Global aliases: `action://copy` → `action://trackedit/copy`, etc.

#### Project Scene (20+ actions)
- Tools: `clip-gain`, `split-tool`, `snap`
- View: `minutes-seconds-ruler`, `beats-measures-ruler`, `toggle-vertical-rulers`
- `show-master-track` / `toggle-rms-in-waveform` / `toggle-clipping-in-waveform`
- `clip-properties` / `clip-rename` / `clip-pitch-speed`
- `play-position-decrease` / `play-position-increase`

---

## 2. Two Script Engines

### Autobot Scripts (internal testing)
Location: `C:\Program Files\Audacity 4\autobotscripts\`
Global object: `api` (ScriptApi)

Available APIs:
- `api.dispatcher` — dispatch actions (FULL ACCESS)
- `api.keyboard` — simulate keyboard input
- `api.navigation` — navigate UI
- `api.shortcuts` — trigger shortcuts
- `api.accessibility` — UI element tree
- `api.process` — process control
- `api.filesystem` — file access
- `api.interactive` — dialogs
- `api.log` — logging
- `api.autobot` — test runner (sleep, setInterval, etc.)
- `api.context` — script context

Usage:
```javascript
api.dispatcher.dispatch("file-new");
api.dispatcher.dispatch("zoom-x-percent", [100]);
api.keyboard.key("Ctrl+S");
api.autobot.sleep(1000);
```

### Extensions (user plugins)
Location: `C:\Users\<user>\AppData\Local\Audacity\Audacity4\extensions\`
Global object: `api` (ExtApi)

Available APIs:
- `api.log` — logging
- `api.interactive` — dialogs
- `api.theme` — theme info
- `api.websocket` — WebSocket client
- `api.websocketserver` — WebSocket server

BLOCKED APIs (commented out in source for security):
- ~~api.dispatcher~~ — "Providing these APIs requires approval"
- ~~api.keyboard~~
- ~~api.navigation~~
- ~~api.shortcuts~~
- ~~api.accessibility~~
- ~~api.process~~
- ~~api.filesystem~~

### Key Difference
Autobot = full control, no networking
Extensions = networking (WebSocket), no control

---

## 3. Extension System

### Manifest Format (manifest.json)
```json
{
  "uri": "muse://extensions/my-extension",
  "type": "macros",
  "title": "My Extension",
  "description": "What it does",
  "version": "1.0.0",
  "apiversion": 2,
  "actions": [
    {
      "code": "main",
      "path": "main.js",
      "type": "macros",
      "title": "Run",
      "func": "main",
      "show_on_appmenu": true
    }
  ]
}
```

### Types
- `"macros"` — JS only, no UI
- `"form"` — QML with UI
- `"composite"` — both

### Install Paths
- Bundled: `<install_dir>/extensions/`
- User: `C:\Users\<user>\AppData\Local\Audacity\Audacity4\extensions\`
- Packaged as `.mext` (zip with manifest.json)

### Module System
CommonJS-style `require()` / `exports` / `module` available.

---

## 4. VST3 Support (Full Backend — UI Not Wired Yet in Alpha)

### Effect ID Format
```
Effect_Audacity_Audacity_<SymbolName>_Built-in Effect: <SymbolName>
```

### VST3 Plugin ID Format
```
Effect_<Family>_<Vendor>_<Symbol>_<Path>
```

### Scan Paths
- Windows: `%PROGRAMFILES%\Common Files\VST3\`
- macOS: `~/Library/Audio/Plug-ins/VST3/`, `/Library/Audio/Plug-ins/VST3/`
- Linux: `~/.vst3/`, `/usr/lib/vst3/`, `/usr/local/lib/vst3/`

### Programmatic Parameter Control
```cpp
// Read all parameters
ParameterInfoList parameters(EffectInstanceId instanceId);

// ParameterInfo contains:
// - id, name, units ("dB", "Hz", "%")
// - type (Toggle, Dropdown, Slider, Numeric, ReadOnly)
// - minValue, maxValue, defaultValue, currentValue
// - currentValueString ("440 Hz", "-3.5 dB")
// - stepCount, enumValues, isLogarithmic, canAutomate

// Set parameter
bool setParameterValue(EffectInstanceId, parameterId, double value);

// Apply effect without UI dialog
DoEffect(pluginID, project, EffectManager::kConfigured);
```

### Realtime Effects Chain
```cpp
// Add VST to track (trackId = -2 for master bus)
addRealtimeEffect(trackId, effectId);
removeRealtimeEffect(trackId, state);
replaceRealtimeEffect(trackId, effectListIndex, newEffectId);
moveRealtimeEffect(state, newIndex);
setIsActive(state, active);
```

### Preset System
```cpp
// Factory presets
PresetIdList factoryPresets(effectId);
// User presets
PresetIdList userPresets(effectId);
// Apply/save/import/export
applyPreset(instanceId, presetId);
saveCurrentAsPreset(instanceId, presetName);
importPreset(instanceId, filePath);
exportPreset(instanceId, filePath);
```

### Builtin Effect Symbols
Amplify, Bass and Treble, Change Pitch, Change Speed, Change Tempo,
Chirp, Click removal, Compressor, Distortion, DTMF Tones, Echo,
Equalization, Fade In, Fade Out, Find Clipping, Graphic EQ, Invert,
Limiter, Noise, Noise Reduction, Normalize, Normalize Loudness,
Paulstretch, Phaser, Repair, Repeat, Reverse, Reverb, Silence,
Sliding Stretch, Stereo To Mono, Tone, Truncate silence, Wahwah,
Auto Duck

---

## 5. WebSocket API (If Compiled)

Default OFF: `MUSE_MODULE_NETWORK_WEBSOCKET=OFF` in CMake.

### Server API (available to extensions)
```javascript
var server = api.websocketserver;
server.listen(8765, function(clientId) {
    server.onMessage(clientId, function(message) {
        var data = JSON.parse(message);
        server.send(clientId, JSON.stringify({ result: "ok" }));
    });
});
```

### Client API
```javascript
var ws = api.websocket;
ws.open(8084, function(socketId) {
    ws.onMessage(socketId, function(message) { ... });
    ws.send(socketId, JSON.stringify({ ... }));
});
```

- Text messages only (no binary)
- No protocol defined — raw strings, parse your own JSON
- Server name: `"muse_extension"`
- Client IDs start at 2001

---

## 6. IPC Mechanisms Found

| Mechanism | Purpose | External Access |
|-----------|---------|:---:|
| QLocalServer/Socket | Multi-window coordination | No |
| QTcpServer (OAuth) | Cloud sign-in redirect capture | No |
| WebSocket (extension API) | Plugin networking | Yes (if compiled) |
| mod-script-pipe | GONE in v4 | N/A |

---

## 7. Bridge Architecture (Planned)

### Target: Extension with WebSocket + Dispatcher
Requires two changes to build from source:
1. `MUSE_MODULE_NETWORK_WEBSOCKET=ON` in CMake
2. Uncomment `api.dispatcher` in `muse_framework/framework/extensions/api/extapi.h`

```
┌─────────────────────┐     WebSocket      ┌──────────────────┐
│  AudacityMCP Server │ ◄────────────────► │  Audacity 4      │
│  (Python/FastMCP)   │    localhost:8765   │  Extension        │
│  99+ tools          │                     │  (bridge.js)     │
└─────────────────────┘                     │  ↓               │
                                            │  dispatcher()    │
                                            │  → 200+ actions  │
                                            │  → VST3 control  │
                                            └──────────────────┘
```

### Source Files to Modify
- `muse_framework/framework/extensions/api/extapi.h` — uncomment dispatcher property
- `CMakeLists.txt` or build config — set `MUSE_MODULE_NETWORK_WEBSOCKET=ON`
- Create extension: `manifest.json` + `bridge.js`

---

## 8. Key Source File Locations

```
audacity/
├── src/
│   ├── appshell/internal/applicationuiactions.cpp    — app actions
│   ├── playback/internal/playbackuiactions.cpp       — transport
│   ├── record/internal/recorduiactions.cpp           — recording
│   ├── trackedit/internal/trackedituiactions.cpp      — editing (biggest)
│   ├── project/internal/projectuiactions.cpp          — file/menu
│   ├── projectscene/internal/projectsceneuiactions.cpp — view/tools
│   ├── effects/
│   │   ├── effects_base/internal/effectsuiactions.cpp — effect actions
│   │   ├── effects_base/ieffectparametersprovider.h   — param API
│   │   ├── builtin_collection/                        — builtin effects
│   │   └── vst/internal/vstparameterextractorservice.* — VST param bridge
│   └── au3cloud/                                      — cloud/OAuth
├── au3/
│   ├── libraries/au3-vst3/                           — VST3 host engine
│   └── libraries/au3-builtin-effects/                — legacy effects
└── muse_framework/
    └── framework/
        ├── autobot/internal/api/                     — autobot JS API
        ├── extensions/                               — plugin system
        │   ├── api/extapi.h                          — extension API (MODIFY THIS)
        │   └── internal/extensionsloader.cpp         — manifest parser
        ├── network/api/
        │   ├── websocketserverapi.*                  — WS server
        │   └── websocketapi.*                        — WS client
        ├── actions/
        │   ├── iactionsdispatcher.h                  — dispatcher interface
        │   └── actiontypes.h                         — ActionData, ActionQuery
        └── vst/internal/                             — VST host framework
```
