# Adaptive Loop Pacing and GPU Delegate

Two patterns added after the user reported the rig was choppy and lagging the PC with multiple cameras.

## 1. Adaptive loop pacing

The first version used `self.root.after(30, self.loop)` — a fixed 33 ms cap regardless of how many cameras were running or what their actual CAP_PROP_FPS was. With three 60 fps cameras the MediaPipe work alone exceeded 33 ms; the result was a 30 fps cap on a rig that should have been running 60+, and CPU saturation.

The fix: read each live camera's actual `CAP_PROP_FPS` per frame, take the **maximum** across live cameras, and pace the next iteration to that. Clamp to a sane range (15–60 fps) so a driver that lies and reports 0 fps doesn't stop the loop.

**Target `max`, not `min`.** Targeting the slowest live camera dragged a 3‑camera rig down to the worst feed's frame rate (e.g. one 5 fps black feed forced the whole loop to 5 fps). Targeting the fastest cam just means the slow camera occasionally produces a duplicate frame, which hand tracking tolerates fine. If a future change is tempted to "be conservative" and target `min(live_fps)`, that is a regression — undo it.

```python
# Inside the main loop, after per-camera work:
loop_t0 = time.time()
live_fps = []  # collected per camera that passed the live-feed check
# ... read frames, run MediaPipe, draw HUD ...
if live_fps:
    target_fps = max(live_fps)
else:
    target_fps = 15.0  # idle: still redraw UI cheaply
target_fps = max(15.0, min(60.0, target_fps))
elapsed_ms = (time.time() - loop_t0) * 1000.0
wait_ms = max(1, int(1000.0 / target_fps - elapsed_ms))
self.loop_id = self.root.after(wait_ms, self.loop)
```

`CameraManager.get_actual_fps(cam_index)` reads `CAP_PROP_FPS`; some drivers return 0, in which case it falls back to 30. If `max(live_fps)` is, say, 30 because that's the fastest cam reporting, the loop runs at 30 — the slow cam just produces duplicate frames occasionally, which the live-feed skip in §3 handles correctly.

## 2. GPU delegate for MediaPipe (with CPU fallback)

MediaPipe's Python `tasks` API exposes a GPU delegate that, when present, offloads the hand landmarker TFLite model to the GPU. On this Windows host the GPU runtime is **not always installed** — calling `Delegate.GPU` raises. Always wrap in try/except and fall back to CPU cleanly.

```python
from mediapipe.tasks import python as _mp_python

delegate_to_use = 0  # CPU
try:
    gpu_opts = _mp_python.BaseOptions(
        model_asset_path=model_path,
        delegate=_mp_python.BaseOptions.Delegate.GPU)
    test_det = mp_vision.HandLandmarker.create_from_options(
        mp_vision.HandLandmarkerOptions(
            base_options=gpu_opts,
            running_mode=mp_vision.RunningMode.VIDEO,
            num_hands=1))
    test_det.close()
    delegate_to_use = 1
    print("HandProcessor: GPU delegate active")
except Exception as e:
    print(f"HandProcessor: GPU delegate unavailable ({e}); using CPU")

base_options = mp_tasks.BaseOptions(
    model_asset_path=model_path,
    delegate=getattr(mp_tasks.BaseOptions.Delegate,
                     'GPU' if delegate_to_use == 1 else 'CPU'))
```

The console line `"GPU delegate active"` vs `"using CPU"` is the user-visible signal. Surface it in the GUI status panel if the user asks for confirmation.

## 3. Per-camera enable + auto-blacklist (same skip path)

The user explicitly asked that **disabled** cameras (checkbox off) and **black / no-signal** cameras (covered lens, unplugged) both be **completely skipped** in the main loop — no MediaPipe, no HUD draw, no canvas update. They should hit the same code path:

```python
for i, (ret, frame) in enumerate(raw):
    # GUI disable: skip processing AND rendering, show as disabled
    if not self.camera_vars[i].get():
        processed_frames.append((i, None, None))
        per_cam_landmarks.append(None)
        continue
    if not ret:
        processed_frames.append((i, None, None))
        per_cam_landmarks.append(None)
        continue
    # Black / no-signal feed: skip MediaPipe + HUD entirely
    if not self.camera_mgr.is_feed_live(ret, frame):
        processed_frames.append((i, None, None))
        per_cam_landmarks.append(None)
        continue
    # Only now run the expensive model
    live_fps.append(self.camera_mgr.get_actual_fps(i))
    det = self.hand_proc.detect(frame)
    ...
```

`is_feed_live` thresholds should be **strict** for the auto-blacklist to work:
```python
def is_feed_live(self, ret, frame, min_std=2.0, min_brightness=3.0):
    if not ret or frame is None:
        return False
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    std = np.std(gray)
    brightness = np.mean(gray)
    return std >= min_std and brightness >= min_brightness
```

The original 5.0/10.0 thresholds were too lax — they let near-black feeds through to MediaPipe, which then failed silently or hallucinated landmarks.

## 4. Resolution pitfall

3 cameras × 1280×720 × 60 fps overwhelmed the host CPU. The default is now **480×360 @ 30 fps per camera** (was 640×480 — 480×360 is plenty for hand landmarks and cuts decode + MediaPipe cost by ~44%). If a future user asks for higher resolution, also reduce the number of cameras and the FPS target — the host will not sustain more than ~30 fps total on this rig regardless of how the loop is paced.

## 5. Frame-skip + cached landmarks (cut MediaPipe cost in half on CPU)

The single biggest CPU consumer in this rig is the MediaPipe HandLandmarker itself. Running it on every frame is fine on GPU but burns 50–80% of a CPU core at 480×360. Running it on **every Nth frame** and reusing the cached landmarks for the in‑between renders is visually indistinguishable and roughly halves CPU cost.

```python
# In the main loop, after reading frames but before detection:
self._frame_counter += 1
run_mp = (self._frame_counter % max(1, self.mediapipe_skip) == 0)
# self._cached_landmarks = {}  # init in __init__

for i, (ret, frame) in enumerate(raw):
    if not self.camera_vars[i].get() or not ret \
            or not self.camera_mgr.is_feed_live(ret, frame):
        processed_frames.append((i, None, None))
        per_cam_landmarks.append(None)
        self._cached_landmarks.pop(i, None)   # forget stale cache
        continue
    if run_mp:
        det = self.hand_proc.detect(frame)
        landmarks = det.hand_landmarks[0] if det and det.hand_landmarks else None
        self._cached_landmarks[i] = landmarks
    else:
        landmarks = self._cached_landmarks.get(i)  # reuse last result
    # ... draw HUD, render to canvas, etc.
```

Tuning:
- `mediapipe_skip = 1` (every frame) — max accuracy, max CPU.
- `mediapipe_skip = 2` (every other frame) — visually identical, ~½ the cost. **Default.**
- `mediapipe_skip = 3–4` — slight visible lag during fast moves, much cheaper. Use on weak CPUs.
- `> 4` — gestures start to feel sluggish. Don't.

**Cache invalidation matters.** When a camera is disabled, gets re‑enabled, returns a black feed, or recovers from a black feed, the cache must be cleared (`self._cached_landmarks.pop(i, None)`). Otherwise you keep showing a stale hand position from a few frames ago on a feed that just came back.

The same trick applies to Ollama: with a 0.5 s cooldown inside `OllamaGestureRecognizer` plus a 6‑tick outer skip in the main loop, you get one cloud call every ~3 s at 30 fps instead of 30 calls/s. The error‑print throttling in `_worker` (one line per 30 s, not per failure) keeps the console clean when the endpoint is down.

## 6. Cached black-background (small but real canvas-render win)

The Tkinter canvas render path originally did `np.zeros((ch, cw, 3))` and a full `cv2.cvtColor` per camera per frame. Reuse a single per‑canvas `np.zeros` and copy it (one `np.copy` is much cheaper than one `np.zeros` plus a fill), and only reallocate when the canvas is actually resized:

```python
bg = getattr(canvas, '_bg_cache', None)
if bg is None or bg.shape[0] != ch or bg.shape[1] != cw:
    bg = np.zeros((ch, cw, 3), dtype=np.uint8)
    canvas._bg_cache = bg
canvas_img = bg.copy()
canvas_img[y_off:y_off + new_h, x_off:x_off + new_w] = disp_resized
```

In addition, use `cv2.resize(..., interpolation=cv2.INTER_AREA)` for the downscale step — measurably faster than the default bilinear on the 480p → canvas path.

## 7. Deferred canvas redraws (off the hot loop)

Caching the background helps, but with **3 cameras** the per‑frame `cv2 → numpy → PIL → ImageTk.PhotoImage → canvas.create_image` pipeline is still ~90 conversions/sec on the Tk thread. The user reported "app is extremely laggy atm" and this was a major contributor. The fix: **defer the canvas redraw off the hot loop**.

In the main loop, instead of doing the heavy work inline, mark the canvas as having a redraw pending and schedule it:

```python
# In HandControlApp.loop(), per camera:
for i, disp, _ in processed_frames:
    canvas = self.camera_canvases[i]
    if disp is None:
        # ... "Disabled / No live feed" message
        canvas._redraw_pending = False
        continue
    if getattr(canvas, '_redraw_pending', False):
        continue  # a redraw is already queued; skip
    canvas._redraw_pending = True
    # Stash the latest frame in a per-camera dict
    self._last_displays[i] = disp
    canvas.after(15, lambda c=canvas: self._redraw_canvas(c))
```

`self._last_displays` is a `{cam_index: latest_display_frame}` dict the loop populates every tick. `_redraw_canvas(canvas)` looks up the canvas's owning cam, reads the latest frame, does the cv2/PIL/Tk conversion there, and clears the pending flag.

Result: the hot loop does **zero** PIL/PhotoImage work; it only schedules Tk `after` callbacks (cheap). The actual rendering happens 15 ms later, on the same Tk thread, but at most one redraw per canvas is ever in flight, so it can't pile up.

**Pair this with lazy Toplevel creation** — the focus overlay (an always-on-top, click-through `Toplevel` with ctypes `WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW` styles) must NOT be built in `__init__`. Set `self.overlay = None` in `__init__` and build it inside `flash_overlay()` on first use. Building a Toplevel at startup costs ~50–150 ms and keeps a hidden window in the WM chain — both show up as visible startup lag and idle CPU.

## 8. Ollama worker must be lazy

Auto-building `OllamaGestureRecognizer` in `__init__` is a startup-perf trap: if the endpoint is unreachable, the worker thread starts making 8-second `requests.post` calls immediately, the main loop encodes a JPEG every 6 ticks, and the GIL gets hammered by the encoding + the worker thread even though the main loop "isn't blocked". The user saw the GUI go from "responsive" to "extremely laggy" the moment the app was restarted with the default Ollama config.

**Fix:** in `__init__`, set `self.ollama = None` and leave the Enable checkbox unchecked. The worker is built only when the user clicks **Save (rebuild Ollama worker)** in the Ollama tab. Throttled error printing (1 line per 30 s, not per failure) inside `_worker` is also mandatory for the same reason.
