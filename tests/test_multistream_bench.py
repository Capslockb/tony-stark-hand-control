"""Benchmark the hot path: simulate 4 cameras at 30 fps, run the
main loop logic, measure CPU/system time. Repeat 10x for noise."""
import os, sys, time, importlib.util
import numpy as np
import cv2

spec = importlib.util.spec_from_file_location(
    'm', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tony_stark_hud_control.py')))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# Build a minimal fake app with just the methods we need
class FakeApp:
    def __init__(self, n_cams=4):
        self.camera_vars = [type('V', (), {'get': lambda self=None: True})()
                            for _ in range(n_cams)]
        self.hand_proc = m.HandProcessor.__new__(m.HandProcessor)
        m.HandProcessor.__init__(self.hand_proc)
        # Wait for the worker to warm up by submitting a few frames
        warmup = (np.random.rand(360, 480, 3) * 255).astype(np.uint8)
        warmup_bgr = cv2.cvtColor(warmup, cv2.COLOR_RGB2BGR)
        for _ in range(5):
            self.hand_proc.detect(warmup_bgr)
        self._frame_counter = 0
        self._live_cache = {}
        self._fps_cache = {}
        self._cached_landmarks = {}
        self._last_displays = {}
        self._hud_base_cache = {}
        # Fake camera manager
        self.camera_mgr = type('CM', (), {
            'read_all': lambda self: [(True, (np.random.rand(360, 480, 3) * 255).astype(np.uint8))
                                       for _ in range(n_cams)],
            'is_feed_live': lambda self, ret, frame: True,
            'get_actual_fps': lambda self, i: 30.0,
        })()
    def draw_hud(self, frame, landmarks):
        return m.HandControlApp.draw_hud(self, frame, landmarks)
    def _build_hud_base(self, h, w):
        return m.HandControlApp._build_hud_base(self, h, w)

app = FakeApp(4)

# Warm up
raw = app.camera_mgr.read_all()
for _ in range(3):
    app._frame_counter += 1
    run_mp = (app._frame_counter % 1 == 0)
    app._last_displays = {} if run_mp else app._last_displays
    for i, (ret, frame) in enumerate(raw):
        if not ret:
            continue
        if run_mp:
            det = app.hand_proc.detect(frame)
            landmarks = det.hand_landmarks[0] if det and det.hand_landmarks else None
            app._cached_landmarks[i] = landmarks
        else:
            landmarks = app._cached_landmarks.get(i)
        display = app._last_displays.get(i)
        if display is None or run_mp:
            display = frame.copy()
        if landmarks:
            app.draw_hud(display, landmarks)
        app._last_displays[i] = display

# Measure: 4 cams x 30 fps x 1 second = 120 frames
# Use synthetic landmarks (the worker is async so we don't have
# real ones in time for the benchmark -- what we want to measure
# is the draw_hud cost with realistic landmark data, anyway).
class _L:
    __slots__ = ('x', 'y', 'z')
    def __init__(self, x, y, z=0): self.x, self.y, self.z = x, y, z
synth_lm = [_L(0.3, 0.5), _L(0.5, 0.5), _L(0.4, 0.5), _L(0.5, 0.5), _L(0.4, 0.5),
            _L(0.4, 0.4), _L(0.4, 0.4), _L(0.4, 0.4), _L(0.4, 0.4), _L(0.4, 0.4),
            _L(0.4, 0.4), _L(0.4, 0.4), _L(0.4, 0.4), _L(0.4, 0.4), _L(0.4, 0.4),
            _L(0.4, 0.4), _L(0.4, 0.4), _L(0.4, 0.4), _L(0.4, 0.4), _L(0.4, 0.4),
            _L(0.4, 0.4)]

times_draw_hud = []
times_loop = []
times_frame_copy = []

# Warmup
for _ in range(3):
    display = (np.random.rand(360, 480, 3) * 255).astype(np.uint8)
    app.draw_hud(display, synth_lm)

# Real measurement: 30 frames of 4 cams = 120 draws
N_CAMS = 4
for trial in range(3):
    t_loop_start = time.perf_counter()
    for i, (ret, frame) in enumerate(raw):
        if not ret:
            continue
        t_copy0 = time.perf_counter()
        display = frame.copy()
        times_frame_copy.append((time.perf_counter() - t_copy0) * 1000)
        t_h0 = time.perf_counter()
        app.draw_hud(display, synth_lm)
        times_draw_hud.append((time.perf_counter() - t_h0) * 1000)
    t_loop = (time.perf_counter() - t_loop_start) * 1000
    times_loop.append(t_loop)
    print(f'  trial {trial+1}: {t_loop:.1f}ms ({N_CAMS} cams, 1 frame each)')

print()
print(f'Per-call draw_hud: {np.mean(times_draw_hud):.3f}ms median={np.median(times_draw_hud):.3f}ms')
print(f'Per-call frame.copy: {np.mean(times_frame_copy):.3f}ms median={np.median(times_frame_copy):.3f}ms')
print(f'Per-loop (4 cams): {np.mean(times_loop):.1f}ms total')
print()
print(f'If 30 fps x 4 cams = 120 frames/sec, draw_hud alone uses:')
print(f'  {np.mean(times_draw_hud) * 120:.0f}ms/sec = {np.mean(times_draw_hud) * 120 / 10:.1f}% of one core')
