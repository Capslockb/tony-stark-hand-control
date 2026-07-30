# Historical Accessibility Overlay Notes

This dated contributor note preserves design context for the Windows focus-highlight overlays. It is not a current platform-support guarantee or validation report.

## Design boundary

The application has used two related Tkinter overlays:

- a transient full-screen cue after focus-navigation gestures;
- a persistent border around the currently focused control.

Both rely on a borderless, topmost `Toplevel`. On Windows, extended window styles may be used to keep the overlay out of the taskbar and allow pointer input to pass through it. The persistent overlay obtains a candidate focused-control rectangle through Win32 focus APIs and refreshes it on a Tk timer.

## Durable implementation lessons

- Transparent-window behavior depends on the Tk build, compositor, and Windows APIs. Visual display does not by itself prove that pointer input passes through the overlay.
- Win32 structures must be initialized with the correct size before focus information is requested.
- Timer callbacks must be cancelled during stop and close paths.
- Overlay geometry must account for small controls, multiple monitors, missing focus information, and controls that expose only an inner rectangle.
- Tk image and window work must stay on the Tk thread.
- Requested timer intervals are scheduling targets, not measured refresh rates.

## Validation boundary

Validate overlay behavior on the exact supported Windows build with ordinary mouse input, keyboard focus navigation, multiple monitors where supported, and repeated start/stop cycles. Confirm that the overlay does not capture pointer input, create orphan callbacks, or remain visible after shutdown.

Current source, public documentation, repository tests, and exact-head validation take precedence over this historical note.
