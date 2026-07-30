# Historical Loop-Pacing and Processing Notes

This dated contributor note summarizes earlier experiments with camera pacing, MediaPipe processing, feed filtering, and Tk rendering. It is not a current performance report or acceptance criterion.

## Loop pacing

The intended loop derives a bounded target cadence from live camera metadata and subtracts measured iteration work before requesting the next Tk callback. Camera-reported frame rates can be missing or inaccurate, and `root.after(...)` values are requested delays rather than delivered frame rates.

The current runtime boundary is tracked in Issue #16: recurring scheduling must be restored and validated before end-to-end frame-rate claims can be made.

## MediaPipe processing

MediaPipe delegate availability depends on the installed build, operating system, drivers, and runtime support. A failed GPU-delegate attempt must fall back cleanly without being presented as proof that GPU acceleration is available.

The application uses a background inference worker and may reuse cached results between submissions. Per-camera result ownership and stale-result handling remain important correctness boundaries; current source and issues should be consulted before changing that design.

## Camera filtering and cached state

Disabled, unreadable, or non-live feeds should not enter expensive processing paths. Cached landmarks and display state must be cleared when a camera is disabled, disappears, or changes state so an old result is not presented as current input.

Brightness and variance thresholds are heuristics. They require validation against the supported cameras and lighting conditions and should not be described as universal values.

## Tk rendering

Coalescing redraw requests can prevent a queue of obsolete frames from accumulating. The conversion and widget update still execute on the Tk thread, so deferred callbacks do not move rendering to a background thread. Callback intervals, camera count, image size, and host load all affect delivered behavior.

## Measurement guidance

When evaluating a pacing or rendering change, record:

- exact commit and packaged-build revision;
- operating system, Python version, MediaPipe build, and delegate;
- camera models, backends, resolutions, and reported frame rates;
- enabled processing and display features;
- delivered loop cadence including scheduled waits;
- inference latency, CPU use, memory use, and sample duration.

Historical host measurements, fixed timing claims, and user-session observations are not current validation evidence.

Current source, public documentation, repository tests, and exact-head validation take precedence over this note.
