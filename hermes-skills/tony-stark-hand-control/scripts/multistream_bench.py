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
