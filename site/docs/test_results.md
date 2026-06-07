# End-to-End Test Results

This document captures the live test results for the Tony Stark Hand Control app at the time of the v1.0.0 release.

## Environment

| Item | Value |
|---|---|
| Host | `WIN-XXX` (Windows 10, 64-bit) |
| CPU | AMD Ryzen 7 5700X (8 cores) |
| RAM | 32 GB |
| GPU | NVIDIA RTX 5060 8GB (Blackwell sm_120) — *not used by MediaPipe (CPU only on Windows)* |
| Python | 3.14.0 |
| Cams | 4 webcams via DSHOW (indices 0-3) at 480x360 / 30 fps |
| Disk free | ~16 GB |

## Test suite: 77 / 77 PASS

```
$ python -m unittest discover tests -v

=== RoomMap ===                     12 PASS
=== HandProcessor ===               17 PASS
=== CameraManager ===               11 PASS
=== StereoCalibrator (synthetic) === 5 PASS
=== triangulate_point_rays ===       2 PASS
=== OllamaGestureRecognizer ===      2 PASS
=== HandControlApp construction === 28 PASS

=== SUMMARY: 77 passed, 0 failed ===
```

The full audit harness lives in `tests/test_app.py` and exercises:
- `RoomMap.add/remove/clear/save/load/nearest_within/invalid-type-fallback`
- `HandProcessor.smooth/predict/adjust/is_palm_open` (open, closed, mirrored Y, presets 1-5, worker cleanup)
- `CameraManager.release/is_feed_live` (empty, double-call, black, uniform, noisy, None, real cameras)
- `StereoCalibrator.is_calibrated/reconstruct_3d/save/load` (synthetic 2-cam rig)
- `triangulate_point_rays` (2 non-parallel rays, recovers the synthetic 3D point)
- `OllamaGestureRecognizer` circuit breaker (3 failures → 30s cooldown)
- Full `HandControlApp` construction with all 6 tabs, all state vars, `_apply_responsiveness`, `_set_attr`, anchor add, `on_close` cleanup

## Hot-path micro-benchmarks

```
$ python tests/test_perf_benchmark.py

detect() call time (no Fast Mode):   0.001 ms  (target: <1 ms)
detect() call time (Fast Mode 240p):  0.004 ms  (target: <1 ms)

End-to-end benchmark (60 calls, sleep 50ms between = ~20 calls/s effective):
60 calls in 3.53s (17.0 detect calls/s sustained)
```

The async MediaPipe worker means `detect()` is non-blocking on the GUI thread.

```
$ python tests/test_multistream_bench.py

Per-call draw_hud: 0.205ms median=0.199ms
Per-call frame.copy: 0.024ms median=0.021ms
Per-loop (4 cams): 0.9ms total

If 30 fps x 4 cams = 120 frames/sec, draw_hud alone uses:
  25ms/sec = 2.5% of one core
```

The HUD is the dominant per-frame cost in multi-cam. After the audit-pass-5 optimization (cache the static base, blit with `np.maximum`, only redraw the animated parts), it's down to 0.2ms per cam per frame.

## Live process behavior

The app, when started, holds:
- ~200 MB working-set memory
- 50-55 threads (Tk, MediaPipe worker, matplotlib refresh, selection overlay, Ollama worker if enabled, plus the Python runtime)
- ~3-5% of one CPU core at 4 cams × 30 fps with hand visible
- The MediaPipe inference itself is on a worker thread, so the GUI thread is never blocked

## Known limitations observed during testing

1. **MediaPipe GPU delegate unavailable on this Windows build.** The build flags disable GPU processing. Falls back to CPU (XNNPACK). ~30ms per inference.
2. **llama.cpp b9505+ is broken on the RTX 5060 Blackwell** for multimodal models (garbled first inference). The Ollama tab is off by default for this reason; users can enable it once a fix is upstream.
3. **MSMF backend returns black frames for the first few reads** while the sensor warms up. The auto-detect probe handles this by reading 5 frames and accepting on the last live frame.
4. **No GPU acceleration for OpenCV operations** on this host. All cv2 work is CPU. (PyTorch and onnxruntime-gpu are installed for future use; not currently exercised.)

## Reproducing these results

```bash
# Clone
git clone https://github.com/Capslockb/tony-stark-hand-control.git
cd tony-stark-hand-control

# Install
python install_wizard.py

# Run the full test suite
python -m unittest discover tests -v

# Or with pytest
pip install -r requirements-dev.txt
pytest -q
```

Expected output: 77 passed, 0 failed.
