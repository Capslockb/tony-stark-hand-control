# Gestures

The full gesture reference.

![gestures](https://raw.githubusercontent.com/Capslockb/tony-stark-hand-control/main/docs/images/gestures.svg)

## Engage / disengage

The app distinguishes between "you're using the PC normally" and "you're gesturing at it." The system is **disengaged** by default. To start controlling the PC, you must **engage**.

### How to engage

Hold an **open palm** toward any camera. The current detector does not evaluate the thumb; it treats the palm as open when at least 3 of the 4 non-thumb fingers (index, middle, ring, and pinky) pass the wrist-relative extension test.

Open-palm detections are stored in a rolling history of up to 10 loop samples. Once their average is above 0.6, the engagement timer starts; the condition must then remain active for the configured **Engagement hold** duration (0.6 seconds by default) before `engaged` becomes true.

The status indicator changes from "Disengaged" to "Engaged" when this completes.

### How to disengage

Lower your hand out of frame, make a fist, or otherwise stop satisfying the open-palm detector. The app disengages and resets the hold timer as soon as the rolling intent average is no longer above 0.6. The delay therefore depends on loop rate and recent history; it is not a fixed 0.3-second timeout.

The optional Ollama recognizer can also set the state when it returns an explicit `engage` or `disengage` gesture.

### Why this matters

If the app didn't distinguish engaged from disengaged, every movement of your hand in front of the camera would fire a click, scroll, or Tab. That would be unusable. The engage gesture is the "I want to control the PC now" signal.

## Click gestures

When engaged, the following thumb-to-fingertip gestures fire actions. Detection compares **normalized 2D landmark distance**, not camera pixels, so the measured fingertip separation is independent of camera resolution. The configured threshold is nevertheless derived from the display height, as described below.

| Gesture | Action | Trigger |
|---|---|---|
| Thumb to **index** | `Enter` (activates focused element) | Distance below the configured threshold |
| Thumb to **middle** | `Apps` key (opens the context menu) | Distance below the configured threshold |
| Thumb to **ring** | `↑` (arrow up) | Distance below the configured threshold |
| Thumb to **pinky** | `↓` (arrow down) | Distance below the configured threshold |

**Current limitation:** fingertip contacts are level-triggered. On every processed frame while the app is engaged, each fingertip inside the threshold fires its mapped action; there is no release latch, debounce, or single-winner arbitration. Holding a contact can repeat the same key, and multiple qualifying fingertips can issue multiple actions during one frame. Use brief, isolated taps until [Issue #13](https://github.com/Capslockb/tony-stark-hand-control/issues/13) is resolved.

The **Click threshold (px)** slider defaults to 40, but the runtime does not compare a literal 40-pixel camera-space distance. It converts the slider value with:

```text
normalized_threshold = click_threshold_px / screen_height * 4
```

The effective normalized threshold therefore changes with display height. Raising the slider allows more thumb-to-fingertip separation and makes actions easier to trigger; lowering it requires a tighter contact and can reduce accidental actions.

## Swipe gestures

Quick movements of the index finger fire navigation actions. Detection uses the **predicted** index position (not the raw filtered one) so swipes feel snappy.

| Swipe direction | Action (Tab mode) | Action (Arrow mode) |
|---|---|---|
| Right | `Tab` (next focusable element) | `→` |
| Left | `Shift+Tab` (previous) | `←` |
| Up | `↑` | `↑` |
| Down | `↓` | `↓` |

The runtime keeps up to one second of predicted screen-pixel positions. Once at least two samples span more than 0.1 seconds, it computes velocity from the oldest and newest retained samples. A swipe fires when speed exceeds `swipe_min_speed` (default 300 px/s) and one axis is more than twice the other.

There's a 0.8 second cooldown after each swipe to prevent rapid-fire.

## Engage-hold duration

In the **Tracking** tab, the **Engagement hold (s)** slider controls how long the rolling open-palm condition must remain active before the system engages. The default is 0.6 s. Increase it if the app keeps engaging accidentally; decrease it if it feels sluggish.

## How detection works

For the curious, the pipeline is:

1. **MediaPipe HandLandmarker** runs in VIDEO mode. It returns 21 landmarks per detected hand in normalized 2D coordinates (z is relative depth, not absolute distance).
2. **One-Euro filter** smooths each fingertip's x/y over time. Two parameters: `min_cutoff` (smoothing at rest) and `beta` (smoothing during motion).
3. **Velocity tracker** records per-tip velocity from the filtered history.
4. **Predictor** extrapolates the current position toward "now" using the velocity, with quadratic decay to limit overshoot.
5. **Click detector** computes normalized 2D distance between the predicted thumb and each predicted fingertip. If a distance is below the converted threshold, it fires the associated action.
6. **Swipe detector** keeps up to one second of predicted index-finger screen positions, compares the oldest and newest retained samples, applies the speed and 2:1 axis-dominance tests, then starts the cooldown.
7. **Engage detector** evaluates the four non-thumb fingers, appends an open/closed result to a 10-sample rolling history, and requires an average above 0.6 for the configured hold duration. If the average falls to 0.6 or below, it disengages and resets the timer.

## Tips for reliable gestures

- **Lighting matters.** MediaPipe struggles with very dim or very bright scenes. Aim for face-level room lighting.
- **Background contrast helps.** A hand against a uniform wall works better than a hand against a cluttered bookshelf.
- **Distance.** 30-100 cm from the camera is a practical starting range. Too close and MediaPipe may lose the whole hand; too far and individual fingers become difficult to distinguish.
- **One hand.** The app currently uses the first hand returned by MediaPipe from the selected camera path.
- **No gloves.** MediaPipe generally performs best on clearly visible bare hands; gloves and poor lighting can reduce landmark quality.

## See also

- [Performance tuning](performance.md) — what the responsiveness slider does
- [Architecture: HandProcessor](architecture.md#handprocessor) — the math
