# Multi-Camera Fusion for Hand Tracking

## Theory
Using multiple cameras from different angles improves hand tracking accuracy by:
1. Reducing occlusion issues (if one camera misses a fingertip due to angle, another might see it)
2. Providing more data points for averaging, reducing noise
3. Enabling 3D position estimation when cameras are calibrated (though current implementation uses normalized 2D averaging)

## Implementation in tony_stark_hud_control.py

### Camera Setup
The `HandHUD.__init__` method accepts `camera_configs` - a list of tuples `(index, backend)`.
- If `None` or empty list: auto-detects a single working camera
- If provided: attempts to open each camera with specified backend

### Frame Processing
1. `capture_frames()`: grabs a frame from each camera
2. `process_hands()`: runs MediaPipe HandLandmarker on each frame
3. `fuse_landmarks()`: averages normalized landmarks across cameras that detected a hand

### Landmark Fusion Algorithm
For each landmark index (0-20):
```
sum_x[idx] += landmark.x from each camera that detected the hand
sum_y[idx] += landmark.y from each camera that detected the hand
sum_z[idx] += landmark.z from each camera that detected the hand
count[idx] += 1 for each detection

avg_x[idx] = sum_x[idx] / count[idx]   (if count[idx] > 0)
avg_y[idx] = sum_y[idx] / count[idx]
avg_z[idx] = sum_z[idx] / count[idx]
```

### Benefits Observed
- More stable tracking when one camera has poor lighting or occlusion
- Reduced jitter due to averaging
- Better handling of partial hand visibility

### Limitations
- Cameras are not geometrically calibrated, so fusion is in normalized image coordinates only
- Assumes hands are in similar positions across camera views (works for front + side views)
- Increases CPU usage linearly with number of cameras

## Configuration Tips
1. Use cameras with similar fields of view and mounting heights
2. Ensure good lighting in all camera views
3. Test each camera individually first using the troubleshooting guide
4. Start with 2 cameras (front + side) before adding more
5. Monitor performance; each additional camera increases processing time

## Troubleshooting Multi-Camera Issues
- If only one camera works: check indices and backends for non-working cameras
- If fused tracking seems worse: one camera may be providing noisy data; try disabling it
- If performance is low: reduce camera resolution or limit to 2 cameras