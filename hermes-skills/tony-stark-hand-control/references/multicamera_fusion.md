# Historical Multi-Camera Processing Notes

This dated contributor note records earlier ideas about using more than one camera for hand tracking. It is not a description of a validated fusion algorithm or a current capability claim.

## Current conceptual boundary

Multiple cameras can provide additional viewpoints, but detections from different image planes cannot be averaged as though their normalized coordinates share one geometry. Reliable 3D fusion requires calibrated intrinsics and extrinsics, consistent landmark ownership, synchronized or acceptably aligned observations, and an end-to-end metric test.

The current application reads multiple feeds and uses shared processing state. The latest inference result is not guaranteed to belong to the camera making the current call, and the live stereo-coordinate path has separate convention and coordinate-input blockers. Consult the current architecture documentation and Issues #6 and #7 before treating multi-camera output as fused or metric.

## Durable implementation concerns

- Preserve camera identity from frame capture through inference result consumption.
- Clear cached detections when a feed is disabled, unreadable, or replaced.
- Do not average normalized landmarks from unrelated views as a substitute for geometric reconstruction.
- Define timestamp and synchronization tolerances before combining observations.
- Bound camera discovery, reads, cancellation, and capture cleanup.
- Measure processing and rendering costs on the exact supported configuration rather than assuming linear or universal scaling.

## Validation boundary

A supported multi-camera claim requires deterministic synthetic geometry tests, per-camera ownership tests, controlled occlusion and recovery cases, exact-head repository checks, and hardware validation with the stated camera models, backends, resolutions, and mounting geometry.

Current source, public documentation, repository tests, and exact-head validation take precedence over this historical note.
