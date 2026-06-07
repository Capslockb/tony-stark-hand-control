# 3D Room Mapping

The 3D / Room tab lets you build a map of your physical environment for the live hand tracker. The map is a list of **anchors** (3D points with a type and a label) stored in `room_map.json`. The 3D viewport shows your cameras, your live hand position, and your anchors.

![3d room](images/3d_room.svg)

## Why would I want this?

The room map serves two purposes:

1. **Visualization** — see where your cameras are, where your hand is, and how they relate in 3D space.
2. **Spatial context** — the live hand position is displayed in the room frame, so you can tell if you're reaching toward a specific piece of furniture, a wall, a hot zone, etc.

Future versions of the app may use the map for gesture zoning (e.g. "gesture 'open the kitchen lights' only fires when the hand is in the kitchen zone"). For now, the map is mostly a visualization tool.

## How to use

1. **Calibrate first.** The 3D view shows your camera positions, which only work if you've calibrated. See [calibration.md](calibration.md).
2. Go to the **3D / Room** tab.
3. **Click in the 3D viewport** to drop an anchor. The click ray is intersected with a horizontal plane at the z-height you specify (default 1.0 m).
4. **Or click "Drop anchor at hand"** to mark the current 3D position of your hand.
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

## How the math works

For each camera, the calibration gives us:
- `K` (intrinsics): 3x3 matrix mapping 3D camera coordinates to 2D image coordinates
- `dist` (lens distortion): 5 coefficients
- `R`, `t` (extrinsics): rotation and translation that map world coordinates to camera coordinates

Given a 2D landmark `(x, y)` in camera `i`:

1. **Undistort**: `(x', y') = cv2.undistortPoints((x, y), K_i, dist_i)`
2. **Normalize**: `(xn, yn) = K_i^-1 @ (x', y', 1)` — this is a 3D unit ray in the camera's coordinate system
3. **World ray**: `ray_world = R_i^T @ (xn, yn, 1)` — same ray expressed in the world frame
4. **Camera origin in world**: `O_i = -R_i^T @ t_i` — where the camera is in 3D space

Then, given rays from N cameras with origins `O_i` and directions `ray_i`, we triangulate the 3D point that is closest to all rays:

```
[ray_1]_x * X = [ray_1]_x * O_1
[ray_2]_x * X = [ray_2]_x * O_2
...
```

This is an over-determined linear system solved via `np.linalg.lstsq`. The solution `X` is the 3D point.

The reprojection error is then: for each camera, project `X` back to 2D and measure the distance to the original landmark. The mean of these distances (in pixels) is the reprojection error.

## Coordinate system

The world frame is defined by the calibration: **camera 0's optical center is the origin**, and camera 0's local X/Y/Z axes are the world X/Y/Z axes. This is a standard OpenCV convention.

If you want a different origin, you can transform the anchors in `room_map.json` after the fact (apply a 4x4 rigid transform to all `(x, y, z)` triplets).

## See also

- [Calibration](calibration.md) — how to calibrate
- [Architecture: StereoCalibrator](architecture.md#stereocalibrator) — the math in more detail
