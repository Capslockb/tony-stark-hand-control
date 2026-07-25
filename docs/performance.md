# Performance Tuning

The app exposes several user-facing controls for trading CPU usage, latency, and tracking stability. Other values described below are implementation constants or are managed only by the responsiveness preset; they are not independent Tracking-tab controls. Performance measurements in this repository come from a specific development machine and should not be treated as guaranteed results on other camera drivers, CPUs, GPUs, displays, or operating systems.

## Live readouts

The **Main** tab refreshes its performance labels every 15 main-loop iterations:

```text
loop: 28.3 ms  (35.4 fps)  |  target: 30.0 fps
cpu:  3.2 %  ram: 195.4 MB  threads:  5
```

- `loop` is the rolling average of work performed inside one main-loop iteration before the scheduled Tk wait.
- The parenthesized `fps` value is `1000 / loop_ms`. It is a compute-capacity estimate, not a measurement of delivered camera FPS or complete scheduled-loop frequency, because it excludes the wait before the next Tk callback.
- `target` is derived from the fastest reported enabled live-camera FPS and clamped to 15–60 FPS. Camera drivers can report inaccurate FPS values.
- `cpu` is process CPU time expressed relative to one logical CPU. Multi-threaded process activity can therefore exceed 100%.
- `ram` is the process working-set size.
- `threads` is `threading.active_count()`: active Python threads only. It does not count every native thread created by MediaPipe, OpenCV, camera drivers, or other libraries.

The CPU/RAM implementation uses Win32 APIs. On non-Windows systems the label reports an error rather than providing equivalent platform telemetry.

## Responsiveness preset (Tracking tab)

The responsiveness preset tunes five HandProcessor values together: One-Euro minimum cutoff, One-Euro beta, cursor EMA alpha, smoothing-buffer length, and prediction horizon. The last two are preset-managed and do not have separate sliders.

| Preset | Internal values | Intended trade-off |
|---|---|---|
| 1 — Smoothest | cutoff 1.0, beta 0.02, EMA 0.30, buffer 10, horizon 0.08 s | Most smoothing and shortest prediction |
| 2 | cutoff 1.8, beta 0.04, EMA 0.45, buffer 8, horizon 0.11 s | Smoother response |
| 3 — Default | cutoff 2.5, beta 0.05, EMA 0.55, buffer 6, horizon 0.15 s | Balanced default |
| 4 — Recommended in the UI | cutoff 3.5, beta 0.08, EMA 0.70, buffer 4, horizon 0.20 s | More responsive, less smoothing |
| 5 — 1:1 | cutoff 5.0, beta 0.12, EMA 0.85, buffer 3, horizon 0.25 s | Least smoothing and longest prediction |

The Tracking tab also exposes the One-Euro and cursor-EMA values individually. Changing those sliders overrides the corresponding current values, while selecting a responsiveness preset again reapplies the complete preset, including its buffer length and prediction horizon.

## Fast Mode (Tracking tab)

Fast Mode rescales frames whose height exceeds 240 pixels down to a 240-pixel height, preserving aspect ratio, before MediaPipe submission. It is intended to reduce inference work at the cost of detail for small or distant hands.

The source comments refer to an approximately 30% inference improvement on the development setup. That figure is not a cross-platform guarantee; measure the effect on the actual camera resolution and host.

## One-Euro filter parameters (Tracking tab)

The One-Euro-style filter adapts its cutoff to estimated motion speed:

- **Minimum cutoff** defaults to 2.5. Higher values follow raw movement more closely; lower values smooth stationary jitter more strongly.
- **Beta** defaults to 0.05. Higher values increase the cutoff more aggressively as estimated speed rises.

These sliders update the HandProcessor values directly. Selecting a responsiveness preset later replaces them with that preset's values.

## Smoothing-buffer length

The moving-average buffer is not an independent Tracking-tab control. It is managed by the responsiveness preset:

- preset 1: 10 samples
- preset 2: 8 samples
- preset 3: 6 samples
- preset 4: 4 samples
- preset 5: 3 samples

Larger buffers generally smooth more but add lag; smaller buffers preserve more immediate motion and noise.

## Cursor EMA alpha (Tracking tab)

When **Enable screen cursor** is on, the cursor EMA blends the new target into the previous cursor position. The default is 0.55.

- Higher alpha follows the new target more closely and preserves more jitter.
- Lower alpha moves more gradually and adds lag.

The screen cursor is off by default; accessibility navigation does not depend on this EMA.

## Velocity clamp

The cursor path currently uses a hard-coded maximum step equivalent to 10,000 pixels per second. There is no velocity-clamp slider in the Tracking tab. Changing this value requires a reviewed code change; it should not be presented as an operator-tunable setting.

## MediaPipe skip

`mediapipe_skip` defaults to 1, meaning the main loop attempts MediaPipe work on every eligible loop iteration. It is an internal value and has no current Tracking-tab control.

Inference is asynchronous and uses a shared pending queue/result path. The skip value gates submission attempts and cached-landmark refreshes; it does not guarantee a particular number of completed inferences per camera or per second. [Issue #7](https://github.com/Capslockb/tony-stark-hand-control/issues/7) tracks the missing per-camera ownership boundary for queued frames and completed results.

## Predictor horizon

The predictor extrapolates from the latest filtered point using estimated velocity, caps elapsed time at the preset's horizon, and applies quadratic decay toward zero at that cap. The horizon is controlled by the responsiveness preset rather than a separate slider.

A longer horizon can preserve apparent responsiveness between completed detections but can also increase overshoot. A shorter horizon limits extrapolation sooner.

## Swipe parameters (Tracking tab)

- **Swipe minimum speed** defaults to 300 screen pixels per second.
- **Swipe cooldown** defaults to 0.8 seconds.

The detector keeps up to one second of predicted index-finger history, requires more than 0.1 seconds between the oldest and newest samples, and requires one axis to dominate the other by more than 2:1.

## Click threshold (Tracking tab)

The UI labels this control in pixels, but runtime click detection compares normalized landmark distance against:

```text
normalized_threshold = click_threshold_px / screen_height * 4
```

The default slider value is 40. It is therefore not literally a 40-pixel camera-space threshold and is not a fixed percentage of screen width. Its effective normalized value changes with screen height. Higher slider values allow greater thumb-to-fingertip separation and make clicks easier to trigger; lower values require a tighter pinch.

## 3D vs screen cursor (Tracking tab)

By default, the app does **not** move the mouse cursor. Accessibility navigation uses keyboard focus actions instead. Enabling **Screen cursor** makes the predicted index-finger position drive the system cursor through the EMA and hard-coded velocity clamp described above.

Live stereo coordinates in the 3D view remain experimental while Issue #6 is open. Do not use the current live 3D output for measurements, automation, or safety decisions.

## Per-camera enable (Main tab)

Disabling a camera removes it from gesture processing and rendering and clears its cached landmarks. The camera handle remains open until the app is stopped or the camera manager is rebuilt; disabling a checkbox does not release that individual device to another application.

## See also

- [Gestures](gestures.md) — gesture behavior and thresholds
- [Architecture: HandProcessor](architecture.md#handprocessor) — filtering and inference structure
- [Issue #3](https://github.com/Capslockb/tony-stark-hand-control/issues/3) — current CI validation blocker
- [Issue #6](https://github.com/Capslockb/tony-stark-hand-control/issues/6) — live stereo convention blocker
- [Issue #7](https://github.com/Capslockb/tony-stark-hand-control/issues/7) — per-camera inference ownership blocker
