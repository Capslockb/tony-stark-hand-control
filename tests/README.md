# Tests

Regression, smoke, and micro-benchmark coverage for Tony Stark Hand Control.

The original core audit in `test_app.py` contains 77 assertions. Repository-wide discovery also runs focused regression modules, so **77 is not the current total for the entire `tests/` directory**.

## What's tested

| File | What | Notes |
|---|---|---|
| `test_app.py` | 77-assertion core audit: RoomMap, HandProcessor, CameraManager, StereoCalibrator, triangulate_point_rays, OllamaGestureRecognizer, HandControlApp construction | Uses synthetic inputs for the core subsystems and does not require a real camera for the main audit path. |
| `test_v100_hotfix.py` | Regression coverage for numpy scalar room anchors and Tk color normalization | Covers the v1.0.1 fixes. |
| `test_predict_smoke.py` | Predictor sanity: stationary vs moving landmarks, prediction horizon, decay curve | |
| `test_palm.py` | `is_palm_open()` correctness: open, closed, partial, Y-flipped | Proves the Y-flip fix from audit pass 2. |
| `test_palm_bug_demo.py` | Demonstrates the old Y-flip bug and the corrected behavior | Pre/post comparison. |
| `test_single_instance.py` | Single-instance lock acquire/release/conflict | Prevents second-launch regressions. |
| `test_perf_benchmark.py` | Hot-path latency: `detect()`, Fast Mode, sustained throughput | Benchmark-style regression guard. |
| `test_multistream_bench.py` | Multi-camera hot-path micro-benchmark: `draw_hud` cost and projected CPU use | Benchmark-style regression guard. |

## Running

### All discovered tests

```bash
# From the repository root
python -m unittest discover tests -v
```

### A single test module

```bash
python -m unittest tests.test_app -v
```

### With pytest

```bash
pip install -r requirements-dev.txt
pytest -q
```

### With coverage

```bash
pytest --cov=tony_stark_hud_control --cov-report=term-missing
```

## Path resolution

The test modules under `tests/` resolve `tony_stark_hud_control.py` relative to their own location. They no longer require a developer-specific absolute path.

Run commands from the repository root so imports, fixtures, and relative resources resolve consistently:

```bash
git clone https://github.com/Capslockb/tony-stark-hand-control.git
cd tony-stark-hand-control
python -m unittest discover tests -v
```

## Interpreting results

The exact discovered-test count can change as focused regression modules are added. Treat the command's final summary and the GitHub Actions run for the tested commit as the source of truth rather than copying a fixed repository-wide count into documentation.

A failure indicates either a regression or an environment-dependent prerequisite. Include the failing test name, platform, Python version, and traceback when opening an issue.

## Why most tests avoid a GUI or real camera

- They run on Linux and Windows CI without webcam drivers.
- They can execute headlessly without opening the Tk main window.
- Synthetic inputs are deterministic and make failures reproducible.
- Hardware-dependent camera and visual checks remain separate from the deterministic core suite.
