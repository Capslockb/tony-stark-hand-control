# 3D Room Mapping

The 3D / Room tab lets you build a map of your physical environment for the live hand tracker. The map is a list of **anchors** (3D points with a type and a label) stored in `room_map.json`. The 3D viewport shows your cameras, your live hand position, and your anchors.

> **Current validation status:** Anchor editing, manual coordinates, and JSON persistence are available, but live stereo coordinates must be treated as experimental. The calibration path stores OpenCV world-to-camera `R, t`, while the current reconstruction path treats `t` as a camera center; the synthetic fixtures validate that second convention rather than values emitted by `cv2.stereoCalibrate`. This mismatch is tracked in [Issue #6](https://github.com/Capslockb/tony-stark-hand-control/issues/6). Do not use live 3D output for measurements, automation, or safety decisions until the convention is corrected and validated end to end.

![3d room](https://raw.githubusercontent.com/Capslockb/tony-stark-hand-control/main/docs/images/3d_room.svg)

## Why would I want this?

The room map serves two purposes:

1. **Visualization** — see where your cameras are, where your hand is, and how they relate in 3D space.
2. **Spatial context** — after the stereo-convention fix in Issue #6 is validated, the live hand position can be displayed in the room frame so you can tell if you're reaching toward a specific piece of furniture, a wall, a hot zone, etc.

Future versions of the app may use the map for gesture zoning (e.g. "gesture 'open the kitchen lights' only fires when the hand is in the kitchen zone"). For now, the map is mostly a visualization tool, and live coordinates remain unvalidated.

## How to use

1. **Calibrate first** before evaluating the experimental live 3D view. See [calibration.md](calibration.md).
2. Go to the **3D / Room** tab.
3. **Click in the 3D viewport** to drop an anchor. The click ray is intersected with a horizontal plane at the z-height you specify (default 1.0 m).
4. **Or click "Drop anchor at hand"** to copy the current experimental live 3D position. Do not treat it as measured ground truth while Issue #6 is open.
5. **Or use the manual entry** to type x, y, z.
6. The new anchor appears in the right-side list. Click "Save room map" to persist it to disk.

## Anchor types

| Type | Color in 3D view | Typical use |
|---|---|---|
| `wall` | brown | Mark corners of walls, edges, or any vertical surfaces |
| `zone` | blue | Mark spatial zones (kitchen, desk, sofa) |
| `hotspot` | orange | Mark points of interest (lamp, switch, knob) |
| `furniture` | yellow | Mark furniture (table, chair, shelf) |
| `custom` | gray | Anything else |

## View controls

The 3D view is a matplotlib 3D axis. Standard matplotlib controls:

- **Drag with the left mouse button** to rotate
- **Scroll wheel** to zoom
- **Right-click drag** to pan
- **The View buttons** (top-down, front, side, 3/4) snap to preset angles

## Auto-fit

The view auto-fits to include all cameras, all anchors, and the live hand. If you add or move an anchor, the view zooms out to keep everything in frame.

If the view is too cluttered, you can hide individual layers:
- **Show hand trail** — the green line showing where your index finger has been
- **Show cameras** — the blue wireframe pyramids
- **Show anchors** — the colored spheres

## Saving and loading

The room map is saved as a single JSON file:

```json
{
  "next_id": 4,
  "anchors": [
    {"id": 1, "name": "wall_north", "x": -0.5, "y": 0.0, "z": 0.5, "type": "wall"},
    {"id": 2, "name": "kitchen", "x": 0.2, "y": 0.3, "z": 0.2, "type": "zone"},
    {"id": 3, "name": "lamp", "x": 0.4, "y": 0.4, "z": 1.2, "type": "hotspot"}
  ]
}
```

The file is auto-saved when the app closes. You can also save and load manually with the Save/Load buttons.

## Intended coordinate convention

For each camera, calibration gives us:
- `K` (intrinsics): 3x3 matrix mapping 3D camera coordinates to 2D image coordinates
- `dist` (lens distortion): 5 coefficients
- `R`, `t` (extrinsics): rotation and translation that map world coordinates to camera coordinates

Given a 2D pixel landmark `(x, y)` in camera `i`, the intended OpenCV-convention pipeline is:

1. **Undistort and normalize**: `cv2.undistortPoints((x, y), K_i, dist_i, P=None)` returns `(xn, yn)` in the normalized camera plane.
2. **Camera ray**: `ray_camera = (xn, yn, 1)`.
3. **World ray**: `ray_world = R_i^T @ ray_camera`.
4. **Camera origin in world**: `O_i = -R_i^T @ t_i`.

Then, given rays from N cameras with origins `O_i` and directions `ray_i`, triangulate the 3D point closest to all rays:

```
[ray_1]_x * X = [ray_1]_x * O_1
[ray_2]_x * X = [ray_2]_x * O_2
...
```

This is an over-determined linear system solved via `np.linalg.lstsq`. The solution `X` is the 3D point.

The current runtime does not yet apply this stored-extrinsic convention consistently; Issue #6 tracks the implementation and regression-test correction. The existing synthetic fixture must be rewritten to use the same world-to-camera convention as `cv2.stereoCalibrate()` before it can serve as end-to-end evidence.

The reprojection error is: for each camera, project a known world point back to 2D and measure the distance to the observed landmark. Calibration reprojection error alone does not validate the separate runtime triangulation convention.

## Coordinate system

The intended world frame is defined by calibration: **camera 0's optical center is the origin**, and camera 0's local X/Y/Z axes are the world X/Y/Z axes. This is the standard convention targeted by the correction in Issue #6.

If you want a different origin after reconstruction is validated, you can transform the anchors in `room_map.json` after the fact (apply a 4x4 rigid transform to all `(x, y, z)` triplets).

## See also

- [Calibration](calibration.md) — how to calibrate
- [Architecture: StereoCalibrator](architecture.md#stereocalibrator) — the math in more detail
- [Issue #6](https://github.com/Capslockb/tony-stark-hand-control/issues/6) — stereo extrinsic convention and validation blocker
