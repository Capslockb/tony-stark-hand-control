# Camera Troubleshooting for Tony Stark Hand Control

## Common Issues on Windows

### Error: "Warning: Empty frame received."
This indicates that OpenCV can open the camera but cannot read frames from it. Common causes:

1. **Camera being used by another application** - Close other apps that might be using the webcam (Zoom, Teams, Camera app, etc.)
2. **Wrong camera index** - Some systems have multiple cameras (built-in + external); the default index 0 might not be the correct one
3. **Backend incompatibility** - Different OpenCV backends work differently on various Windows configurations

### Solutions Implemented in Current Version

The `tony_stark_hud_control.py` script now includes robust camera initialization that:
1. Tries known good settings first (camera index 1 with CAP_DSHOW backend, which worked in testing)
2. Falls back to trying all combinations of indices (0,1,2) and backends (CAP_DSHOW, CAP_MSMF, CAP_V4L2, CAP_ANY)
3. Includes a failure counter that exits after 30 consecutive empty frames

### Manual Troubleshooting Steps

If you continue to experience issues, try these steps:

1. **Test your camera with a simple script:**
   ```python
   import cv2
   cap = cv2.VideoCapture(0)  # Try 0, 1, 2 if this fails
   if cap.isOpened():
       ret, frame = cap.read()
       if ret:
           print(f"Camera works! Frame shape: {frame.shape}")
       else:
           print("Opened but cannot read frames")
       cap.release()
   else:
       print("Cannot open camera")
   ```

2. **Try different backends explicitly:**
   ```python
   # Try DirectShow (often works well on Windows)
   cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
   
   # Try MSMF
   cap = cv2.VideoCapture(0, cv2.CAP_MSMF)
   
   # Try default
   cap = cv2.VideoCapture(0)
   ```

3. **Check camera permissions in Windows Settings:**
   - Go to Settings → Privacy & security → Camera
   - Ensure "Camera access" is turned on
   - Ensure "Let apps access your camera" is enabled
   - Check that Python/OpenCV has permission

4. **Update or reinstall camera drivers:**
   - Open Device Manager
   - Expand "Cameras" or "Imaging devices"
   - Right-click your camera → Update driver or Uninstall device (then restart to reinstall)

5. **Check for Windows updates** that might include camera driver fixes

### Known Working Configurations (from testing)

- Camera index 1 with CAP_DSHOW backend (OpenCV videoio flag 700)
- Some systems work with index 0 and CAP_DSHOW
- External webcams often appear at higher indices

### Environment Variables

You can force a specific camera by modifying the script or setting environment variables, but the current implementation tries multiple options automatically.

### When All Else Fails

If no camera works:
1. Test with the Windows Camera app to verify hardware functionality
2. Try a different USB port if using an external webcam
3. Consider using a smartphone as a webcam with apps like DroidCam or iVCam as a last resort

## Camera handle leaks (calibration → Start sequence)

If your app opens cameras for **calibration** and then the user clicks **Start** to run tracking, **the calibration-time handles can leak** unless you explicitly release them. Symptoms: only one camera appears after Start, or OpenCV returns "device busy" errors. Fix:

1. Add a `release()` method to your CameraManager:
   ```python
   def release(self):
       for cap in self.cameras:
           try: cap.release()
           except Exception: pass
       self.cameras = []
   ```

2. In `Start()` (which opens a fresh CameraManager), always release the previous one first:
   ```python
   if self.camera_mgr is not None:
       self.camera_mgr.release()
       self.camera_mgr = None
   self.camera_mgr = CameraManager(...)
   ```

3. In `Calibrate()`, track whether you opened the cameras yourself (vs. reusing the user's already-open ones), and release them after calibration completes — otherwise the next Start() will see stale handles.

4. Call `release()` on `Stop()` and on window-close so the OS reclaims the handles.

This was a real bug found in the 2026-06 audit — calibration would open cameras and never let go, then Start() would either fail to open them or open a *second* set that fought the first for the same device.

## MSMF warm-up frame bug (cams added then immediately blacklisted)

**Symptom:** Console prints `Auto-detected camera N` for several cams, but the GUI shows all-black feeds. Status bar says "feed not live." Cycling Stop/Start doesn't help.

**Root cause:** `CameraManager._find_cameras` was reading only the **first** frame per camera before accepting it. The MSMF backend (default on Windows 10/11) returns near-black frames for the first 1-5 reads while the sensor warms up and auto-exposure settles. The cam got added, then `is_feed_live` correctly flagged every subsequent read as "frozen / black" and the per-cam auto-blacklist kicked in.

**Fix in `_find_cameras`:** Read **5 frames** and only accept the cam if the LAST frame is live (i.e. passes the std/brightness check):

```python
last_good = False
for _ in range(5):
    ret, frame = cap.read()
    if not ret or frame is None:
        continue
    if self.is_feed_live(True, frame):
        last_good = True
if last_good:
    found.append(cap)
    break  # keep the cap; this backend works
cap.release()  # else: try next backend
```

**Why this is correct, not a hack:** the *first* frame of a cam is genuinely unreliable across all backends (not just MSMF) — driver init, USB enumeration, AE settle all happen after `cap.open()`. Reading N warm-up frames before committing to the cam is a standard pattern. The 5-frame threshold is conservative; you can reduce to 3 once you're confident in your hardware.

**Verification:** `scripts/audit_app.py` includes a CameraManager live-feed check section that exercises pure-black, uniform-white, dim-noisy, bright-noisy, None, and ret=False inputs.