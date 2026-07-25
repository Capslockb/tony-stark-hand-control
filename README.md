# Tony Stark Hand Control

**Multi-camera, GPU-friendly hand tracking for PC control — in the spirit of the Iron Man HUD.**

A local-first, accessibility-focused hand-tracking system. Point one (or up to four) webcams at yourself, hold up an open palm, and your hand becomes a controller — swipes drive keyboard navigation, thumb-to-finger taps become clicks, and the whole rig reconstructs your hand in 3D space. The core hand-tracking pipeline runs locally with no telemetry; optional Ollama cloud inference is off by default. No mouse required.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB.svg)](https://www.python.org)
[![Platform: Windows primary](https://img.shields.io/badge/platform-Windows%20primary-999)](#quick-start)
[![Privacy: local-first](https://img.shields.io/badge/privacy-local--first-success)](#privacy)
[![CI](https://github.com/Capslockb/tony-stark-hand-control/actions/workflows/ci.yml/badge.svg)](https://github.com/Capslockb/tony-stark-hand-control/actions/workflows/ci.yml)

> 🌐 **Live site:** [**capslockb.github.io/tony-stark-hand-control**](https://capslockb.github.io/tony-stark-hand-control/) — install in 60 seconds, no clone required.
> 📱 **On your phone?** Open the mobile install page: [**capslockb.github.io/tony-stark-hand-control/mobile**](https://capslockb.github.io/tony-stark-hand-control/mobile/)

<p align="center">
  <img src="docs/images/architecture.svg" alt="Architecture overview" width="720">
</p>

---

## Why this exists

Most webcam hand-tracking demos do **mouse emulation** — they hand you a virtual mouse and call it a day. That's broken for real use: clicking the wrong thing is one pixel of slop away, every menu fights you, and the cursor is always exactly where you don't want it.

Tony Stark Hand Control takes a different approach: **accessibility navigation**. Swipes send `Tab` / `Shift+Tab` / `↑` / `↓`, thumb-touches fire `Enter` and the context-menu key, and a **persistent green border** tracks the focused UI element so you always know what will activate. It's the same paradigm every operating system already uses for keyboard navigation — we just drive it with a hand.

For the people who want a mouse anyway, screen-cursor mode is one checkbox away. For the people who want to **see** what their hand is doing in 3D space, the Room tab triangulates your fingertips across cameras and renders them in a live matplotlib viewport with anchored walls, zones, and hotspots.

---

## Features

| | |
|---|---|
| **Multi-camera fusion** | Auto-detects up to 4 cameras (DSHOW → MSMF → ANY), runs MediaPipe on each in parallel |
| **3D room mapping** | Interactive matplotlib 3D viewport with camera frustums, live hand tracking, and click-to-place anchors (wall / zone / hotspot / furniture / custom) |
| **1:1 hand tracking** | Async MediaPipe worker thread + One-Euro filter + velocity-based predictor for sub-frame latency |
| **Accessibility-first** | Swipes send Tab / Shift+Tab / Arrow keys, palm-hold engages, thumb+index clicks. **No mouse required.** |
| **Persistent selection overlay** | Green border tracks the currently-focused UI element at 10 Hz so you always know what will activate |
| **Engage / disengage** | Open palm held ~0.6 s = engaged (cursor / click enabled). Lower hand = disengaged (system idle) |
| **Live performance readout** | Per-loop ms, target FPS, app CPU%, RAM, thread count, all on the Main tab |
| **Single-instance lock** | One app at a time. Second launch focuses the existing window instead of stuttering |
| **Local-first core** | Camera capture, MediaPipe tracking, gesture detection, and PC-control actions run locally with no telemetry |
| **Optional LLM gestures** | Drop in Ollama (cloud or local llama.cpp) to add custom gestures the local detector doesn't know. Off by default. |
| **Platform status** | Windows is the primary tested path; Linux and macOS parity remain roadmap work |

---

## Quick start

**Option A — install from source**:
```cmd
git clone https://github.com/Capslockb/tony-stark-hand-control.git
cd tony-stark-hand-control
python install_wizard.py
start_windows.bat
```

**Option B — download the prebuilt .exe** (easiest, no Python needed):
1. Go to https://github.com/Capslockb/tony-stark-hand-control/releases/latest
2. Download `tony_stark_hud_control.exe`
3. Double-click to run. The app will download the MediaPipe model on first launch.

**Option C — experimental Linux prebuilt** (x86_64):
```bash
# Download from releases page
tar -xzf tony_stark_hud_control-linux-x86_64.tar.gz
./tony_stark_hud_control.sh
```

The Linux package is provided for evaluation, not as a feature-parity claim. Focus discovery and the persistent selection overlay still require platform-specific work tracked in the roadmap.

The install wizard will:
1. Verify Python ≥ 3.10
2. Install dependencies from `requirements.txt`
3. Download the MediaPipe hand-landmark model (`hand_landmarker.task`, ~7 MB)
4. Create a desktop shortcut
5. Launch the app

## Experimental source install (native Linux)

```bash
git clone https://github.com/Capslockb/tony-stark-hand-control.git
cd tony-stark-hand-control
python3 install_wizard.py
python3 tony_stark_hud_control.py
```

This is a source-install path, not a claim of feature parity with Windows. WSL is not equivalent to a native Linux desktop for this camera-and-GUI application; use the native Windows build unless you have deliberately configured GUI and webcam forwarding.

---

## Usage

1. **Start the app** — GUI window opens with the camera feeds on the right and controls on the left.
2. **Press `Start`** — cameras are detected, feeds appear, MediaPipe starts running.
3. **Engage**: hold an **open palm** toward any camera for ~0.6 seconds. The status indicator changes from "Disengaged" to "Engaged".
4. **Navigate**:
   - **Swipe right** → `Tab` (next focusable element)
   - **Swipe left** → `Shift+Tab` (previous)
   - **Swipe up** → `↑`
   - **Swipe down** → `↓`
   - **Thumb to index** → `Enter` (activate focused element)
   - **Thumb to middle** → right-click / context menu
   - **Thumb to ring** → `↑`
   - **Thumb to pinky** → `↓`
5. **Disengage** by lowering your hand out of the frame.

The **persistent green selection border** always shows which UI element is currently focused.

## Configuration

All configuration lives in the GUI tabs:

- **Main** — Start/Stop/Calibrate, per-camera enable, performance readouts
- **Ollama** — optional cloud or local LLM gesture recognition (advanced, see `docs/ollama_integration.md`)
- **Tracking** — Responsiveness preset (1=smooth … 5=1:1), Fast Mode (240p pre-downscale), One-Euro filter params
- **Accessibility** — Navigation mode (Tab vs Arrow), selection overlay settings
- **3D / Room** — Interactive 3D viewport, click to place anchors, save/load room map
- **Cameras** — Per-camera list with Test buttons and live-feed status

## Documentation

- **[Installation](docs/installation.md)** — detailed setup, dependencies, troubleshooting
- **[Calibration](docs/calibration.md)** — how to print the checkerboard, run the calibration, and what the reprojection error means
- **[Gestures](docs/gestures.md)** — full gesture reference with diagrams
- **[3D Room Mapping](docs/3d_room_mapping.md)** — building a map of your room for the live hand tracker
- **[Performance tuning](docs/performance.md)** — what each slider does, how to trade quality for speed
- **[Troubleshooting](docs/troubleshooting.md)** — common issues and how to fix them
- **[Architecture](docs/architecture.md)** — how the pieces fit together
- **[Ollama integration](docs/ollama_integration.md)** — adding optional cloud / local LLM gesture recognition

---

## Performance

On a RTX 5060 (Blackwell, sm_120) + Ryzen 7 5700X with 4 cameras at 480×360 / 30 fps:

| Stage | Cost | Notes |
|---|---|---|
| MediaPipe per inference | ~30 ms | CPU (XNNPACK); GPU delegate unavailable on this Windows build |
| One-Euro filter + predictor | 0.1 ms per tip | Cached buffer, 6-frame history |
| HUD overlay (4 cams) | 24 ms/sec = 2.4% of one core | Static base cached, only animated parts redrawn |
| Total main loop | 28-35 ms ≈ 28-35 fps | Adaptive pacing to fastest live camera |

See `docs/performance.md` for the full benchmark.

## Tests

```bash
python -m unittest discover tests -v
```

The suite covers RoomMap, HandProcessor, CameraManager, StereoCalibrator, `triangulate_point_rays`, Ollama gesture recognition, application construction, and focused regression and benchmark modules. The original core audit contains 77 assertions, but repository-wide discovery includes additional modules and its total can change.

Treat the command's final summary and the GitHub Actions run for the exact commit as the source of truth. The current CI matrix is failing and is tracked in [Issue #3](https://github.com/Capslockb/tony-stark-hand-control/issues/3); a fixed passing count should not be claimed until an exact-head run is green.

---

## What's coming next

A real roadmap of public features is in [`ROADMAP.md`](ROADMAP.md). Highlights:

- **v1.1.0 (Q3 2026)** — two-hand tracking, Linux & macOS focus-overlay parity, bundled-model installer, per-gesture hooks, CLI flags
- **v1.2.0 (Q4 2026)** — monocular depth from MediaPipe z, phone-as-second-camera companion app, room-map gesture zoning
- **v2.0.0 (Q1 2027)** — "OK Jarvis" wake word, sign-language dictionary, third-party plugin SDK

These are publicly promised, not "maybe someday" bullet points. The roadmap is binding intent. If something moves, the doc updates.

---

## Contributing

PRs are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the workflow. Code style: PEP 8, 4-space indent, snake_case functions, PascalCase classes, docstrings on public methods, Conventional Commits for messages.

## License

MIT — see [`LICENSE`](LICENSE).

## Privacy

The core camera, MediaPipe, gesture-detection, and PC-control pipeline runs locally and sends no telemetry. The optional Ollama feature can be configured to send camera-frame snapshots and prompts to a remote endpoint; it is off by default. Review the endpoint provider's current retention policy before enabling cloud inference. Do not reuse the exposed credential-like default tracked in [Issue #5](https://github.com/Capslockb/tony-stark-hand-control/issues/5). See `SECURITY.md` for the disclosure policy.

## Acknowledgments

- [MediaPipe](https://developers.google.com/mediapipe) for the HandLandmarker model
- [One-Euro Filter](https://cristal.univ-lille.fr/~casiez/1euro/) by Casiez et al.
- The open-source accessibility community, which built every keyboard-navigation pattern this app leans on
