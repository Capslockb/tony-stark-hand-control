# 3D Reconstruction from Multiple Cameras (calibrated, undistorted, shared world frame)

The 3D path in `tony_stark_hud_control.py` is a full two-phase stereo pipeline — not a
single per-camera `calibrateCamera` followed by a `triangulatePoint` call. This note
captures the actual code, the math pitfalls we hit, the synthetic stress-test that
verified it end-to-end, and the parts that any future session should NOT change.

## What the user wanted

- Point a finger at the screen → know the 3D position of the fingertip relative to the cameras
- Same point seen by two cameras should give the same world-frame (X, Y, Z)
- Calibration should survive app restarts (don't make the user print a checkerboard every day)
- Be honest about the math — no fake 3D numbers, no per-camera independent world frames
- Print the baseline and reprojection error so the user can see the calibration is real

## What is in the code

Class: `StereoCalibrator(board_size=(9, 6), square_size=0.025, calib_path=...)`
Helper: `triangulate_point_rays(origins, rays)` — pure function, used for tests

### Phase A — per-camera intrinsics
`cv2.findChessboardCorners` + `cv2.cornerSubPix` for sub-pixel accuracy.
Then `cv2.calibrateCamera(...)` per camera → `K_i, dist_i` (intrinsics + per-camera
extrinsics that we *throw away* — they live in independent world frames and are useless
for triangulation).

### Phase B — shared extrinsics
`cv2.stereoCalibrate(..., flags=cv2.CALIB_FIX_INTRINSIC)` is called pairwise against
camera 0 (1↔0, 2↔0, ...). This puts every camera in the same world frame (camera 0's
optical center is the origin; camera 0's extrinsic is identity by convention).

### Phase C — projection matrices
`P_i = K_i @ [R_i | t_i]` for each camera. Stored in `self.calibrations[i]['P']`.

### Phase D — runtime triangulation
For each detected 2D landmark per camera:
1. `cv2.undistortPoints(pts, K, dist, P=None)` → **normalized** image-plane coords
   (the `P=None` is load-bearing — `P=K` would re-emit pixel coords and break the math;
   see pitfalls below)
2. `p_norm = [xn, yn, 1.0]`
3. `ray_world = R_i.T @ p_norm` (OpenCV convention: `X_world = R * X_cam + t` so a ray
   direction in the cam frame maps to the world frame by `R^T`)
4. `origin = t_i` (setting `X_cam = 0` in `X_world = R * 0 + t` gives `origin = t_i`
   — **NOT** `-R^T @ t_i`; see pitfalls)
5. Solve the over-determined 2N × 3 system `[r_i]_x * X = [r_i]_x * O_i` via `np.linalg.lstsq`.

The runtime call in the main loop is:
```python
tip_3d = []
for j, t in enumerate(tip_indices):  # j = thumb/index/middle/ring/pinky
    pts = [fp[j] for fp in fingertip_pixels]  # fp[i] = (x_px, y_px) or None
    X = self.stereo.reconstruct_3d(pts)
    tip_3d.append(X)
```
…and the result is drawn as `3D index: +0.05, +0.10, +1.00 m` on the camera feed.
With ≥3 fingertips reconstructed, a second line shows the fingertip spread as a 3D
bounding box.

### Phase E — persistence
After a successful calibration, the result is saved to `calibration.npz` next to the
script (`DEFAULT_CALIB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
"calibration.npz")`). `StereoCalibrator.save(path=None)` and `load(path=None) -> bool`
are the public API. The app auto-loads on startup and shows "Loaded saved calibration
(N cams, baseline X cm, reproj err Y px)" in the Main tab. **Do not** skip the load —
recalibrating on every launch is annoying and the cameras don't move between sessions
in this user's setup.

## Calibration flow in the GUI

The Main tab's **Calibrate (checkerboard)** button calls `HandControlApp.start_calibration()`.
That method:
- Auto-opens cameras if the user hasn't clicked Start yet
- Prompts the user with a dialog explaining the printed 9×6 checkerboard requirement
- Calls `StereoCalibrator.calibrate_all(camera_manager, samples=15, progress_callback=...)`
- The progress callback updates a label on every captured view so the GUI stays alive
- On success, shows the baseline (cm), reprojection error (px), and a message about
  persistence; on failure, shows the reason ("Only captured N valid views; need at least 5")

If the user has more than 2 cameras, calibration still works (it aligns each to camera 0
sequentially). For 4+ cameras in a real volumetric setup, you would want a true multi-view
bundle adjustment; the current pairwise approach is approximate but good enough for hand
tracking at 0.5–2 m.

## Three math pitfalls we actually hit (synthetic tests caught them)

These are the bugs that survived multiple earlier rewrites of this code and were only
caught by writing a synthetic ground-truth test. **All three are easy to reintroduce.**
A future session that "simplifies" the triangulation should re-run the synthetic test
(`scripts/synthetic_stereo_test.py`, see below) before declaring done.

### Pitfall 1: `origin = -R^T @ t` is wrong
Wrong reasoning: "X_cam = R^T * (X_world - t) so when X_cam = 0, X_world = t" — that's
correct. But the camera's *origin* in the world frame IS `t` (where the camera physically
is in the world). Setting `X_world = R * 0 + t = t`. So `origin = t`, **not**
`-R^T * t`.

Symptom: every reconstructed point gets pulled toward z ≈ 0 (the rays intersect at the
cameras themselves rather than at the actual 3D point). Errors in the 1.0–1.7 m range
on a 1 m test point.

Fix: `origin = t` (or `origin = c['t'].reshape(3)`). Verified with synthetic data.

### Pitfall 2: `cv2.undistortPoints(P=K)` returns pixel coords, not normalized
OpenCV signature:
- `cv2.undistortPoints(pts, K, dist, P=None)`  → returns NORMALIZED image-plane coords
- `cv2.undistortPoints(pts, K, dist, P=K_new)` → returns pixel coords in the K_new frame

If you want normalized (so you can build a unit ray `[xn, yn, 1]`), you must use `P=None`.
If you use `P=K` (the seemingly-symmetric choice), you get pixel coords and your "unit
ray" is `[x_pixel, y_pixel, 1]` which is wildly wrong.

Symptom: triangulation gives garbage for any camera with a focal length ≠ 1.

Fix: `und = cv2.undistortPoints(pts, c['K'], c['dist'], P=None)`. Verified.

### Pitfall 3: comments matter — don't undo the fix while refactoring
Even after the math is fixed, the comments in the file must say `origin = t` clearly.
A future agent reading `-R^T * t` and "fixing" it to `t` without checking the math could
revert pitfall 1. Always re-run the synthetic test after a refactor.

## Synthetic ground-truth test (the smoke test for any 3D change)

This is the most valuable piece of this work. Before declaring a 3D change correct, run
`scripts/synthetic_stereo_test.py`. It:
1. Builds a known stereo rig (K, R=identity, t = [baseline, 0, 0])
2. Generates N random world points in a plausible volume
3. Projects them through each camera → 2D pixel coords
4. Calls `StereoCalibrator.reconstruct_3d` on those 2D points
5. Reports max and mean reconstruction error in metres

The accepted pass criterion (from the session that fixed the math):
**mean err < 1e-5 m, max err < 1e-5 m on 50 random points**. Real calibration noise
will be much worse, but the math has to be this clean before you can trust any
real-world output.

If you ever change the math (different convention, DLT instead of cross-product, etc.),
this test should still pass. If it doesn't, do not commit.

The test was run inline in the session with these results:

```
50 random points, no distortion, ideal stereo rig:
  Max err: 1.32e-06
  Mean err: 2.35e-07
  #bad (err>0.001): 0
```

## Reference: full OpenCV pipeline (as implemented)

```python
import cv2, numpy as np

# Phase A: intrinsics
objp = np.zeros((9*6, 3), np.float32)
objp[:, :2] = np.mgrid[0:9, 0:6].T.reshape(-1, 2) * 0.025
obj_points, img_points_per_cam = [], [[] for _ in cams]
# ... capture frames, findChessboardCorners, cornerSubPix ...

for i, cap in enumerate(cams):
    ret, K, dist, rvecs, tvecs = cv2.calibrateCamera(
        obj_points, img_points_per_cam[i], (w, h), None, None)
    # Keep K, dist; discard rvecs/tvecs (independent world frame)

# Phase B: shared extrinsics (pairwise against cam 0)
R = [np.eye(3)]; t = [np.zeros((3, 1))]
for i in range(1, n):
    rms, _, _, _, _, Ri, ti, _, _ = cv2.stereoCalibrate(
        obj_points,
        img_points_per_cam[0], img_points_per_cam[i],
        K, dist, K, dist,                 # use cam 0's intrinsics for both
        (w, h),
        flags=cv2.CALIB_FIX_INTRINSIC)
    R.append(Ri); t.append(ti)

# Phase C: projection matrices
P = [K @ np.hstack((R[i], t[i])) for i in range(n)]

# Phase D: runtime triangulation (see StereoCalibrator.reconstruct_3d)
```

## Sizing the checkerboard

A4-landscape, 9×6 interior corners (= 10×7 squares), 27 mm squares:
- 10 × 27 = 270 mm wide, 7 × 27 = 189 mm tall
- Fits A4 landscape (297 × 210 mm) with ~13 mm side and ~10 mm top/bottom margin

The `scripts/generate_checkerboard_pdf.py` helper produces a print-ready PDF with a red
crosshair marking the world origin corner (camera 0's "right-hand rule" reference).
Print it on a flat rigid surface (cardboard, foam board, or laminated paper). **Do not**
print on regular A4 copy paper — it warps and the corners can't be detected reliably.

`square_size=0.025` (25 mm) is the default in the code; if the user prints the 27 mm
version, change it. The reprojection error will be noticeably higher if the value is
wrong by even 10% — the user can verify by checking that the reported reprojection error
is below ~0.5 px on a clean capture.

## Things NOT to do

- **Do not** call `cv2.calibrateCamera` once per camera and use the per-camera extrinsics
  to triangulate. The cameras live in different world frames; the math gives garbage.
  Always run `cv2.stereoCalibrate` after to get shared extrinsics.
- **Do not** skip `cv2.undistortPoints`. Even with "good" cameras the distortion can be
  5+ pixels at the corners; skipping it adds that much error to the triangulation.
- **Do not** build `P_i` from K, R, t of different cameras' independent extrinsics.
  Always use the stereoCalibrate output R, t.
- **Do not** delete `calibration.npz` between sessions. The user explicitly asked for
  persistence. If the cameras move, the user clicks Calibrate again and the file is
  overwritten.
- **Do not** default `square_size` to 0.025 if the user is using a different board. Always
  set it to whatever the printed board's actual square size is. The reprojection error
  is the canary: if it pops above 1.0 px on a 480×360 feed, the square size is probably
  wrong.
- **Do not** remove the synthetic stress test from `scripts/`. It is the only thing that
  caught the three math bugs above; without it, future agents will reintroduce them.
- **Do not** apply the old 2D-pixel-coordinate shortcut (`points_2d[i] = (lm.x * screen_width,
  lm.y * screen_height)`) to the 3D path. The screen size is the wrong image size; you
  must use each camera's *own* image size (`self.camera_mgr.get_size(i)` or
  `self.stereo.image_sizes[i]`).

## Files
- `tony_stark_hud_control.py` — `StereoCalibrator` class
- `calibration.npz` — saved after a successful calibration, auto-loaded on startup
- `scripts/generate_checkerboard_pdf.py` — A4-landscape 9×6 PDF generator
- `scripts/synthetic_stereo_test.py` — synthetic ground-truth triangulation test
- `scripts/audit_app.py` -- comprehensive runtime test harness (77 assertions; see "Test-first audit pattern" below)
- `references/smoothing_and_aspect.md` — for the rest of the snappy-tracking chain
- `references/ollama_integration.md` §PITFALL — context on why we did NOT use local llama.cpp

## save() must compute P on the fly if missing

`StereoCalibrator.save()` historically read `c['P']` directly. This raised
`KeyError: 'P'` for any calibration dict that didn't include P -- which
happens for:

- synthesized/test calibrations (see `scripts/audit_app.py`)
- old `calibration.npz` files saved before the P-key was added
- any code path that builds a calibration dict by hand

**Fix in `save()`:** compute `P = K @ [R|t]` on the fly if the calibration
dict is missing it. The synthetic stress test already includes a save/load
round-trip; the audit script adds a 2-cam round-trip that exercises the
P-fallback path.

```python
if 'P' in c and c['P'] is not None:
    payload[f'P_{i}'] = c['P']
else:
    payload[f'P_{i}'] = c['K'] @ np.hstack((c['R'], c['t']))
```

**Why not just always recompute P in save()?** Because during calibration
we *also* store `c['P']` for runtime use, and the load() path expects to
find P in the npz. Recomputing in save() would also be fine, but the
fallback is safer for legacy files.

## Test-first audit pattern (2026-06-04)

When the codebase grew past ~2000 lines, an "audit + re-audit" cycle
became the only way to find bugs and not regress them. The pattern is:

1. **Write `scripts/audit_app.py` first** -- synthetic tests for every
   subsystem (RoomMap, HandProcessor, CameraManager, StereoCalibrator,
   triangulate_point_rays, OllamaGestureRecognizer circuit breaker, full
   App construction). Total: 77 assertions in ~10s.
2. **Run it.** It will fail in places -- most failures will be in the
   test code itself (uniform-bright vs noisy, missing `num_cameras`
   field, etc.) but a few will be real bugs in the app.
3. **Fix the real bugs.** Distinguish them by *what* the test asserts:
   "rejects uniform white" is correct behavior, "reconstruct_3d returns
   valid point" is a math invariant. Real bugs typically fail in the
   invariant tests.
4. **Add the fix as a regression test** by extending the audit script
   (e.g. add a `is_feed_live rejects uniform white` test if you just
   fixed a real is_feed_live bug; don't add it if it was just a test bug).
5. **Re-run the full audit** and the perf benchmark
   (`scripts/perf_benchmark.py`) before declaring done.

The audit script lives in the skill's `scripts/` directory so any future
session can run it after a big refactor. It's the cheapest insurance
against silent regressions.
