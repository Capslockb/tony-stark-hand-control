# Architecture

How the pieces of the Tony Stark Hand Control app fit together.

![architecture](images/architecture.svg)

> **3D validation status:** Manual room anchors and JSON persistence are available, but live stereo reconstruction is experimental. Calibration stores OpenCV world-to-camera `R, t`; the current reconstruction path interprets `t` as a camera center, and one helper also mixes normalized landmarks with a pixel-coordinate API. Until [Issue #6](https://github.com/Capslockb/tony-stark-hand-control/issues/6) is corrected and validated end to end, do not use live 3D coordinates for measurement, automation, or safety decisions.
>
> **Main-loop status:** The flow described below is the intended design, not the behavior of the current `main` branch. The adaptive pacing and next-iteration scheduling block is misplaced inside `_redraw_canvas()`, after its normal return path, so Start currently processes one iteration and does not schedule the next. See [Issue #16](https://github.com/Capslockb/tony-stark-hand-control/issues/16).

## Top-level structure

```
tony_stark_hud_control.py
├── Constants & helpers
├── RoomMap                 (3D anchor list, JSON persistence)
├── OllamaGestureRecognizer (optional fixed-vocabulary snapshot classifier)
├── CameraManager           (multi-cam probe, live-feed check, release)
├── HandProcessor           (MediaPipe worker, smoothing, predictor)
├── triangulate_point_rays  (ray-based 3D triangulation)
├── StereoCalibrator        (Phase A intrinsics + Phase B shared extrinsics)
└── HandControlApp          (Tkinter GUI, 6 tabs, main loop, selection overlay)
```

Plus:
- `install_wizard.py` — pre-flight check + dependency install
- `start_windows.bat` — Windows launcher
- `tests/test_app.py` — core regression audit; repository-wide discovery includes additional modules
- `docs/` — user documentation
- `hermes-skills/` — associated Hermes Agent skills
- `.github/workflows/` — CI + release automation

## Subsystem details

### CameraManager

Wraps `cv2.VideoCapture` for one or more cameras. On construction:

1. Probes indices 0-3 with three backends: DSHOW, MSMF, ANY.
2. For each (index, backend), opens the camera, sets resolution and FPS, reads 3 frames, and keeps it if at least one of those frames passes the live-feed check.
3. Returns the list of opened cameras. Each is a `cv2.VideoCapture` instance.

`is_feed_live()` checks std-dev and mean brightness of a BGR frame. The main loop refreshes the cached result every 10th iteration, so the effective check rate follows the loop rate rather than a fixed 10 Hz timer.

`release()` is idempotent — safe to call multiple times. Closes all camera handles and clears the list.

### HandProcessor

This is the heart of the app. It runs MediaPipe in a **background worker thread** so the GUI does not wait for inference to finish.

#### Async worker

The worker thread is started in `__init__`. It maintains:
- `_infer_q`: a `queue.Queue(maxsize=2)` carrying preprocessed RGB frames and millisecond timestamps
- `_inference_pending`: a submission gate that prevents another request while the current request is outstanding
- `_result_lock`: guards `_last_result` (the latest `HandLandmarkerResult`)
- `_last_result`: the most recent completed result, available to the main thread without waiting

`detect(frame)` is the public API. When no request is pending, it preprocesses and enqueues the frame, then returns the cached `_last_result` immediately. While a request remains pending, later calls return the same cached result without submitting another frame. The next completed result is therefore not guaranteed to correspond to the camera making the current call; [Issue #7](https://github.com/Capslockb/tony-stark-hand-control/issues/7) tracks the missing per-camera ownership boundary.

The worker uses a daemon thread, but normal application shutdown also sets `_stop_worker = True`. The current shutdown path does not join the worker; the queue wait can take up to 0.5 seconds to observe the stop flag, and process exit remains the final fallback.

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
    distance(tip, wrist) > distance(pip, wrist) * 1.15
    and distance(pip, wrist) > distance(mcp, wrist) * 0.95
```

A finger counts as extended only when both ratio checks pass. If at least 3 of the 4 non-thumb fingers qualify, the palm is considered open. There is no fixed `0.05` normalized-distance threshold in this detector.

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
- The intended shared frame places camera 0 at the origin (`R=I`, `t=0`)
- Other cameras' stored `R, t` follow OpenCV's world-to-camera convention: `X_cam = R @ X_world + t`

**Projection matrices**:
- For each camera, `P = K @ [R | t]` (3x4)
- These are saved to `calibration.npz` for later use in 3D reconstruction

**Intended 3D reconstruction convention**:
For each 2D pixel landmark `(x, y)` in camera `i`:

1. **Undistort and normalize**: `cv2.undistortPoints((x, y), K_i, dist_i, P=None)` returns `(xn, yn)` in the normalized camera plane
2. **Camera ray**: `ray_camera = (xn, yn, 1)`
3. **World ray**: `ray_world = R_i^T @ ray_camera`
4. **Camera origin in world**: `O_i = -R_i^T @ t_i`

Then `triangulate_point_rays(origins, rays)` returns the 3D point closest to all rays.

The current runtime does not apply this convention consistently: `reconstruct_3d()` uses `origin = t`, while `reconstruct_fingertips()` passes normalized landmarks to a path that expects pixel coordinates. Existing synthetic checks use the same camera-center interpretation as the runtime rather than the convention emitted by `cv2.stereoCalibrate()`. Issue #6 tracks the focused implementation and regression-test correction.

**Reprojection error**:
Calibration reprojection error measures how well known checkerboard points project back into calibration images. It can help assess calibration fit, but it does not validate the separate runtime triangulation convention. Live 3D correctness requires an end-to-end test that begins with OpenCV-compatible `R, t`, projects known 3D points, and reconstructs them within a defined tolerance.

### HandControlApp

The Tkinter GUI. Six tabs:

1. **Main** — Start/Stop/Calibrate, per-camera enable, status, performance readouts
2. **Ollama** — optional fixed-vocabulary snapshot classification through a local or remote Ollama-compatible endpoint
3. **Tracking** — responsiveness, Fast Mode, engage/click/swipe tuning, filter controls, focus-highlight settings, and 3D/cursor toggles
4. **Accessibility** — Navigation mode (Tab vs Arrow), selection overlay
5. **3D / Room** — interactive matplotlib 3D viewport
6. **Cameras** — per-camera list with Test buttons

The intended main loop is paced against the fastest live camera's FPS. Once Issue #16 is corrected, each iteration should:
1. Read frames from all enabled cameras
2. Update cached live-feed status (every 10th frame)
3. Update cached FPS (every 30th frame)
4. Attempt a shared HandProcessor submission every `mediapipe_skip`th iteration; `mediapipe_skip` is currently an internal value rather than a GUI control
5. Draw the HUD on each camera's display
6. Stitch together a multi-cam aggregate decision for engage/disengage
7. Fire gestures if engaged
8. Queue at most one deferred redraw per camera and schedule the next loop iteration

On the current `main` branch, step 8 does not complete: redraw requests are queued, but the next-loop scheduling block is inside `_redraw_canvas()` and is unreachable after a normal canvas match. That regression is tracked in Issue #16.

The selection overlay refreshes at 10 Hz via `root.after(100, ...)`. On Windows, it calls `ctypes.windll.user32.GetGUIThreadInfo` to identify the focused control and `GetWindowRect` to obtain its bounds before positioning a green Tk border around it.

The 3D / Room tab uses `matplotlib.backends.backend_tkagg.FigureCanvasTkAgg` to embed a 3D matplotlib viewport. Click events are unprojected to 3D world rays and intersected with a horizontal plane to place anchors. Manual anchor placement and room-map persistence are separate from the unvalidated live stereo-coordinate path.

User-initiated redraw requests—initial drawing, resize events, anchor changes, and view controls—go through `_schedule_3d_redraw()` and are coalesced with `root.after(33, ...)`, which gives that request path a nominal ceiling near 30 Hz. Live fingertip reconstruction uses a separate pending flag and schedules `_redraw_3d_view()` with `root.after(200, ...)`, so live 3D updates are requested at about 5 Hz. These are scheduling intervals, not measured delivered frame rates; actual rendering also depends on Tk and matplotlib work.

### Single-instance lock

A `_SingleInstance` class prevents a second copy of the app from continuing when the lock mechanisms are available:

1. **Windows named mutex** (`Global\TonyStarkHandControl_v1`) — used on Windows through `ctypes.WinDLL`
2. **Temporary-file lock** on `tony_stark_hud.lock` — `msvcrt.locking` on Windows and `fcntl.flock` on Linux/macOS

The module currently imports OpenCV, MediaPipe, and Tkinter before reaching the `__main__` entry point. The lock is therefore acquired before constructing the Tk root and `HandControlApp`, but not before those heavyweight imports. Lock infrastructure errors are handled as best-effort and allow startup to continue.

On conflict, the second launch attempts to enumerate Windows top-level windows looking for one with "Tony Stark" or "Hand Control" in the title and calls `SetForegroundWindow`. If that path is unavailable or no window is found, it falls back to a Tk message box and then a stderr message if no GUI can be created.

On `WM_DELETE_WINDOW` (user clicks X), the lock is released. It is also released from a `finally:` block.

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
  → 3D / Room tab: experimental fingertip triangulation; correctness blocked by Issue #6
  → selection overlay: 10 Hz refresh of focused UI element border
```

## Performance characteristics

On a RTX 5060 (Blackwell, sm_120) + Ryzen 7 5700X with 4 cameras at 480x360 / 30 fps:

| Stage | Cost | Notes |
|---|---|---|
| CameraManager.read_all | ~10 ms | 4 × cv2.VideoCapture.read with small buffer |
| HandProcessor.detect | <1 ms (returns cached) | Real MediaPipe cost is ~30 ms on the worker |
| is_palm_open | <0.1 ms | 12 wrist-relative distance evaluations (`math.hypot`) |
| Gesture detection (when engaged) | ~0.5 ms | 4 × math.hypot + 4 × ring buffer ops |
| HUD overlay per cam | 0.2 ms | Static base cached, np.maximum blit |
| 3D reconstruction (5 tips × N cams) | ~5 ms | Timing only; live-coordinate correctness remains unvalidated under Issue #6 |
| Canvas redraw request | `after(15, ...)` with one pending callback per canvas | A 15 ms scheduling delay is not a measured redraw cost or delivered frame rate |
| 3D view redraw | user actions: 33 ms coalescing; live reconstruction: 200 ms scheduling | Nominal request ceilings are ~30 Hz and ~5 Hz respectively; delivered rate has not been benchmarked |
| Selection overlay refresh | <1 ms at 10 Hz | `GetGUIThreadInfo` + `GetWindowRect` + Tk geometry update |

On the cited development machine, reported main-loop work was **28-35 ms**, corresponding to a **28-35 fps compute-capacity estimate before the scheduled Tk wait**. Process CPU telemetry reported **3-5% of one logical CPU** with 4 cameras. These measurements are not cross-platform guarantees, do not establish the delivered 3D-view frame rate, and are not current runtime validation while Issue #16 blocks loop rescheduling.

## See also

- [Performance tuning](performance.md) — what the GUI knobs do
- [Calibration](calibration.md) — the calibration procedure
- [3D Room Mapping](3d_room_mapping.md) — operator-facing status and limitations
- [Gestures](gestures.md) — what each gesture does
- [Issue #6](https://github.com/Capslockb/tony-stark-hand-control/issues/6) — stereo convention and validation blocker
- [Issue #7](https://github.com/Capslockb/tony-stark-hand-control/issues/7) — per-camera inference ownership blocker
- [Issue #16](https://github.com/Capslockb/tony-stark-hand-control/issues/16) — main-loop rescheduling blocker
- The 7 audit passes in `hermes-skills/tony-stark-hand-control/references/`
