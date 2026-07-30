# Historical Camera Troubleshooting Notes

This dated contributor note preserves earlier observations about Windows camera probing and handle lifecycle. It is not a current support matrix, driver recommendation, or validation report.

## Failure categories

An OpenCV capture may fail because the device is already in use, the selected index or backend is unsuitable, operating-system permissions block desktop applications, the driver is unavailable, or the device opens but does not return usable frames.

Camera indices and backend behavior vary by host. A configuration observed on one development machine must not be presented as a known-good default for other systems.

## Safe diagnostic sequence

1. Confirm that the camera works in the operating system's camera application.
2. Confirm current camera privacy settings, including desktop-application access where applicable.
3. Close other applications that may own the device.
4. Test the intended camera index and backend with a small program that always releases the capture handle.
5. Review current application logs and exact source behavior before changing probe order or thresholds.

## Handle lifecycle

Calibration, testing, tracking, stop, and close paths must have explicit ownership of each capture handle. A manager that opened a device should release it when that operation finishes unless ownership is deliberately transferred. Repeated release should be harmless.

Deterministic tests should use fake capture objects to verify release on success, failure, cancellation, and repeated stop or close operations. Real-device validation remains necessary for supported Windows backends.

## Warm-up and feed checks

Some cameras return unusable early frames while the backend and exposure settle. A bounded warm-up may reduce false rejection, but a fixed frame count is not a universal guarantee. Probe work also needs an application-level deadline, cancellation, and cleanup boundary; requesting backend timeout properties after construction does not bound a blocking `VideoCapture` constructor.

Feed-quality thresholds based on brightness or variance are heuristics. They should distinguish unreadable or clearly blank input without rejecting legitimate low-light scenes, and they require tests with synthetic frames plus controlled hardware validation.

Current source, public troubleshooting documentation, open issues, repository tests, and exact-head validation take precedence over this historical note.
