# Roadmap

This is a public commitment to where Tony Stark Hand Control is going. Items are scoped, dated, and tied to a real milestone. If priorities change, this document updates and the commit trail shows the diff.

> **Status legend:** 🔒 in progress · 🎯 next · 💭 considering

---

## v1.1.0 — UX polish & platform parity

**Target: Q3 2026**

### 🎯 Two-hand tracking
Right now the app supports one hand. MediaPipe can return up to two. The work is plumbing: two parallel smoothing pipelines, two gesture channels, and a "primary hand" arbitration rule (rightmost by default, configurable).

### 🎯 Linux & macOS parity
The Windows path is the one that's been beaten on. Linux needs an equivalent of the GetGUIThreadInfo-based selection overlay (`xdotool`, then a different `WS_EX_LAYERED` equivalent). macOS needs the AXUIElement bridge for focus tracking. Both have working prototypes in `hermes-skills/tony-stark-hand-control/references/` — they need to be promoted to first-class.

### 🎯 Bundled-model installer
The `hand_landmarker.task` (~7 MB) is downloaded on first run. For users who want a single `.exe` with no network at all, the install wizard should embed the model. PyInstaller `--add-data` already covers the mechanics.

### 🎯 Per-gesture hook system
Users want to fire shell commands, HTTP requests, or Python callbacks when a specific gesture fires. The architecture is: a hook table in `gesture_hooks.json` next to `room_map.json`, evaluated on each confirmed gesture. No code change to enable — just a JSON file.

### 🎯 Command-line launch flags
`--calibrate`, `--engaged-on-start`, `--no-overlay`, `--camera-index N`. Useful for power users and for headless test rigs.

---

## v1.2.0 — Smart depth

**Target: Q4 2026**

### 🎯 Monocular depth from MediaPipe z
MediaPipe's hand-landmark `z` is already a relative depth estimate. Combine it with the known camera intrinsics and you get a usable 3D position from a **single** camera — no calibration rig required. The accuracy won't match a stereo rig, but it'll let people try the 3D Room tab with their laptop webcam.

### 🎯 Stereo depth from a phone-as-second-camera
Companion app: install on a phone, point at the same scene, stream over the local network as a virtual camera index. This collapses the "I don't have four webcams" objection.

### 🎯 Room-map-driven gesture zoning
Once you have a calibrated 3D room, gestures can be **scoped** to zones. A swipe in the kitchen zone opens the kitchen lights (via Home Assistant). A pinch in the desk zone unmutes the mic. The Room Map already supports the data model; v1.2 wires it to the action layer.

---

## v2.0.0 — Voice + vision

**Target: Q1 2027**

### 🎯 "OK Jarvis" wake word
A lightweight on-device wake-word detector (open-source Porcupine or similar) listens while the app is engaged. On detection, the app opens a microphone channel. "Open Spotify", "next track", "lights off" — sent to a configurable local LLM (Ollama or llama.cpp) for intent extraction.

### 🎯 Sign-language dictionary
The MediaPipe hand-landmark pipeline is already sign-language ready. The work is gesture vocabulary: define the 50 most common ASL letters and words, train a small on-device classifier, expose them as new gestures.

### 🎯 Plugin SDK
External Python packages can register new gesture types, new calibration procedures, and new 3D-room anchor types. Discoverable via a `tony_stark_hand_control.plugins` entry point. Third-party plugins can ship on PyPI.

---

## Considering (not committed)

These are real ideas, not vapor. None of them have a milestone yet because they need design work or external dependencies. Listed here so the community can vote.

- 💭 **Native mobile remote controls** beyond the committed phone-as-second-camera workflow
- 💭 **Webcam-only calibration** using AR markers in the scene (no printed checkerboard)
- 💭 **Head-tracking companion mode** — use face landmarkers to drive a head-tracked mouse for accessibility
- 💭 **Cloud calibration sync** (opt-in, end-to-end encrypted) so users with identical rigs can share `calibration.npz`
- 💭 **Steam Deck / handheld PC support** — the GUI is too big; need a compact layout
- 💭 **OBS / streaming integration** — overlay the HUD on a virtual camera for content creators
- 💭 **Wayland native support** (currently the focus overlay uses X11 / Win32 APIs)

---

## How this doc is maintained

- New features start under **Considering**
- When committed, they move to a versioned milestone with a target quarter
- When shipped, the entry is deleted from this file and added to `CHANGELOG.md` with a link back to the roadmap entry it came from
- If a feature is dropped, the entry stays in the changelog with a "withdrawn" note — no silent removal
- The roadmap is reviewed at every minor release

## Want to influence the roadmap?

Open a GitHub Discussion in the **Ideas** category. The most-upvoted ideas in the last 90 days get prioritized into the next milestone planning pass.

## Want to build one of these?

PRs against any roadmap item are welcome. Open an issue first to claim the slot so two people don't end up duplicating work.
