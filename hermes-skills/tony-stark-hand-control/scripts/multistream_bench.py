"""Micro-benchmark for the multi-cam hot path: build a minimal
FakeApp, feed it synthetic frames for N cameras at M fps, measure
draw_hud cost and projected CPU utilization at the target frame rate.

Usage: python scripts/multistream_bench.py [path_to_main_script]

The default path is resolved from this repository's directory layout. The
script does NOT construct the real HandControlApp (it imports cv2 + MediaPipe
+ tkinter + matplotlib which takes ~6s) -- it uses a minimal FakeApp that has
just the methods the hot path needs.

Reports:
  - per-call draw_hud cost (median, p95)
  - per-call frame.copy() cost
  - per-loop cost for N cams
  - projected CPU% at the target frame rate (so you can tell
    at a glance whether the optimization is worth shipping)

Run before/after a draw_hud optimization to quantify the win.
"""

import os, sys, time, importlib.util
import numpy as np
import cv2

# ---- Configurable: change these to match your setup ----
N_CAMS = 4
FRAME_W = 480
FRAME_H = 360
N_TRIALS = 3
N_FRAMES_PER_TRIAL = 30  # 1 second at 30 fps


def load_module(path):
    spec = importlib.util.spec_from_file_location('m', path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class _L:
    __slots__ = ('x', 'y', 'z')
    def __init__(self, x, y, z=0):
        self.x, self.y, self.z = x, y, z


def synth_landmarks():
    """Build a 21-landmark hand. Tips at 5 positions, the rest
    pulled toward the wrist so the geometry is roughly valid."""
    lm = [_L(0.3, 0.5), _L(0.5, 0.5), _L(0.4, 0.5), _L(0.5, 0.5), _L(0.4, 0.5)]
    for _ in range(16):
        lm.append(_L(0.4, 0.4))
    return lm


def build_fake_app(m):
    """Build a minimal app with just the methods the hot path needs.
    Avoids importing the full HandControlApp (which pulls in tkinter,
    matplotlib, MediaPipe -- ~6 seconds)."""
    class FakeApp:
        def __init__(self, n_cams):
            self._hud_base_cache = {}
            # camera_vars are only needed if the loop path you're
            # benchmarking reads them. For draw_hud alone, not needed.
            self.camera_vars = []
            self.hand_proc = None  # not used by draw_hud
        def draw_hud(self, frame, landmarks):
            return m.HandControlApp.draw_hud(self, frame, landmarks)
        def _build_hud_base(self, h, w):
            return m.HandControlApp._build_hud_base(self, h, w)
    return FakeApp(N_CAMS)


def main():
    script_path = (
        os.path.abspath(sys.argv[1])
        if len(sys.argv) > 1
        else os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', '..', '..', 'tony_stark_hud_control.py'))
    )
    if not os.path.exists(script_path):
        print(f'ERROR: script not found: {script_path}')
        sys.exit(1)

    print(f'Loading {script_path}...')
    m = load_module(script_path)
    print(f'Loaded. Module has {len([k for k in dir(m) if not k.startswith("_")])} symbols.')
    print()

    app = build_fake_app(m)
    lm = synth_landmarks()

    # Pre-generate frames OUTSIDE the timed loop. This is the
    # critical micro-bench hygiene from audit_2026_06_04_pass5.md
    # -- np.random.rand(...).astype(uint8) is ~5ms and will
    # drown the cv2 work you're trying to measure.
    print(f'Pre-generating {N_CAMS} x {N_FRAMES_PER_TRIAL} frames '
          f'at {FRAME_W}x{FRAME_H}...')
    frames = [(np.random.rand(FRAME_H, FRAME_W, 3) * 255).astype(np.uint8)
              for _ in range(N_CAMS * N_FRAMES_PER_TRIAL)]

    # Warmup
    print('Warming up...')
    for f in frames[:3]:
        app.draw_hud(f.copy(), lm)

    # Real measurement
    times_hud = []
    times_copy = []
    times_loop = []
    print(f'Benchmarking {N_TRIALS} trials x {N_FRAMES_PER_TRIAL} frames '
          f'x {N_CAMS} cams...')
    for trial in range(N_TRIALS):
        t_loop0 = time.perf_counter()
        for i, frame in enumerate(frames):
            t_c0 = time.perf_counter()
            display = frame.copy()
            times_copy.append((time.perf_counter() - t_c0) * 1000)
            t_h0 = time.perf_counter()
            app.draw_hud(display, lm)
            times_hud.append((time.perf_counter() - t_h0) * 1000)
        times_loop.append((time.perf_counter() - t_loop0) * 1000)
        print(f'  trial {trial + 1}: {times_loop[-1]:.1f}ms total')

    print()
    print('=== Results ===')
    print(f'  draw_hud: median={np.median(times_hud):.3f}ms '
          f'p95={np.percentile(times_hud, 95):.3f}ms '
          f'max={max(times_hud):.3f}ms')
    print(f'  frame.copy: median={np.median(times_copy):.3f}ms')
    print(f'  per-loop ({N_CAMS} cams): {np.mean(times_loop):.1f}ms')
    print()
    target_fps_per_cam = 30
    total_calls_per_sec = N_CAMS * target_fps_per_cam
    hud_ms_per_sec = np.median(times_hud) * total_calls_per_sec
    hud_pct_core = hud_ms_per_sec / 10  # 1000ms = 100% of one core
    print(f'  At {target_fps_per_cam} fps x {N_CAMS} cams = {total_calls_per_sec} calls/sec:')
    print(f'    draw_hud: {hud_ms_per_sec:.0f}ms/sec = {hud_pct_core:.1f}% of one core')
    print()
    # Verdict
    if hud_pct_core < 5:
        print('  >>> draw_hud cost is negligible. Don\'t optimize further.')
    elif hud_pct_core < 20:
        print('  >>> draw_hud cost is acceptable. Focus on other hot-path items.')
    elif hud_pct_core < 50:
        print('  >>> draw_hud cost is significant. Worth optimizing.')
    else:
        print('  >>> draw_hud cost is the dominant cost. MUST optimize.')


if __name__ == '__main__':
    main()
