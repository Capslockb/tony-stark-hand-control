# Architecture

How the pieces of the Tony Stark Hand Control app fit together.

![architecture](images/architecture.svg)

## Top-level structure

```
tony_stark_hud_control.py
├── Constants & helpers
├── RoomMap                 (3D anchor list, JSON persistence)
├── OllamaGestureRecognizer (optional LLM, with circuit breaker)
├── CameraManager           (multi-cam probe, live-feed check, release)
├── HandProcessor           (MediaPipe worker, smoothing, predictor)
├── triangulate_point_rays  (ray-based 3D triangulation)
├── StereoCalibrator        (Phase A intrinsics + Phase B shared extrinsics)
└── HandControlApp          (Tkinter GUI, 6 tabs, main loop, selection overlay)
```

Plus:
- `install_wizard.py` — pre-flight check + dependency install
- `start_windows.bat` — Windows launcher
- `tests/test_app.py` — 77-test regression suite
- `docs/` — user documentation
- `hermes-skills/` — associated Hermes Agent skills
- `.github/workflows/` — CI + release automation

## Subsystem details

### CameraManager

Wraps `cv2.VideoCapture` for one or more cameras. On construction:

1. Probes indices 0-3 with three backends: DSHOW, MSMF, ANY.
2. For each (index, backend), opens the camera, sets resolution and FPS, reads 3 frames, and keeps it if the last frame is "live" (not black/uniform).
3. Returns the list of opened cameras. Each is a `cv2.VideoCapture` instance.

`is_feed_live()` checks std-dev and mean brightness of a BGR frame. Cached at 10 Hz by the main loop to avoid per-frame work.

`release()` is idempotent — safe to call multiple times. Closes all camera handles and clears the list.

### HandProcessor

This is the heart of the app. It runs MediaPipe in a **background worker thread** so the GUI never blocks on inference.

#### Async worker

The worker thread is started in `__init__`. It maintains:
- `_infer_queue`: maxlen=1 queue of (frame, timestamp_ms) submissions
- `_result_lock`: guards `_last_result` (the latest HandLandmarkerResult)
- `_last_result`: the most recent result, available to the main thread without blocking

`detect(frame)` is the public API. It submits the frame to the queue (non-blocking) and returns the cached `_last_result` immediately. The next call to `detect()` may or may not have a new result, depending on inference speed.

The worker is a daemon thread — it dies when the process exits, no cleanup needed.

#### Smoothing

For each of the 5 fingertips (thumb, index, middle, ring, pinky), `smooth()` runs:

1. **One-Euro filter** on the normalized (x, y) coordinates. The filter has a cutoff frequency that adapts to the speed of the signal: low when at rest (smooth), high when moving (responsive).
2. **Moving average** over a buffer of recent filtered values (default 6 frames).
3. **Velocity update** — the per-tip velocity is computed from the last 3 filtered values. Units: normalized units per second.

The result is stored in `self.filtered[tip_id]` (the current filtered position), `self.buffers[tip_id]` (the history), and `self.velocities[tip_id]` (the current velocity).

#### Predictor

`predict(tip_id, now=None)` returns the current best estimate of where the tip is right now, given the latest detection and the recent velocity.

The predictor takes the most recent filtered position and extrapolates forward by `predict_max_dt` seconds (default 0.15s), with a quadratic decay to prevent overshoot when the hand stops:

```
dt = min(now - last_filtered_ts, predict_max_dt)
if dt > 0 and velocity is known:
    horizon = predict_max_dt
    decay = max(0, 1 - (dt / horizon)^2)
    predicted = filtered + velocity * dt * decay
else:
    predicted = filtered
```

If the tip has never been seen (`predict()` called before any `smooth()`), the predictor returns `None`. The caller falls back to the raw MediaPipe landmark.

#### Engage / palm-open

`is_palm_open(landmarks)` checks if 3 or more of the 4 non-thumb fingers are clearly extended. Uses a **wrist-relative distance** check (not a Y-axis comparison) so it works on mirrored (selfie) cameras:

```
for each non-thumb finger:
    distance(tip, wrist) > distance(pip, wrist) + threshold
```

A finger is extended if its tip is further from the wrist than its PIP joint is. The threshold is 0.05 normalized units. Count of extended >= 3 → palm is open.

### triangulate_point_rays

Pure function. Takes a list of camera origins and unit rays (in a SHARED world frame) and returns the 3D point that is closest to all rays.

Builds the over-determined linear system:

```
[ray_i]_x * X = [ray_i]_x * origin_i
```

and solves with `np.linalg.lstsq`. Returns `None` if the rays are parallel (rank < 3).

### StereoCalibrator

Two-phase calibration. Saves to `calibration.npz`.

**Phase A (per-camera intrinsics)**:
- For each camera, capture N views of the checkerboard (different positions, angles, distances)
- Run `cv2.calibrateCamera` on each camera independently to get `K`, `dist`, and per-frame `rvec`, `tvec`

**Phase B (shared extrinsics)**:
- For each pair of cameras, run `cv2.stereoCalibrate` with the corresponding image points
- This gives a single shared world frame with camera 0 at the origin (R=I, t=0)
- All other cameras' R, t are in this shared frame

**Projection matrices**:
- For each camera, `P = K @ [R | t]` (3x4)
- These are saved to `calibration.npz` for later use in 3D reconstruction

**3D reconstruction**:
For each 2D landmark `(x, y)` in camera `i`:

1. **Undistort**: `(x', y') = cv2.undistortPoints((x, y), K_i, dist_i)`
2. **Normalize**: `(xn, yn) = K_i^-1 @ (x', y', 1)` — unit ray in camera frame
3. **World ray**: `ray_world = R_i^T @ (xn, yn, 1)` — same ray in world frame
4. **Camera origin in world**: `O_i = -R_i^T @ t_i`

Then `triangulate_point_rays(origins, rays)` returns the 3D point.

**Reprojection error**:
After reconstructing, reproject each 3D point back to each camera and measure the distance to the original 2D landmark. The mean (in pixels) is the calibration quality metric. < 1 px is good, < 0.5 px is excellent.

### HandControlApp

The Tkinter GUI. Six tabs:

1. **Main** — Start/Stop/Calibrate, per-camera enable, status, performance readouts
2. **Ollama** — optional cloud or local LLM gesture recognition
3. **Tracking** — Responsiveness preset, One-Euro params, Fast Mode, MediaPipe skip
4. **Accessibility** — Navigation mode (Tab vs Arrow), selection overlay
5. **3D / Room** — interactive matplotlib 3D viewport
6. **Cameras** — per-camera list with Test buttons

The main loop runs at the fastest live camera's FPS. Each iteration:
1. Reads frames from all enabled cameras
2. Updates cached live-feed status (every 10th frame)
3. Updates cached FPS (every 30th frame)
4. Submits frames to the HandProcessor worker (every Nth frame, configurable)
5. Draws the HUD on each camera's display
6. Stitches together a multi-cam aggregate decision for engage/disengage
7. Fires gestures if engaged

The selection overlay refreshes at 10 Hz via `root.after(100, ...)`. It uses `win32gui.GetGUIThreadInfo` to find the focused UI element and draws a green border around it.

The 3D / Room tab uses `matplotlib.backends.backend_tkagg.FigureCanvasTkAgg` to embed a 3D matplotlib viewport. Click events are unprojected to 3D world rays and intersected with a horizontal plane to place anchors.

### Single-instance lock

A `_SingleInstance` class ensures only one copy of the app runs at a time. Two layers:

1. **Windows named mutex** (`Global\TonyStarkHandControl_v1`) — kernel-level, robust
2. **File lock** on `%TEMP%\tony_stark_hud.lock` using `msvcrt.locking` — belt and suspenders

The lock is acquired BEFORE importing tkinter or cv2 (so a second launch is fast even if the first is fully loaded).

On conflict, the second launch enumerates top-level windows looking for one with "Tony Stark" or "Hand Control" in the title, and calls `SetForegroundWindow` to bring it to the front. If no window is found, a tkinter message box says "already running."

On `WM_DELETE_WINDOW` (user clicks X), the lock is released. Also in a `finally:` block for crash safety.

## Data flow

```
cameras (1-4)
  → CameraManager.read_all()
  → (caching: live check every 10th frame, FPS every 30th)
  → HandProcessor.detect(frame)  [non-blocking, returns cached result]
  → hand landmarks (21 points per hand)
  → (per-tip smoothing, velocity, predictor)
  → engagement check (is_palm_open averaged over ring buffer)
  → (if engaged) gesture detection (thumb-finger distance, swipe velocity)
  → keyboard / mouse events (via pyautogui or ctypes for accessibility)
  → HUD overlay on each camera display
  → 3D / Room tab: triangulated 3D position of all 5 fingertips
  → selection overlay: 10 Hz refresh of focused UI element border
```

## Performance characteristics

On a RTX 5060 (Blackwell, sm_120) + Ryzen 7 5700X with 4 cameras at 480x360 / 30 fps:

| Stage | Cost | Notes |
|---|---|---|
| CameraManager.read_all | ~10 ms | 4 × cv2.VideoCapture.read with small buffer |
| HandProcessor.detect | <1 ms (returns cached) | Real MediaPipe cost is ~30 ms on the worker |
| is_palm_open | <0.1 ms | 4 × math.hypot |
| Gesture detection (when engaged) | ~0.5 ms | 4 × math.hypot + 4 × ring buffer ops |
| HUD overlay per cam | 0.2 ms | Static base cached, np.maximum blit |
| 3D reconstruction (5 tips × N cams) | ~5 ms | 5 × undistort + K^-1 + R^T + triangulate |
| Canvas redraw | 15 ms throttled | Tk Canvas + ImageTk.PhotoImage |
| 3D view redraw | throttled to 5 Hz | matplotlib |
| Selection overlay refresh | <1 ms at 10 Hz | win32 GetGUIThreadInfo + Toplevel.move |

Total main loop: **28-35 ms ≈ 28-35 fps** on a typical desktop. CPU usage: **3-5% of one core** with 4 cameras.

## See also

- [Performance tuning](performance.md) — what the GUI knobs do
- [Calibration](calibration.md) — the calibration procedure
- [Gestures](gestures.md) — what each gesture does
- The 7 audit passes in `hermes-skills/tony-stark-hand-control/references/`
