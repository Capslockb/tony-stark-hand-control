# Performance Tuning

The app exposes a handful of knobs that let you trade off CPU usage, latency, and tracking quality. Most users should not need to touch them — the defaults are tuned for a 4-camera RTX 5060 setup — but if you're running on a weaker machine, or want to push the limits, here's what each one does.

## Live readouts

The **Main** tab shows two real-time readouts updated every ~15 frames:

```
loop: 28.3 ms  (35.4 fps)  |  target: 30.0 fps
cpu:  3.2 %  ram: 195.4 MB  threads: 53
```

- `loop`: how long one main-loop iteration takes (across all enabled cameras)
- `target`: the FPS the loop is aiming for (auto-set to the fastest live camera's FPS)
- `cpu`: this process's CPU usage (per CPU core)
- `ram`: this process's working-set memory
- `threads`: number of active Python threads (includes the MediaPipe worker, the matplotlib refresh, the selection overlay refresh, etc.)

## Responsiveness preset (Tracking tab)

The single most important knob. It tunes the One-Euro filter, the moving-average buffer, and the predictor horizon all at once.

| Preset | What it does | When to use |
|---|---|---|
| 1 — Smoothest | Heavy smoothing, large buffer, short predictor horizon | When you want stable cursor even at the cost of latency |
| 2 | Slightly less smoothing | Still smooth but more responsive |
| 3 — Default | Balanced | Good for most users |
| 4 — Recommended | More responsive, smaller buffer, longer predictor | Snappier 1:1 feel, recommended for most users |
| 5 — 1:1 | Minimal smoothing, smallest buffer, longest predictor | Maximum 1:1 with your hand. Can feel jittery if your hand trembles. |

The preset sets four internal values which are also exposed as individual sliders below. If you change a slider, the preset goes out of sync — re-set the preset to apply the full set.

## Fast Mode (Tracking tab)

When checked, frames are pre-downscaled to 240p before being passed to MediaPipe. This reduces inference time by ~30% at the cost of some accuracy on tiny / far-away hands.

For most use cases (hand within 1 m of the camera) the accuracy loss is imperceptible. Turn it on if your CPU is the bottleneck.

## One-Euro filter parameters (Tracking tab)

The One-Euro filter is a low-pass filter whose cutoff frequency adapts to the speed of the signal. Two parameters:

- **min_cutoff** (default 2.5 Hz): the cutoff when the signal is stationary. Higher = less smoothing when at rest. Lower = more smoothing when at rest (cursor feels heavier but jitter is gone).
- **beta** (default 0.05): the cutoff slope vs speed. Higher = more responsive to fast motion. Lower = more lag during fast motion.

The defaults are tuned for "stable at rest, snappy when moving." Increase `beta` to 0.1+ if you find the cursor lagging behind your hand during fast swipes. Decrease to 0.01 if you see jitter.

## Smoothing buffer size (Tracking tab)

How many frames of history to keep per tip for the moving-average post-filter. Default 6.

- **Larger buffer** (10+): smoother, but more lag.
- **Smaller buffer** (3): snappier, but jitter and noise pass through.

## Cursor EMA alpha (Tracking tab)

When the screen cursor is enabled (off by default), this controls the exponential moving average between the current raw position and the previous cursor position. Default 0.55.

- **Higher (0.8+):** the cursor follows the raw position more closely (more jitter).
- **Lower (0.3):** the cursor trails the raw position (smoother but laggier).

## Velocity clamp (Tracking tab)

Maximum cursor speed in pixels per second. Default 10000. This caps the per-frame cursor movement to prevent "teleport" artifacts when the hand briefly leaves the frame and re-enters at a new position.

You probably don't need to change this. If your hand is fast and the cursor seems to lag, increase to 20000. If you see "jumps" when the hand first enters the frame, decrease to 5000.

## MediaPipe skip (Tracking tab)

How many frames between MediaPipe inferences. Default 1 (every frame). Set to 2 to run MediaPipe every other frame — halves the CPU cost of inference at the cost of slightly more cursor lag (mitigated by the predictor).

Useful on weak CPUs. With 4 cameras at 30 fps, MediaPipe running every other frame still gives 60 inferences/sec total, which is plenty.

## Predictor max horizon (Tracking tab)

How far forward the predictor extrapolates the current position. Default 0.15 s (150 ms). The predictor takes the most recent velocity and projects the position forward to "now" with quadratic decay.

If you have lag, increase to 0.25. If you see overshoot (the cursor "leads" your hand during fast stops), decrease to 0.10.

## Swipe parameters (Tracking tab)

- **Swipe min speed** (default 300 px/s): how fast the index finger must move for it to count as a swipe. Increase if accidental swipes fire; decrease if your swipes don't register.
- **Swipe cooldown** (default 0.8 s): minimum time between swipes. Increase to prevent rapid-fire; decrease to allow back-to-back swipes.

## Click threshold (Tracking tab)

Normalized 2D distance for thumb-to-fingertip click detection. Default 0.05 (5% of screen width).

- **Smaller** (0.03): clicks only fire when the thumb and finger are really touching. More "true" clicks, but you have to be very precise.
- **Larger** (0.08): clicks fire even when the thumb and finger are close. Easier to trigger, but false positives.

## 3D vs Screen cursor (Tracking tab)

By default, the app does **not** move the mouse cursor. The whole point of the app is accessibility navigation (Tab/Shift+Tab/Arrow), not mouse emulation. But if you want to use it as a fancy mouse, enable **Screen cursor**.

With Screen cursor enabled:
- The index finger position drives the system mouse cursor
- The screen cursor uses the EMA + velocity clamp described above
- All other gestures (clicks, swipes) still work

## Per-cam enable (Main tab)

Disable a camera to remove it from the pipeline. Disabled cameras don't run MediaPipe, don't contribute to FPS pacing, and don't appear in the right-side grid.

Useful when you have a 4-camera rig but only want 1-2 active. The disabled cameras' handles are released, freeing up the webcam driver.

## See also

- [Gestures](gestures.md) — what each gesture does
- [Architecture: HandProcessor](architecture.md#handprocessor) — the math
