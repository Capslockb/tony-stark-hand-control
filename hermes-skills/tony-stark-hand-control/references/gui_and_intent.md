# Unified GUI + Intent Detection (Engage Gesture) + Live-Feed Validation

This note captures three reusable patterns from the Tony Stark hand control project that apply to **any "command‑by‑gesture" system** that must coexist with normal PC use.

---

## 1. Unified Tkinter GUI (single window, multi‑feed, per‑feed toggles)

### Why
A separate OpenCV window per camera is fine for a quick prototype, but a single Tkinter window with one canvas per camera is much easier to operate:
- All feeds are visible at once for a unified overview.
- The user can enable/disable individual cameras without restarting the app.
- A left‑hand control column carries global buttons (Start/Stop) and status text.

### Pattern
- Create a root `tk.Tk()` and two frames in a grid: `controls_frame` on the left, `feeds_frame` on the right.
- On **Start**: instantiate a `CameraManager` (or equivalent), then for each camera create a `LabelFrame` containing a `BooleanVar` checkbox and a `tk.Canvas`. Store the checkbox var and canvas in dictionaries keyed by camera index.
- Main loop is driven by `root.after(30, loop)`. At each tick:
  1. Read all cameras.
  2. For each enabled camera, convert the BGR frame to RGB, resize to the canvas size, wrap with `PIL.ImageTk.PhotoImage`, and `canvas.create_image(0, 0, anchor="nw", image=...)`. Stash the `PhotoImage` on the canvas (`canvas.imgtk = imgtk`) to prevent GC.
  3. Update status labels.
- On **Stop**: cancel the after‑callback, release cameras, clear canvases, re‑enable Start.
- Always handle `WM_DELETE_WINDOW` → stop cleanly + `root.destroy()`.

### Pitfalls
- **`PhotoImage` GC**: if you do not keep a reference, the image disappears on the next tick. The `canvas.imgtk = imgtk` trick is the standard fix.
- **Canvas size flicker**: read `canvas.winfo_width()/winfo_height()` (fall back to defaults like 480×360 if 0) before resizing.
- **Threading**: keep all GUI updates on the main thread; long work (e.g., Ollama API calls) goes in a worker thread that posts results via a `queue.Queue` you poll in the main loop.

### Imports
```python
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
```

---

## 2. Intent Detection (Engage Gesture)

### The problem
A camera‑driven input system must not fire when the user is just typing on their keyboard with their hands off‑camera, or just sitting there. A naïve "if a hand is detected, do something" will fire during any incidental hand crossing.

### Solution: open‑palm hold to engage
- Define an "engaged" gesture: an open palm facing the camera, all four fingers extended.
### Heuristic (works with MediaPipe 21‑landmark hand model): for each of {index, middle, ring, pinky}, **check whether the fingertip is further from the wrist than the PIP joint**. Count how many fingers are extended. If ≥ 3 are extended, treat the frame as a "palm‑open" sample.

### CRITICAL: do NOT use a Y-axis comparison (`tip.y < pip.y`)

The naive implementation that compares normalized Y coordinates is **broken on mirrored (selfie) cameras**:
- On a non-mirrored camera, an extended finger has `tip.y < pip.y` (tip above PIP in image space, smaller y).
- On a Windows webcam running in selfie mode (the default for most front-facing cameras), the Y axis is flipped — an extended finger has `tip.y > pip.y`.
- The original code returned `False` for a clearly open palm on the user's selfie camera, which made the engage gesture unreliable.

A reproduction demo lives at `C:\Users\Bernardo\palm_bug_demo.py` (old returns False on mirrored, new returns True).

The correct, mirror-invariant check: measure **distance from the wrist** (landmark 0) to the fingertip, vs distance from wrist to the PIP joint. If `tip_dist > pip_dist * 1.15` (and `pip_dist > mcp_dist * 0.95` to ensure the finger geometry is reasonable), the finger is extended.

```python
def is_palm_open(landmarks):
    if not landmarks or len(landmarks) < 21:
        return False
    wrist = landmarks[0]
    fingers = [(8, 6, 5), (12, 10, 9), (16, 14, 13), (20, 18, 17)]  # (tip, pip, mcp)
    def dist(a, b):
        return math.hypot(a.x - b.x, a.y - b.y, a.z - b.z)
    w_mcp = {f[2]: dist(wrist, landmarks[f[2]]) for f in fingers}
    w_pip = {f[1]: dist(wrist, landmarks[f[1]]) for f in fingers}
    w_tip = {f[0]: dist(wrist, landmarks[f[0]]) for f in fingers}
    extended = 0
    for tip, pip, mcp in fingers:
        if w_tip[tip] > w_pip[pip] * 1.15 and w_pip[pip] > w_mcp[mcp] * 0.95:
            extended += 1
    return extended >= 3
```

Test invariants to verify before shipping:
- 4 fingers extended → True
- 0 fingers extended (closed fist) → False
- 2 fingers extended (peace sign) → False
- 3 fingers extended (the threshold) → True
- `None` or empty input → False
- Y-axis flipped (mirror test) → still True (this is the bug-fix verification)
- Add a **hold** requirement: the palm‑open state must persist for `engage_hold_seconds` (default 0.6 s) before flipping Engaged. This filters out a single accidental frame.
- Add **smoothing**: keep a `deque(maxlen=10)` of 0/1 samples and use the rolling mean. Only flip Engaged if the mean is above a threshold (default 0.6). This kills single‑frame flicker.
- When the palm leaves, reset both the engage time and the history.

### Code skeleton
```python
self.intent_history = deque(maxlen=10)
self.engaged = False
self.engaged_time = 0
self.engage_hold_seconds = 0.6

def is_palm_open(landmarks):
    """Mirror-invariant palm-open check. Uses wrist-relative distances
    so it works on selfie cameras (flipped Y) too. See the full note
    above for why a Y-axis comparison is wrong."""
    if not landmarks or len(landmarks) < 21:
        return False
    wrist = landmarks[0]
    fingers = [(8, 6, 5), (12, 10, 9), (16, 14, 13), (20, 18, 17)]
    def dist(a, b):
        return math.hypot(a.x - b.x, a.y - b.y, a.z - b.z)
    w_pip = {f[1]: dist(wrist, landmarks[f[1]]) for f in fingers}
    w_tip = {f[0]: dist(wrist, landmarks[f[0]]) for f in fingers}
    w_mcp = {f[2]: dist(wrist, landmarks[f[2]]) for f in fingers}
    return sum(1 for t, p, m in fingers
               if w_tip[t] > w_pip[p] * 1.15 and w_pip[p] > w_mcp[m] * 0.95) >= 3

# in main loop:
any_palm = any(lm and is_palm_open(lm) for lm in per_cam_landmarks)
self.intent_history.append(1 if any_palm else 0)
avg = np.mean(self.intent_history) if self.intent_history else 0
if avg > 0.6:
    if not self.engaged:
        if self.engaged_time == 0:
            self.engaged_time = time.time()
        elif time.time() - self.engaged_time >= self.engage_hold_seconds:
            self.engaged = True
else:
    self.engaged = False
    self.engaged_time = 0
```

### Variations
- **Ollama‑driven engagement**: if a VLM is classifying gestures, include `engage` and `disengage` in the label set. Have the VLM call them when it sees the user deliberately presenting their hand vs. walking away.
- **Different gesture**: a fist (all fingers curled) also works as a toggle. Use the inverse: `tip.y > pip.y` for all four fingers.

### Pitfalls
- Coordinate convention: MediaPipe returns `y` in [0,1] with **y=0 at the top**. So "above" means smaller y. Don't mix it up with screen coordinates.
- Lighting/extreme angles break the heuristic. If you see it stuck in one state, add a "no hand seen for N seconds" reset to Disengaged.
- Don't engage the moment a palm appears in the corner of the frame. Gate engagement on the hand being near the center of the feed, or on a deliberate movement (e.g., raising the hand from below the frame into view).

---

## 3. Live-Feed Validation

### The problem
A USB camera that gets unplugged, a phone‑as‑webcam app that crashes, or a frozen frame can all produce a "valid"‑looking but useless `ret=True, frame.shape==(H,W,3)` image. The hand tracker will happily report "no hand" forever, the GUI will look like everything is fine, and the user won't know their second camera is dead.

### Cheap, reliable detector
Reject any frame where the grayscale standard deviation is too low (frozen/uniform) or the mean brightness is too low (black). A real scene with normal lighting has std ≫ 5 and mean ≫ 10.

```python
def is_feed_live(self, ret, frame, min_std=5.0, min_brightness=10):
    if not ret or frame is None:
        return False
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return np.std(gray) >= min_std and np.mean(gray) >= min_brightness
```

**WARNING — these default thresholds WILL blacklist your second/third camera.** Out of a 4-camera setup, only the brightest, best-lit one had std≥2 and brightness≥3; the other three were "live" but with a darker scene (low-light webcam, IR camera, dim room with a moving hand). They got dropped from the tracking pipeline and the GUI rendered black for them. **Default thresholds to use instead**: `min_std=0.5, min_brightness=0.2`. Those only reject genuinely frozen/uniform frames. Raise them only if you have a specific reason.

When the threshold matters:
- The check is designed to catch *frozen* frames (a camera that has stalled but still reports `ret=True`). A near-uniform black frame has std → 0 and brightness → 0.
- A *dim but live* scene can have brightness 0.5–2 with std 1–3 (a hand moving in a dark room). The check should keep this.
- If you're worried about static scenes (a flat wall, no hand movement), use **frame-to-frame diff** instead of std+brightness. The std+brightness check is the cheap "is this image alive" probe.

### Where to apply it
- **Before** hand detection: skip cameras whose feed is not live. They don't contribute to fusion and don't waste CPU.
- **In the GUI**: show "Disabled / No live feed" text on the canvas so the user knows the checkbox is on but the hardware is dead.

### Pitfalls
- **Very dark intentional scenes** (e.g., a dim room) can fail the brightness test. Lower the threshold or skip the brightness check.
- **Static walls** (very uniform) fail the std test. If the user sits in front of a flat background with only their hand moving, you may want a more sophisticated test (frame‑to‑frame diff). For most setups the std test is enough.
- **Don't call it for already‑disabled cameras**: check the per‑camera `BooleanVar` first, then `is_feed_live`.

---

## Putting it all together
The Tony Stark GUI does the following per loop tick:

1. Read all cameras.
2. For each camera: if the user has it enabled AND `is_feed_live(...)`, run MediaPipe and draw the HUD; otherwise mark it inactive.
3. Update the Intent state from the per‑camera palm‑open heuristic + smoothing.
4. If Engaged, run cursor/click/swipe logic.
5. If Ollama is enabled, send one frame to the worker thread (it throttles itself).
6. Render all enabled feeds to the Tkinter canvases.

This pattern keeps the system quiet when the user is not using it, robust to dead cameras, and snappy when it is being used.
