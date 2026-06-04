# Tests

Regression suite for Tony Stark Hand Control. 77 assertions, all currently passing.

## What's tested

| File | What | Notes |
|---|---|---|
| `test_app.py` | 77 assertions: RoomMap, HandProcessor, CameraManager, StereoCalibrator, triangulate_point_rays, OllamaGestureRecognizer, HandControlApp construction | The main regression test. Self-contained — no real camera or GUI required (synthetic inputs). |
| `test_predict_smoke.py` | Predictor sanity: stationary vs moving landmarks, prediction horizon, decay curve | |
| `test_palm.py` | `is_palm_open()` correctness: open, closed, partial, Y-flipped | Proves the Y-flip fix from audit pass 2 |
| `test_palm_bug_demo.py` | Demonstrates the old Y-flip bug existed and is now fixed | Pre/post comparison |
| `test_single_instance.py` | Single-instance lock acquire/release/conflict | Prevents second-launch regression |
| `test_perf_benchmark.py` | Hot-path latency: `detect()`, Fast Mode, sustained throughput | Catches performance regressions |
| `test_multistream_bench.py` | Multi-cam hot-path micro-benchmark: `draw_hud` cost, projected CPU% | Catches HUD regressions |

## Running

### All tests (recommended)

```bash
# From the repo root
python -m unittest discover tests -v
```

### A single test file

```bash
python -m unittest tests.test_app -v
```

### With pytest (faster, better output)

```bash
pip install -r requirements-dev.txt
pytest -q
```

### With coverage

```bash
pytest --cov=tony_stark_hud_control --cov-report=term-missing
```

## Path resolution

The test files use a hardcoded path to find the main app:

```python
r'C:/Users/Bernardo/tony_stark_hand_control/tony_stark_hud_control.py'
```

This works on the developer's machine. If you cloned this repo to a different location, either:

1. Update the path in each test file, OR
2. Add a `conftest.py` that sets the path, OR
3. Run the tests from inside the repo so a relative path works:

```python
# conftest.py at the repo root
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
```

## Expected results

```
=== SUMMARY: 77 passed, 0 failed ===
```

A failing test indicates a regression. Open a GitHub issue with the test output.

## Why no GUI / no real camera in the test suite?

- The test suite runs on any platform (Linux CI, macOS, Windows) without webcam drivers
- It runs in headless mode (no Tk window) — important for CI in containers
- It runs in seconds, not minutes
- Synthetic inputs are deterministic, so test failures are reproducible

The app itself is tested manually (and visually) by running `tony_stark_hud_control.py` and clicking around.
