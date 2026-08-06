# End-to-End Test Results

This document captures environment-specific live test results recorded for the Tony Stark Hand Control v1.0.0 release. It is a historical result, not a statement about the current `main` branch.

## Environment

| Item | Value |
|---|---|
| Host | `WIN-XXX` (Windows 10, 64-bit) |
| CPU | AMD Ryzen 7 5700X (8 cores) |
| RAM | 32 GB |
| GPU | NVIDIA RTX 5060 8GB (Blackwell sm_120) — *the MediaPipe GPU delegate was unavailable in this recorded run, so inference fell back to CPU* |
| Python | 3.14.0 |
| Cams | 4 webcams via DSHOW (indices 0-3) at 480x360 / 30 fps |
| Disk free | ~16 GB |

## Historical v1.0.0 result: 77 / 77 PASS

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

The original core audit harness lives in `tests/test_app.py` and exercises:
- `RoomMap.add/remove/clear/save/load/nearest_within/invalid-type-fallback`
- `HandProcessor.smooth/predict/adjust/is_palm_open` (open, closed, mirrored Y, presets 1-5, worker cleanup)
- `CameraManager.release/is_feed_live` (empty, double-call, black, uniform, noisy, None, real cameras)
- `StereoCalibrator.is_calibrated/reconstruct_3d/save/load` (synthetic 2-cam rig)
- `triangulate_point_rays` (2 non-parallel rays, recovers the synthetic 3D point)
- `OllamaGestureRecognizer` circuit breaker (3 failures → 30s cooldown)
- Full `HandControlApp` construction with all 6 tabs, all state vars, `_apply_responsiveness`, `_set_attr`, anchor add, `on_close` cleanup

Repository-wide coverage now includes additional regression and benchmark modules, so the current total is not expected to remain 77. The historical command above is retained only as part of the recorded v1.0.0 result; it is not the recommended current validation command.

## Hot-path micro-benchmarks

```
$ python tests/test_perf_benchmark.py

detect() call time (no Fast Mode):   0.001 ms  (target: <1 ms)
detect() call time (Fast Mode 240p):  0.004 ms  (target: <1 ms)

End-to-end benchmark (60 calls, sleep 50ms between = ~20 calls/s effective):
60 calls in 3.53s (17.0 detect calls/s sustained)
```

In this historical benchmark, the asynchronous MediaPipe worker made the `detect()` submission call non-blocking. That does not guarantee that the GUI thread can never block or that current `main` delivers recurring frames; the current loop-rescheduling regression is tracked in [Issue #16](https://github.com/Capslockb/tony-stark-hand-control/issues/16).

```
$ python tests/test_multistream_bench.py

Per-call draw_hud: 0.205ms median=0.199ms
Per-call frame.copy: 0.024ms median=0.021ms
Per-loop (4 cams): 0.9ms total

If 30 fps x 4 cams = 120 frames/sec, draw_hud alone uses:
  25ms/sec = 2.5% of one core
```

On this host and test configuration, the HUD was the dominant measured per-frame cost. After the audit-pass-5 optimization (cache the static base, blit with `np.maximum`, only redraw the animated parts), the recorded cost was about 0.2 ms per camera frame.

## Live process behavior

In this recorded run, the started application held:
- ~200 MB working-set memory
- 50-55 threads (Tk, MediaPipe worker, matplotlib refresh, selection overlay, Ollama worker if enabled, plus the Python runtime)
- ~3-5% of one CPU core at 4 cams × 30 fps with hand visible
- MediaPipe inference was submitted to a worker thread; this measurement does not establish end-to-end GUI responsiveness

## Known limitations observed during testing

1. **MediaPipe GPU delegate unavailable in this recorded Windows environment.** MediaPipe fell back to CPU (XNNPACK), with about 30 ms measured per inference. This is a host-specific observation, not a general Windows capability boundary.
2. **A June 2026 llama.cpp b9505+ run on the RTX 5060 Blackwell produced a garbled first multimodal inference.** Treat this as an environment-specific historical observation and verify current upstream behavior before relying on it.
3. **MSMF returned black frames for the first few reads on the tested cameras** while the sensors warmed up. The auto-detect probe handled this run by reading 5 frames and accepting the last live frame.
4. **No GPU acceleration was observed for OpenCV operations in this run.** Other installed acceleration runtimes were not exercised by this benchmark.

## Reproducing checks on the current branch

```bash
# Clone
git clone https://github.com/Capslockb/tony-stark-hand-control.git
cd tony-stark-hand-control

# Install
python install_wizard.py

# Run the pytest-style regression explicitly
python -m pytest -q tests/test_v100_hotfix.py

# Run deterministic assertion, smoke, demonstration, and benchmark scripts
python tests/test_predict_smoke.py
python tests/test_palm.py
python tests/test_palm_bug_demo.py
python tests/test_single_instance.py
python tests/test_perf_benchmark.py
python tests/test_multistream_bench.py
```

Run the live integration audit only on a machine with a graphical display and suitable camera access:

```bash
python tests/test_app.py
```

Do not use `python -m unittest discover tests -v` or an unfiltered `pytest` command for hosted or headless validation. Collection imports mixed-format modules, including scripts that perform work during import. See [`tests/README.md`](../tests/README.md) for the current execution boundary.

Use each command's final result and the GitHub Actions run for the exact commit as the source of truth. The current CI matrix is failing and is tracked in [Issue #3](https://github.com/Capslockb/tony-stark-hand-control/issues/3); the historical 77/77 result above must not be treated as current validation.
