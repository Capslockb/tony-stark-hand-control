# Smoothing Pipeline and Aspect‑Preserving Camera Display

Two recurring bugs in any real‑time hand‑tracking GUI, and the patterns that fix them.

## 1. Choppy / Jittery Tracking (Three‑Layer Smoothing)

A naïve 5‑frame moving average is not enough. The cursor jitters visibly and spikes on fast hand motion. The fix used in `tony_stark_hud_control.py` is three layers stacked:

### Layer 1 — One‑Euro Filter (per fingertip, on raw normalized coords)
A low‑pass filter whose cutoff adapts to speed. At rest it's very smooth; on fast motion the cutoff rises so the filter doesn't lag.

```python
def _one_euro_filter(self, prev, raw, dt, min_cutoff=2.5, beta=0.05):
    if prev is None or dt <= 0:
        return raw
    # Speed estimate from raw delta
    dx, dy = raw[0] - prev[0], raw[1] - prev[1]
    speed = math.hypot(dx, dy) / max(dt, 1e-6)
    # Adaptive cutoff: higher when moving
    cutoff = min_cutoff + beta * speed
    alpha = 1.0 - math.exp(-2 * math.pi * cutoff * dt)
    x_f = prev[0] + alpha * (raw[0] - prev[0])
    y_f = prev[1] + alpha * (raw[1] - prev[1])
    return (x_f, y_f)
```

- `min_cutoff` (Hz): lower → smoother at rest. Default `2.5` for the **Responsiveness preset 3**. Preset 5 uses 5.0 (snappiest); preset 1 uses 1.0 (smoothest).
- `beta`: higher → snappier on fast motion. Default `0.05`. Preset 5 uses 0.12; preset 1 uses 0.02.

### Layer 2 — Moving Average (6 frames at preset 3)
A `deque(maxlen=6)` per fingertip, averaged after the One‑Euro filter. ~0.2 s window at 30 fps. Kills the residual jitter from layer 1. The buffer size is part of the Responsiveness preset (1 = 10 frames, 5 = 3 frames). Smaller buffer = less phase delay but more jitter.

### Layer 3 — Screen‑Pixel EMA + Velocity Clamp
On the final cursor position in screen pixels:

```python
alpha = 0.55
if cursor_ema is None:
    cursor_ema = (tx, ty)
else:
    cx, cy = cursor_ema
    nx = cx + alpha * (tx - cx)
    ny = cy + alpha * (ty - cy)
    # With the predictor upstream, the input is already accurate.
    # 10000 px/s (10 px/ms) only clamps absurd teleports, not real motion.
    max_step = 10000 * dt
    dx, dy = nx - cx, ny - cy
    dist = math.hypot(dx, dy)
    if dist > max_step and dist > 0:
        nx = cx + dx / dist * max_step
        ny = cy + dy / dist * max_step
    cursor_ema = (nx, ny)
pyautogui.moveTo(int(cx), int(cy))
```

`alpha` 0.3–0.85 is the useful range (preset 1 → 5). Lower = floatier, higher = snappier. `max_step` 10000 px/s is the new default; lower it to 5000 if you want to suppress jumps on shaky hands. With the predictor upstream (see `mediapipe` skill, section "Inter-Frame Motion Prediction"), the input to this EMA is already extrapolated forward in time, so the EMA just smooths the *output* and a tighter clamp would only add lag.

### Layer 0 — Inter-Frame Motion Predictor (optional but recommended)
A per-tip velocity estimator + `predict(tip_id, now)` extrapolator. **Crucial for 1:1 feel.** All gesture / click / cursor / HUD code reads from `predict()`, not from the last filtered value. See the `mediapipe` skill for the full pattern. The `tony_stark_hud_control.py` Responsiveness preset bundles this with the other three knobs (table in the audit reference).

### Per‑frame `dt`
Compute `dt = time.time() - last_ts`, clamp to `[1/120, 0.2]`. Pass it to all three layers; otherwise the filter coefficients are wrong and the cursor flies on slow frames.

## 2. Stretched Camera Feeds (Aspect‑Preserving Resize)

Tkinter canvases resize to whatever the user drags them to. Blindly doing `cv2.resize(frame, (canvas_w, canvas_h))` squashes a 16:9 webcam into a square box. The fix is a `letterbox_resize` helper:

```python
def letterbox_resize(frame, target_w, target_h):
    h, w = frame.shape[:2]
    if target_w < 2: target_w = 480
    if target_h < 2: target_h = 360
    scale = min(target_w / w, target_h / h)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(frame, (new_w, new_h))
    # Centre on a black canvas
    canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    x_off = (target_w - new_w) // 2
    y_off = (target_h - new_h) // 2
    canvas[y_off:y_off+new_h, x_off:x_off+new_w] = resized
    return canvas
```

Apply it right before converting to `Image.fromarray` → `ImageTk.PhotoImage`. The HUD is drawn on the *original* frame, not the letterboxed one, so the annotations land in the right place.

### Sanity check after the fix
- Resize the window to a square. The video should be centred with black bars on top/bottom (or sides for vertical videos), not stretched.
- The 3D reconstruction line drawn by `cv2.putText` should appear inside the video rectangle, not outside.

## 3. Tkinter Canvas Redraw Throttling (No‑Lag Multi‑Cam)

A naïve loop that does `cv2 → numpy → PIL → ImageTk.PhotoImage → canvas.create_image` for every camera on every tick can starve the Tk mainloop and make the GUI feel frozen. Symptoms: the camera canvases stop updating, the Notebook tab becomes unresponsive, and any `root.after()` callbacks pile up. The fix is to **defer** the canvas redraw to a low‑priority `canvas.after(15, ...)` callback and drop requests that arrive while one is already pending.

```python
# On the camera's canvas widget, store these:
canvas._redraw_pending = False
canvas._last_frame = None   # (numpy BGR array)

def schedule_canvas_redraw(canvas):
    """Drop the request if one is already pending (coalesce)."""
    if getattr(canvas, '_redraw_pending', False):
        return
    canvas._redraw_pending = True
    canvas.after(15, _do_canvas_redraw, canvas)

def _do_canvas_redraw(canvas):
    canvas._redraw_pending = False
    frame = canvas._last_frame
    if frame is None:
        return
    # Convert + draw (with letterbox_resize)
    cw, ch = canvas.winfo_width(), canvas.winfo_height()
    img = letterbox_resize(frame, cw, ch)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    im = Image.fromarray(img_rgb)
    imgtk = ImageTk.PhotoImage(image=im)
    canvas.imgtk = imgtk          # prevent GC of the image
    canvas.delete("all")
    canvas.create_image(0, 0, anchor="nw", image=imgtk)
```

In the main loop, instead of doing the heavy work directly:

```python
# In the per-camera loop, just store the latest frame and kick the
# redraw. The actual cv2 → PIL → Tk work happens 15ms later, on the
# main thread, in the after() callback.
for i, disp, _ in processed_frames:
    if i in self.camera_canvases:
        c = self.camera_canvases[i]
        c._last_frame = disp
        schedule_canvas_redraw(c)
```

### Why this works
- `canvas.after(15, ...)` runs on the Tk main thread, interleaved with the rest of the GUI (Notebook tabs, buttons, status labels). The work happens at most ~66 times/sec per canvas.
- The `_redraw_pending` flag means if 5 frames arrive in 15ms, only one redraw actually runs. The other 4 are silently dropped — the user sees the latest one anyway.
- Each canvas has its own flag, so a stalled/redrawing canvas doesn't block the others.
- If the user resizes the window, Tk fires a configure event; you can also call `_do_canvas_redraw` from a `<Configure>` binding to force a fresh paint with the new dimensions.

### Pitfalls
- **`imgtk = ImageTk.PhotoImage(...)` must be stored on the canvas as `canvas.imgtk = imgtk`** or it gets garbage-collected and the next paint shows a blank canvas. This is the #1 Tkinter image-shows-then-disappears bug.
- **`_last_frame` is a numpy array.** Storing it on the canvas is fine — Tk's widget objects are python objects too. The next frame overwrites it.
- **15 ms is the sweet spot.** Lower (5 ms) burns CPU without visual benefit; higher (33 ms) makes the camera feel choppy on a 30 fps source.
- **Don't use `canvas.after(0, ...)` — it's the same as `canvas.update_idletasks()` and can run while you're still building the frame, causing "flash of half-painted canvas".** The 15 ms delay lets the mainloop finish its current tick first.

### Apply it selectively
- You only need this trick for **multiple** camera feeds. A single 480×360 canvas updating 30 times/sec on a fast CPU rarely lags. The problem is **N canvases × 30 fps = N × cv2 → PIL → Tk conversions per second**, which scales poorly.
- If a single-camera session still feels laggy, suspect the **MediaPipe inference** (15-50ms per frame on CPU) rather than the Tk rendering. Move MediaPipe to a worker thread for sub-15ms loop pacing (advanced; see `references/adaptive_pacing_and_gpu.md` for the existing single-thread approach).

### See also
- The same `_redraw_pending` pattern works for **HUD overlays, status labels, and progress bars** that update at high frequency. Any time the source data updates faster than the eye can perceive, coalesce the redraws.

## Tuning cheat sheet

| Symptom                           | Fix                                                 |
|-----------------------------------|-----------------------------------------------------|
| Cursor jitters at rest            | Lower `min_cutoff` (e.g. 0.8)                       |
| Cursor lags on fast motion        | Raise `beta` (e.g. 0.05) and/or `alpha` (0.5)       |
| Cursor jumps on MediaPipe glitches | Lower `max_step` (e.g. 1200 px/s)                  |
| Video stretched / squished        | Use `letterbox_resize`, not raw `cv2.resize`        |
| Aspect still wrong after fix      | Check the HUD is drawn *before* letterboxing        |
