# Calibration

Calibration estimates the geometry of the active camera rig: each camera's intrinsics and lens distortion, plus pairwise extrinsics relative to camera 0. The result is saved for later sessions.

> **Current validation status:** calibration can complete and persist its parameters, but successful calibration does not currently prove that live stereo coordinates are correct. The reconstruction path interprets the stored OpenCV extrinsics inconsistently, and the synthetic fixture does not exercise values emitted by `cv2.stereoCalibrate()`. This is tracked in [Issue #6](https://github.com/Capslockb/tony-stark-hand-control/issues/6). Treat the live 3D view as experimental and do not use it for measurements, automation, or safety decisions.

## When to calibrate

- First time you set up the cameras
- After moving any camera
- After changing camera resolution
- After changing lenses (if your cameras have interchangeable lenses)

You do **not** need to recalibrate merely because you:
- Restart the app
- Move your hand
- Tweak unrelated GUI sliders

## What you need

- A printed checkerboard with 9 × 6 internal corners (10 × 7 squares), printed so each square measures 25 mm
- A flat backing such as cardboard, a book, or a clipboard
- At least two active cameras able to see the full checkerboard at the same time

For rigs with more than two active cameras, every camera must detect the same checkerboard view before that sample is accepted.

## Printing the checkerboard

1. The current repository and install wizard do not include or generate `checkerboard_A4_9x6.pdf`. Create or obtain a checkerboard with:
   - 9 columns × 6 rows of internal corners (10 × 7 squares)
   - 25 mm square size
2. **Print at 100% scale**; do not use “fit to page.”
3. **Mount it flat.** Paper warp can degrade corner detection and calibration quality.
4. **Measure the printed squares** with a ruler. A scale error changes the physical scale represented by the saved calibration.

## Running the calibration

1. **Open the app** and go to the **Main** tab.
2. Click **Calibrate**.
3. Hold the checkerboard where **all active cameras** can see the complete pattern simultaneously.
4. Move it through varied positions and orientations:
   - near and farther from the cameras;
   - left, right, high, and low in the shared field of view;
   - tilted around multiple axes;
   - rotated in the image plane.
5. The default target is 15 accepted views. The progress callback reports `Captured N/15 views`; a view is accepted only when every active camera detects the full board.
6. Calibration can finish with fewer than 15 views if the capture-attempt budget expires, but the default path fails when fewer than 7 valid views were captured. More varied, high-quality views are preferable to repeated nearly identical views.
7. On success, the status reports the number of calibrated cameras, the camera-0-to-camera-1 baseline, and the mean reprojection error.
8. The calibration is saved to `calibration.npz` next to the application script and loaded on later runs.

Do not rely on a fixed completion time: camera count, resolution, lighting, board visibility, and checkerboard-detection cost all affect duration.

## What the numbers mean

### Reprojection error

The displayed reprojection error is the **mean Euclidean pixel distance** between detected checkerboard corners and the corresponding corners projected by the fitted calibration. It is not a standard deviation.

Lower is generally better, but the repository does not enforce documented “excellent/good/bad” acceptance bands. Compare the value across repeated calibrations of the same rig and inspect the capture quality. Most importantly, a low calibration reprojection error does **not** validate the separate live triangulation convention while Issue #6 remains open.

### Baseline

The displayed **baseline** is the magnitude of the stored translation between camera 0 and camera 1, reported in centimeters. With more than two cameras, this single number does not summarize every camera's position or the full rig geometry.

An implausible baseline can indicate an incorrect checkerboard scale, poor shared views, or a changed camera arrangement. Recalibrate after changing the rig.

### Per-camera intrinsics

Each camera's intrinsic matrix `K` is:

```
[fx  0  cx]
[ 0 fy  cy]
[ 0  0   1]
```

`(fx, fy)` are focal lengths in pixels and `(cx, cy)` is the optical center. These values and the distortion coefficients are resolution- and lens-specific.

## Troubleshooting calibration

### “Could not find checkerboard” or no progress

- Confirm the pattern has 9 × 6 **internal corners**, not 9 × 6 squares.
- Keep the board flat and fully inside every active camera frame.
- Improve lighting and reduce glare or motion blur.
- Move the board more slowly.
- Disable or reposition a camera that cannot share a usable view with the rest of the rig.

### Reprojection error is unexpectedly high

- Confirm the print was produced at 100% scale and measure the squares.
- Keep the board flat.
- Capture more varied views across the shared image area.
- Keep every camera fixed throughout calibration.
- Repeat calibration and compare results rather than relying on one fixed threshold.

### Cameras do not share the checkerboard view

A sample is accepted only when every active camera detects the full pattern in the same capture iteration. Reposition the board or cameras so their fields of view overlap, or calibrate a smaller active set.

### Calibration succeeds but live 3D is wrong

First account for the known reconstruction-convention defect in [Issue #6](https://github.com/Capslockb/tony-stark-hand-control/issues/6). Calibration success, a plausible baseline, and a low reprojection error are not end-to-end proof of live 3D correctness in the current runtime.

After that defect is corrected and validated, ordinary rig checks still include:

- confirming the checkerboard scale;
- checking that cameras did not move after calibration;
- confirming the runtime uses the same resolution as calibration;
- repeating calibration with better shared views.

## Reusing calibration across machines

`calibration.npz` is rig-specific. Reuse is only defensible when the camera hardware, lenses, resolution, camera ordering, and physical arrangement are unchanged. Copying the file to a different machine does not make a different rig equivalent.

Recalibrate after moving or replacing a camera, changing its resolution, changing its lens, or changing camera order.

The current synthetic tests construct calibration data directly; they do not yet validate the complete `cv2.stereoCalibrate()` → persistence → live reconstruction path. Issue #6 defines the required deterministic regression test.

## See also

- [3D Room Mapping](3d_room_mapping.md) — manual anchors and the live-3D validation boundary
- [Architecture: StereoCalibrator](architecture.md#stereocalibrator) — intended coordinate convention
- [Issue #6](https://github.com/Capslockb/tony-stark-hand-control/issues/6) — extrinsic-convention and regression-test blocker
