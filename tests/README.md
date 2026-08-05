# Tests

Regression, smoke, and micro-benchmark coverage for Tony Stark Hand Control.

The files under `tests/` are not all ordinary `unittest` modules. Some are executable benchmark scripts, and `tests/test_app.py` is a manual live-integration audit that performs camera, worker, network-adjacent, and Tk setup at module import time. Do not use unfiltered import-based discovery for hosted or headless validation.

## What's tested

| File | What | Notes |
|---|---|---|
| `test_app.py` | Core audit: RoomMap, HandProcessor, CameraManager, StereoCalibrator, triangulate_point_rays, OllamaGestureRecognizer, HandControlApp construction | Manual live integration. It probes real cameras and constructs Tk; run it directly only on a suitable GUI host with camera access. |
| `test_v100_hotfix.py` | Regression coverage for numpy scalar room anchors and Tk color normalization | Covers the v1.0.1 fixes. |
| `test_predict_smoke.py` | Predictor sanity: stationary vs moving landmarks, prediction horizon, decay curve | Focused regression module. |
| `test_palm.py` | `is_palm_open()` correctness: open, closed, partial, Y-flipped | Proves the Y-flip fix from audit pass 2. |
| `test_palm_bug_demo.py` | Demonstrates the old Y-flip bug and the corrected behavior | Pre/post comparison. |
| `test_single_instance.py` | Single-instance lock acquire/release/conflict | Prevents second-launch regressions. |
| `test_perf_benchmark.py` | Hot-path latency: `detect()`, Fast Mode, sustained throughput | Executable benchmark guard; run directly rather than through `unittest`. |
| `test_multistream_bench.py` | Multi-camera hot-path micro-benchmark: `draw_hud` cost and projected CPU use | Executable benchmark guard; run directly rather than through `unittest`. |

## Running

Run focused regression modules from the repository root. For example:

```bash
python -m unittest discover tests -v -p "test_v100_hotfix.py"
python -m unittest discover tests -v -p "test_predict_smoke.py"
python -m unittest discover tests -v -p "test_palm.py"
python -m unittest discover tests -v -p "test_single_instance.py"
```

Run benchmark-style guards as scripts:

```bash
python tests/test_perf_benchmark.py
python tests/test_multistream_bench.py
```

Run the live integration audit only on a machine with a graphical display and appropriate camera access:

```bash
python tests/test_app.py
```

Do not treat `python -m unittest discover tests -v` as a safe headless command: discovery imports every matching module, including scripts that perform work during import. The bounded CI runner and its exact-head workflow result are the source of truth for repository-wide hosted validation.

## With pytest

Install the development requirements and select focused regression modules explicitly. Avoid collecting the live audit or benchmark scripts as ordinary tests.

```bash
pip install -r requirements-dev.txt
pytest -q tests/test_v100_hotfix.py tests/test_predict_smoke.py tests/test_palm.py tests/test_single_instance.py
```

## Path resolution

The test modules under `tests/` resolve `tony_stark_hud_control.py` relative to their own location. Run commands from the repository root so imports, fixtures, and relative resources resolve consistently.

## Interpreting results

The exact test count can change as focused regression modules are added. Treat the command's final summary and the GitHub Actions run for the tested commit as the source of truth rather than copying a fixed repository-wide count into documentation.

A failure indicates either a regression or an environment-dependent prerequisite. Include the failing file, test name when available, platform, Python version, and traceback when opening an issue.

## Why deterministic tests avoid a GUI or real camera

- They run on Linux and Windows CI without webcam drivers.
- They can execute headlessly without opening the Tk main window.
- Synthetic inputs are deterministic and make failures reproducible.
- Hardware-dependent camera and visual checks remain in the separate manual live audit.
