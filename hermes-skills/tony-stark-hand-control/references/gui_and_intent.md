# GUI, Engagement, and Feed-Validation Notes

This dated contributor note summarizes earlier design work around the Tk interface, palm-open engagement, and camera-feed checks. It is historical context rather than a current runtime specification.

## GUI ownership

Tk widgets must be created and updated on the graphical event thread. Camera discovery, model initialization, and network requests can be slow or blocking and should use bounded worker paths that return results to the UI safely.

The current repository has a known main-loop rescheduling regression tracked in Issue #16. A design description of repeated `root.after(...)` processing is not evidence that the current branch continues beyond its first processing iteration.

A robust interface should:

- key camera state by camera index;
- retain image objects for as long as Tk needs them;
- avoid piling up redraw callbacks;
- release camera handles during Stop and close paths;
- keep cancellation and error reporting visible;
- isolate GUI construction from hardware and service access in tests.

## Engagement detection

The palm-open heuristic uses wrist-relative landmark distances so it is not dependent on a simple image-axis comparison. Focused tests should include empty input, closed and partially open hands, mirrored coordinates, and the configured hold/smoothing boundary.

Engagement reduces accidental input but is not a safety control. Gesture contacts remain subject to current runtime limitations, including the repeated-contact behavior tracked separately in Issue #13.

## Feed validation

Brightness and variance checks are inexpensive heuristics, not proof that a camera is healthy. Thresholds can reject valid dark or visually uniform scenes and should not be presented as universal values.

Useful tests should distinguish:

- failed reads;
- missing frames;
- uniform synthetic frames;
- dark but changing frames;
- frozen repeated frames;
- disabled cameras;
- slow or blocking capture operations.

Frame-to-frame comparison may be more appropriate than a single-frame brightness rule for some devices. Hardware-specific acceptance requires controlled testing on the stated camera and driver combination.

## Validation boundary

Current source, current issues, repository tests, and exact-head CI results take precedence over this note. Developer-machine paths, copied session output, and historical performance observations are not portable validation evidence.