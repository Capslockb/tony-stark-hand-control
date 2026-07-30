# Historical 3D Reconstruction Notes

This document preserves contributor context for the experimental multi-camera reconstruction path. It is not a current correctness claim, calibration specification, or validation report.

## Current status

The repository contains camera calibration, persistence, projection-matrix, ray-triangulation, and room-anchor code. Live stereo output remains experimental and must not be used for measurement, automation, or safety decisions until the coordinate conventions and end-to-end tests tracked in Issue #6 are corrected and reviewed.

OpenCV extrinsics produced by stereo calibration use the world-to-camera convention:

```text
X_camera = R @ X_world + t
```

Under that convention, the camera center in world coordinates is:

```text
C_world = -R.T @ t
```

The current runtime does not apply this boundary consistently. One path treats `t` as the camera origin, and another mixes normalized landmark coordinates with a pixel-coordinate reconstruction interface. Historical synthetic checks that used the same incorrect assumption are not independent validation.

## Calibration and persistence

Calibration estimates per-camera intrinsics and distortion, then pairwise extrinsics relative to camera 0. Results are persisted so a stable camera rig does not require calibration on every launch.

Persistence should be loss-aware and explicit about incompatible or incomplete records. A saved calibration file is not proof that live reconstruction is correct. Reprojection error measures checkerboard fit and does not validate the separate runtime triangulation convention.

## Required validation boundary

A useful deterministic regression should:

1. construct OpenCV-compatible `R` and `t` values for a known camera rig;
2. project known 3D points into each camera using the same convention;
3. pass pixel observations through the production reconstruction path;
4. assert reconstruction within a defined tolerance;
5. include non-identity rotation, distortion handling, missing observations, and degenerate geometry;
6. fail when normalized and pixel coordinates are mixed.

Hardware validation should additionally record the exact revision, operating system, camera models, resolutions, calibration target dimensions, sample count, and measured error method.

## Contributor guidance

Keep changes to calibration, coordinate conversion, and triangulation focused and reviewable. Run deterministic geometry tests before interpreting live output. Current source, current issues, repository tests, and exact-head CI results take precedence over this dated note.