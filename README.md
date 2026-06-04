# Tony Stark Hand Control

> Multi-camera hand-tracking + 3D room mapping for PC control (Tony Stark HUD style).

A local-first, GPU-accelerated hand-tracking system that uses one or more cameras to detect hand gestures, reconstructs the hand in 3D space, and drives your PC via **accessibility navigation** (Tab/Shift+Tab/Arrow) — not mouse emulation. Built for users who want hands-on control without touching the keyboard or mouse.

![architecture](docs/images/architecture.svg)

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
| **Local-only** | Everything runs on your CPU/GPU. No cloud, no telemetry, no API keys required |

## Quick start (Windows)

```cmd
git clone https://github.com/Capslockb/tony-stark-hand-control.git
cd tony-stark-hand-control
python install_wizard.py
start_windows.bat
```

The install wizard will:
1. Verify Python ≥ 3.10
2. Install dependencies from `requirements.txt`
3. Download the MediaPipe hand-landmark model (`hand_landmarker.task`, ~7 MB)
4. Create a desktop shortcut
5. Launch the app

## Quick start (Linux / WSL)

```bash
git clone https://github.com/Capslockb/tony-stark-hand-control.git
cd tony-stark-hand-control
python3 install_wizard.py
python3 tony_stark_hud_control.py
```

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
   - **Thumb to ring** → scroll up
   - **Thumb to pinky** → scroll down
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
python -m unittest discover tests
```

The test suite covers: RoomMap, HandProcessor, CameraManager, StereoCalibrator, triangulate_point_rays, OllamaGestureRecognizer circuit breaker, and full HandControlApp construction. Current status: **77/77 passing**.

## Contributing

This is a personal project, but PRs are welcome. See `CONTRIBUTING.md` for the workflow.

## License

MIT — see `LICENSE`.

## Privacy

The app is **100% local**. No network calls are made by the hand-tracking pipeline. The optional Ollama tab can be configured to use a cloud endpoint, but it is **off by default** and requires explicit user configuration. See `SECURITY.md` for the full disclosure policy.
