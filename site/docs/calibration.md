# Calibration

Calibration teaches the system the geometry of your camera rig: which cameras are where, what their focal length is, and how they relate to each other. Without calibration, the 3D reconstruction tab will be empty.

## When to calibrate

- First time you set up the cameras
- After moving any camera
- After changing camera resolution
- After changing lenses (if your cameras have interchangeable lenses)

You do **not** need to recalibrate if you:
- Restart the app
- Move your hand (the hand position is computed at runtime)
- Tweak any of the GUI sliders

## What you need

- The included checkerboard pattern (printed on flat, stiff paper)
- A flat surface to lay it on (a table, a book, a clipboard)
- Both cameras visible at the same time (you'll be holding the checkerboard in front of both)

## Printing the checkerboard

1. The install wizard places a `checkerboard_A4_9x6.pdf` on your desktop. If you don't have it, the pattern is:
   - 9 columns x 6 rows of internal corners (so 10x7 squares)
   - 25 mm square size
2. **Print at 100% scale** (no "fit to page"). The squares must be exactly 25 mm.
3. **Mount on a flat surface.** Paper warps. Glue the printout to a piece of cardboard or a hardcover book.
4. **Measure the squares** with a ruler after printing. If your squares are 24.5 mm instead of 25, either re-print or accept the 2% error (it'll show up as reprojection error in the calibration readout).

## Running the calibration

1. **Open the app** and go to the **Main** tab.
2. Click **Calibrate**. The status bar will say "Calibrating... hold the checkerboard in front of the cameras".
3. **Hold the checkerboard in front of BOTH cameras** at the same time. The cameras need to see it simultaneously.
4. **Move the checkerboard** slowly:
   - Hold it close to the cameras (30 cm)
   - Hold it far (3 m)
   - Tilt it left, right, up, down
   - Rotate it in the plane
5. The app captures a sample every time it sees the full checkerboard pattern in both cameras. It needs ~10-15 good samples.
6. After ~30-60 seconds, the status changes to "Calibrated. Reprojection error: 0.5 px" (or similar).
7. The calibration is saved to `calibration.npz` next to the script. You do not need to re-calibrate next time you run the app.

## What the numbers mean

### Reprojection error

The reprojection error (in pixels) is the standard deviation of how far the detected checkerboard corners are from where the model says they should be, after fitting. A good calibration has:

| Error | Quality | Notes |
|---|---|---|
| < 0.5 px | Excellent | Lab-grade setup, fixed cameras |
| 0.5-1.0 px | Very good | Typical for a careful home setup |
| 1.0-2.0 px | Good | Slight warping, lens distortion not fully captured |
| 2.0-5.0 px | Marginal | Cheaper cameras, paper warping, etc. |
| > 5.0 px | Bad | Recalibrate; the 3D reconstruction will be visibly off |

### Baseline

The **baseline** is the distance between your cameras. The app reports it in centimeters in the calibration readout. A typical laptop webcam + USB cam setup is 10-30 cm. A stereo webcam pair is ~6-12 cm.

### Per-camera intrinsics

Each camera's intrinsic matrix K is:
```
[fx  0  cx]
[ 0 fy  cy]
[ 0  0   1]
```

Where `(fx, fy)` is the focal length in pixels and `(cx, cy)` is the optical center. The app uses these to project 3D world points to 2D image points.

## Troubleshooting calibration

### "Could not find checkerboard" forever

- Make sure the pattern is 9x6 internal corners, not 8x6 or 10x7
- Check that the paper is flat (a warped printout will fail)
- Increase lighting; the app uses adaptive thresholding but very dark scenes fail
- Try moving the checkerboard more slowly

### Reprojection error > 5 px

- Check that you printed at 100% scale
- Check that the paper is flat
- Try recalibrating with more samples (hold the board in more positions)
- Make sure the cameras are stable (not on a wobbly stand)

### Cameras see different checkerboards

The app captures a sample when BOTH cameras see the full pattern simultaneously. If one camera is at an awkward angle, the calibration will take longer. Try holding the board closer to the camera that's struggling.

### Calibration succeeds but 3D is way off

- The baseline might be wrong. Check the readout. If it says 5 cm when it should be 30 cm, your cameras moved between calibration sessions — recalibrate.
- The cameras might have rolled (rotated around the Z axis) between captures. This is rare but possible. Recalibrate.

## Reusing calibration across machines

`calibration.npz` is **not portable**. The intrinsics (K, dist) are valid only for the specific camera + lens combination, and the extrinsics (R, t) are valid only for the specific physical arrangement. If you move a camera even 1 cm, you need to recalibrate.

If you want to share calibration across machines:
1. Use identical cameras (same SKU, same lens)
2. Mount them in an identical physical arrangement (3D-printed jig helps)
3. Calibrate once, copy `calibration.npz` to the other machines

This is what the unit tests do — they synthesize a calibration and test that reconstruction works.

## See also

- [3D Room Mapping](3d_room_mapping.md) — what to do *after* calibration
- [Architecture: StereoCalibrator](architecture.md#stereocalibrator) — the math
