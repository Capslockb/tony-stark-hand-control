# Historical Smoothing and Display Notes

This dated contributor note preserves design context for fingertip smoothing, cursor output, aspect-preserving camera display, and coalesced Tk redraws. It is not a current tuning specification or performance report.

## Smoothing pipeline

The application has combined adaptive filtering, a short history buffer, velocity estimation, prediction, and final screen-coordinate smoothing. Each stage trades jitter against delay, and its parameters depend on delivered sample timing rather than an assumed frame rate.

Durable boundaries:

- use monotonic elapsed time and handle missing, repeated, or delayed samples;
- keep units explicit when converting normalized landmarks to display coordinates;
- reset histories after tracking loss, camera changes, or long gaps;
- prevent prediction and velocity limits from turning stale detections into current motion;
- validate presets with repeatable traces rather than fixed claims about feel or latency.

## Aspect-preserving display

Camera frames should retain their source aspect ratio when placed in a resizable Tk canvas. Scale the image uniformly, center it in the available area, and use padding for unused space. Apply overlays in a coordinate system that matches the image on which they are drawn.

Tests should cover horizontal, vertical, square, very small, and resized canvases without requiring a real camera or display where practical.

## Redraw coalescing

A pending-redraw flag can collapse several obsolete frame requests into one Tk callback using the latest available frame. The conversion and widget update still execute on the Tk thread; deferred scheduling does not make rendering concurrent.

The redraw lifecycle must clear pending state on success and controlled failure, retain the Tk image object for as long as it is displayed, and cancel or ignore callbacks after stop and close. Requested callback intervals are not delivered refresh-rate measurements.

## Validation boundary

Evaluate smoothing and display changes against deterministic landmark traces, tracking-loss and recovery cases, window resizing, repeated start and stop, and exact-head repository checks. Hardware observations should identify the exact commit, cameras, display environment, settings, and measurement method.

Current source, public documentation, repository tests, and exact-head validation take precedence over this historical note.
