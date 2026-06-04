# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-06-04

### Added
- **Initial public release**
- Multi-camera hand-tracking (1-4 cameras, DSHOW/MSMF/AUTO backends)
- Async MediaPipe worker thread (non-blocking detect(), <1 ms call time)
- One-Euro filter + velocity-based predictor for 1:1 hand tracking
- 3D triangulation from multi-camera rig (Phase A intrinsics + Phase B shared extrinsics)
- 3D / Room tab: interactive matplotlib viewport, camera frustums, click-to-place anchors (wall/zone/hotspot/furniture/custom), save/load to `room_map.json`
- Accessibility navigation: swipes → Tab/Shift+Tab/Arrow keys, thumb+index = Enter, etc.
- Persistent green selection border tracking the focused UI element at 10 Hz (Win32 GetGUIThreadInfo)
- Engage gesture: open palm held ~0.6 s
- Per-cam enable/disable with live-feed check (auto-blacklist frozen/black feeds)
- Fast Mode: 240p pre-downscale for ~30% faster MediaPipe inference
- 5-tab Tkinter GUI: Main / Ollama / Tracking / Accessibility / 3D / Cameras
- Live performance readout: per-loop ms, target FPS, app CPU%, RAM, thread count
- Single-instance lock: Win32 named mutex + msvcrt file lock; duplicate launch focuses existing window
- Async GUI startup: camera probe runs on a background thread (no Start-button freeze)
- MSMF warm-up fix: read 5 frames, accept on last live frame
- OpenCV OPEN/READ timeouts: cap probe time at ~1.5 s per index
- HUD base cache: static overlay rendered once per unique frame size, blitted with np.maximum
- Per-cam enable state cached as a Python list (skips 120 Tcl bridge calls/sec at 4 cams)
- Ollama circuit breaker: 3 failures → 30 s cooldown
- 77-test regression suite covering all subsystems
- Comprehensive documentation in `docs/`: install, calibration, gestures, 3D room, performance, troubleshooting, architecture
- Install wizard (`install_wizard.py`) and Windows launcher (`start_windows.bat`)
- GitHub Actions CI: pytest on every push, release.yml auto-builds the .exe on tag
- Associated Hermes skills in `hermes-skills/tony-stark-hand-control/`

### Security
- App is 100% local. No telemetry, no cloud calls in the hand-tracking pipeline.
- Optional Ollama cloud endpoint is off by default.
- No secrets in repo (`.env`, tokens, calibration.npz all gitignored)

### Known limitations
- MediaPipe GPU delegate is unavailable on this Windows build (the `GPU processing is disabled in build flags` message). Inference runs on CPU via XNNPACK.
- Local `llama.cpp` is broken on RTX 5060 (Blackwell sm_120) for multimodal models — see `docs/ollama_integration.md` for the workaround.
- Y-flip on selfie cameras: handled (wrist-relative distance check).
- 3D reconstruction needs ≥2 cameras calibrated.
