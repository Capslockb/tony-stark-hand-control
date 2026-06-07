# Gestures

The full gesture reference.

![gestures](images/gestures.svg)

## Engage / disengage

The app distinguishes between "you're using the PC normally" and "you're gesturing at it." The system is **disengaged** by default. To start controlling the PC, you must **engage**.

### How to engage

Hold an **open palm** (all 5 fingers extended, thumb included) toward any camera for about **0.6 seconds**. The status indicator in the bottom-left of the camera feed changes from "Disengaged" to "Engaged" in green.

The engage detector uses a wrist-relative distance check (not a Y-axis comparison) so it works on mirrored (selfie) cameras.

### How to disengage

Lower your hand out of frame, or make a fist. After ~0.3 seconds of no palm-open detection, the system disengages. You can also toggle it manually in the GUI.

### Why this matters

If the app didn't distinguish engaged from disengaged, every movement of your hand in front of the camera would fire a click, scroll, or Tab. That would be unusable. The engage gesture is the "I want to control the PC now" signal.

## Click gestures

When engaged, the following thumb-to-fingertip gestures fire actions. The detection uses **normalized 2D distance** (not pixels), so the click threshold is camera-resolution-independent.

| Gesture | Action | Threshold (normalized) |
|---|---|---|
| Thumb to **index** | `Enter` (activates focused element) | < 0.05 |
| Thumb to **middle** | Right-click / Apps key (context menu) | < 0.05 |
| Thumb to **ring** | `↑` (arrow up) | < 0.05 |
| Thumb to **pinky** | `↓` (arrow down) | < 0.05 |

The 0.05 normalized distance corresponds to about 5% of the screen width on a 1080p display. If you find the click too sensitive (fires when you don't want it), open the **Tracking** tab and increase the **Click threshold** slider. If it never fires, decrease it.

## Swipe gestures

Quick movements of the index finger fire navigation actions. Detection uses the **predicted** index position (not the raw filtered one) so swipes feel snappy.

| Swipe direction | Action (Tab mode) | Action (Arrow mode) |
|---|---|---|
| Right | `Tab` (next focusable element) | `→` |
| Left | `Shift+Tab` (previous) | `←` |
| Up | `↑` | `↑` |
| Down | `↓` | `↓` |

A swipe is defined as: index-finger velocity above `swipe_min_speed` (default 300 px/s) for 0.5 seconds in a direction with 2:1 axis dominance.

There's a 0.8 second cooldown after each swipe to prevent rapid-fire.

## Engage-hold duration

In the **Tracking** tab, the **Engagement hold (s)** slider controls how long you must hold the open palm before the system engages. The default is 0.6 s. Increase it if the app keeps engaging on accident; decrease it if it feels sluggish.

## How detection works

For the curious, the pipeline is:

1. **MediaPipe HandLandmarker** runs in VIDEO mode (one inference per frame). It returns 21 landmarks per hand in normalized 2D coordinates (z is depth, not absolute distance).
2. **One-Euro filter** smooths each fingertip's x/y over time. Two parameters: `min_cutoff` (smoothing at rest) and `beta` (smoothing at motion).
3. **Velocity tracker** records the per-tip velocity from the last 3 filtered values. Units: normalized 2D units per second.
4. **Predictor** extrapolates the current position forward to "now" using the velocity, with quadratic decay to prevent overshoot.
5. **Click detector** computes the normalized 2D distance between the predicted thumb and each predicted fingertip. If any is < threshold, fire the action.
6. **Swipe detector** looks at the predicted index position over a 0.5 s window. If the velocity exceeds `swipe_min_speed` in one direction, fire the action and start a cooldown.
7. **Engage detector** looks at `is_palm_open()` over a ring buffer. If the average is > 0.6 (i.e. the palm has been open for >60% of the last N frames), engage.

## Tips for reliable gestures

- **Lighting matters.** MediaPipe struggles with very dim or very bright scenes. Aim for face-level room lighting.
- **Background contrast helps.** A hand against a uniform wall works better than a hand against a cluttered bookshelf.
- **Distance.** 30-100 cm from the camera is the sweet spot. Too close and MediaPipe loses the whole hand; too far and individual fingers become indistinguishable.
- **One hand.** The app currently supports one hand. If you put both hands in frame, it'll use whichever MediaPipe returns first.
- **No gloves.** MediaPipe was trained on bare hands. Gloves work poorly. Dark skin tones in dim light also work poorly (this is a known MediaPipe limitation, not an app bug).

## See also

- [Performance tuning](performance.md) — what the responsiveness slider does
- [Architecture: HandProcessor](architecture.md#handprocessor) — the math
