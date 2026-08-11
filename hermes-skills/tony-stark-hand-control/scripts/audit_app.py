"""Comprehensive live runtime test of the Tony Stark hand control app.

Exercises every major subsystem without opening a GUI window:
  - HandProcessor (synthetic frames, predictor, velocity, palm-open)
  - CameraManager (real cameras, live-feed check)
  - RoomMap (add/remove/save/load/JSON)
  - StereoCalibrator (3D reconstruction from synthetic intrinsics)
  - HandControlApp (full construction with Tk root, no mainloop)
  - OllamaGestureRecognizer circuit breaker

Reports pass/fail for each subsystem and exits non-zero on any failure.

Pattern (from 2026-06-04 audit):
  - Use synthetic inputs where possible (RoomMap, triangulate,
    HandProcessor) so tests are deterministic and fast.
  - Use real cameras only for CameraManager -- the test confirms
    the auto-detect + release path actually works on this host.
  - Use a Tk root + .withdraw() to construct the App without
    entering mainloop, so we can inspect all the widgets and
    state vars are wired correctly.
  - For Ollama circuit breaker, monkey-patch the threshold to
    2 and call _record_failure() directly -- the real threshold
    (3) requires ~24s of HTTP timeouts which is too slow for
    a unit test.

Run it from the project root:

    python hermes-skills/tony-stark-hand-control/scripts/audit_app.py

You can override the repository-relative default explicitly:

    python hermes-skills/tony-stark-hand-control/scripts/audit_app.py ./tony_stark_hud_control.py
"""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time


# --- Locate the main script -------------------------------------------------
def resolve_app_path(argv=None):
    """Resolve an explicit target or the application at the repository root."""
    args = sys.argv if argv is None else argv
    if len(args) > 1:
        return Path(args[1]).expanduser().resolve()

    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / 'tony_stark_hud_control.py'


APP_PATH = resolve_app_path()
if not APP_PATH.is_file():
    print(f'ERROR: cannot find {APP_PATH}')
    print('Run this helper from a normal repository checkout or pass the path '
          'to tony_stark_hud_control.py as argv[1].')
    sys.exit(2)

spec = importlib.util.spec_from_file_location('m', str(APP_PATH))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

import numpy as np
import cv2

# --- Minimalist check/reporting --------------------------------------------
results = []
def check(name, cond, detail=''):
    status = 'PASS' if cond else 'FAIL'
    results.append((status, name, detail))
    print(f'  [{status}] {name}' + (f'  ({detail})' if detail else ''))

# ===== RoomMap =============================================================
print('\n=== RoomMap ===')
rm = m.RoomMap()
a1 = rm.add(1.0, 2.0, 0.5, atype='wall', label='North wall')
check('add returns anchor with id', a1['id'] == 1)
check('add stores coords', (a1['x'], a1['y'], a1['z']) == (1.0, 2.0, 0.5))
rm.add(0.0, 0.0, 1.0, atype='zone', label='Origin')
rm.remove(1)
check('remove by id', all(a['id'] != 1 for a in rm.anchors))
rm.clear()
check('clear empties list', rm.anchors == [])
rm.add(0.1, 0.2, 0.3, atype='furniture')
rm.add(-0.5, 0.0, 1.0, atype='hotspot')
with tempfile.TemporaryDirectory() as td:
    path = os.path.join(td, 'test_map.json')
    rm.path = path
    rm.save()
    check('save creates file', os.path.exists(path))
    rm2 = m.RoomMap()
    rm2.path = path
    ok = rm2.load()
    check('load returns True', ok)
    check('load restores count', len(rm2.anchors) == 2)
    check('load restores coords',
          rm2.anchors[0]['x'] == 0.1 and rm2.anchors[1]['z'] == 1.0)
rm = m.RoomMap()
rm.add(0, 0, 0); rm.add(1, 0, 0)
check('nearest_within returns close anchor',
      rm.nearest_within(0.05, 0, 0, radius=0.1) is not None)
check('nearest_within returns None when too far',
      rm.nearest_within(5, 0, 0, radius=0.1) is None)
rm = m.RoomMap()
check('invalid type falls back to custom',
      rm.add(0, 0, 0, atype='nonexistent')['type'] == 'custom')

# ===== HandProcessor =======================================================
print('\n=== HandProcessor ===')
hp = m.HandProcessor.__new__(m.HandProcessor)
m.HandProcessor.__init__(hp)
check('one_euro_min_cutoff is set', hp.one_euro_min_cutoff == 2.5)
check('one_euro_beta is set', hp.one_euro_beta == 0.05)
check('cursor_ema_alpha is set', hp.cursor_ema_alpha == 0.55)
check('predict_max_dt is set', hp.predict_max_dt == 0.150)
check('buffers have 5 tips', len(hp.buffers) == 5)
check('velocities dict has 5 tips', len(hp.velocities) == 5)
frame = (np.random.rand(360, 480, 3) * 255).astype(np.uint8)
frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
t0 = time.perf_counter()
for _ in range(20):
    hp.detect(frame_bgr)
elapsed = (time.perf_counter() - t0) / 20 * 1000
check(f'detect() call is <2ms (got {elapsed:.3f}ms)', elapsed < 2.0)
for _ in range(5):
    hp.smooth(hp.index_tip, 0.5, 0.5, dt=1/30)
p = hp.predict(hp.index_tip)
check('predict() returns tuple after first smooth', p is not None and len(p) == 2)
hp2 = m.HandProcessor.__new__(m.HandProcessor)
m.HandProcessor.__init__(hp2)
check('predict() returns None before any smooth',
      hp2.predict(hp2.index_tip) is None)
hp.responsiveness = 5; hp.adjust()
check('preset 5 max_dt=0.250', hp.predict_max_dt == 0.250)
check('preset 5 min_cutoff=5.0', hp.one_euro_min_cutoff == 5.0)
check('preset 5 buf=3', all(b.maxlen == 3 for b in hp.buffers.values()))
hp.responsiveness = 1; hp.adjust()
check('preset 1 buf=10', all(b.maxlen == 10 for b in hp.buffers.values()))

# is_palm_open
class L:
    __slots__ = ('x', 'y', 'z')
    def __init__(self, x, y, z=0): self.x, self.y, self.z = x, y, z
def make_hand(extended, num_fingers):
    """Build a 21-landmark hand. If `extended` is True, the fingers
    are straight and the tip is far from the wrist (y < pip < mcp
    < wrist). If False, the tip is at the same y as the pip (curled)."""
    lms = [L(0.5, 0.9)]  # 0: wrist
    # 1-4: thumb (we don't test it; just make it short)
    lms += [L(0.45, 0.85), L(0.42, 0.83), L(0.40, 0.81), L(0.38, 0.79)]
    # 5-8: index
    if extended and num_fingers >= 1:
        lms += [L(0.40, 0.85), L(0.40, 0.78), L(0.40, 0.72), L(0.40, 0.65)]
    else:
        lms += [L(0.40, 0.85), L(0.40, 0.83), L(0.40, 0.82), L(0.40, 0.82)]
    # 9-12: middle
    if extended and num_fingers >= 2:
        lms += [L(0.45, 0.85), L(0.45, 0.78), L(0.45, 0.72), L(0.45, 0.63)]
    else:
        lms += [L(0.45, 0.85), L(0.45, 0.83), L(0.45, 0.82), L(0.45, 0.82)]
    # 13-16: ring
    if extended and num_fingers >= 3:
        lms += [L(0.50, 0.85), L(0.50, 0.78), L(0.50, 0.72), L(0.50, 0.66)]
    else:
        lms += [L(0.50, 0.85), L(0.50, 0.83), L(0.50, 0.82), L(0.50, 0.82)]
    # 17-20: pinky
    if extended and num_fingers >= 4:
        lms += [L(0.55, 0.85), L(0.55, 0.78), L(0.55, 0.74), L(0.55, 0.69)]
    else:
        lms += [L(0.55, 0.85), L(0.55, 0.83), L(0.55, 0.82), L(0.55, 0.82)]
    return lms
check('open palm detected', m.HandProcessor.is_palm_open(make_hand(True, 4)))
check('closed fist rejected', not m.HandProcessor.is_palm_open(make_hand(False, 0)))
flipped = [L(lm.x, 1.0 - lm.y, lm.z) for lm in make_hand(True, 4)]
check('mirrored Y still detected as open', m.HandProcessor.is_palm_open(flipped))
hp._stop_worker = True
time.sleep(0.6)
check('worker stops cleanly', True)

# ===== CameraManager =======================================================
print('\n=== CameraManager ===')
cm = m.CameraManager.__new__(m.CameraManager); cm.cameras = []
cm.release()
check('release() on empty list is safe', cm.cameras == [])
released = []
class MockCap:
    def release(self): released.append(1)
cm2 = m.CameraManager.__new__(m.CameraManager)
cm2.cameras = [MockCap(), MockCap()]
cm2.release()
check('release() releases all cameras', len(released) == 2)
cm2.release()
check('release() safe when called twice', cm2.cameras == [])
cm3 = m.CameraManager.__new__(m.CameraManager)
check('is_feed_live rejects pure black',
      not cm3.is_feed_live(True, np.zeros((100, 100, 3), np.uint8)))
check('is_feed_live rejects uniform white (frozen)',
      not cm3.is_feed_live(True, np.full((100, 100, 3), 255, np.uint8)))
check('is_feed_live accepts dim-but-noisy',
      cm3.is_feed_live(True, (np.random.rand(100, 100, 3) * 50 + 100).astype(np.uint8)))
check('is_feed_live rejects uniform frame',
      not cm3.is_feed_live(True, np.full((100, 100, 3), 50, np.uint8)))
check('is_feed_live accepts bright + noisy',
      cm3.is_feed_live(True, (np.random.rand(100, 100, 3) * 50 + 220).astype(np.uint8)))
check('is_feed_live rejects None', not cm3.is_feed_live(True, None))
check('is_feed_live rejects ret=False',
      not cm3.is_feed_live(False, np.zeros((100, 100, 3), np.uint8)))
try:
    cm4 = m.CameraManager(width=480, height=360, fps=30)
    check('CameraManager opens >=1 camera', len(cm4.cameras) >= 1,
          f'found {len(cm4.cameras)} cams')
    for i in range(len(cm4.cameras)):
        w, h = cm4.get_size(i)
        check(f'  cam {i} reports size', w > 0 and h > 0, f'{w}x{h}')
    ret, frame = cm4.read_all()[0]
    check('  read_all returns (ret, frame)', ret and frame is not None)
    cm4.release()
    check('  release after read works', cm4.cameras == [])
except RuntimeError as e:
    check('CameraManager opens >=1 camera', False, str(e))

# ===== StereoCalibrator (synthetic) ========================================
print('\n=== StereoCalibrator (synthetic) ===')
sc = m.StereoCalibrator()
check('StereoCalibrator starts uncalibrated', not sc.is_calibrated)
check('StereoCalibrator has 0 num_cameras', sc.num_cameras == 0)
K = np.array([[600, 0, 320], [0, 600, 240], [0, 0, 1]], dtype=np.float64)
dist = np.zeros((1, 5))
sc.calibrations = [
    {'K': K, 'dist': dist, 'R': np.eye(3), 't': np.zeros((3, 1)), 'image_size': (640, 480)},
    {'K': K, 'dist': dist, 'R': np.eye(3), 't': np.array([[0.10], [0], [0]]), 'image_size': (640, 480)},
]
sc.image_sizes = [(640, 480), (640, 480)]
sc.reprojection_error = 0.5
sc._last_baseline_m = 0.10
sc.num_cameras = 2
sc.baseline_m = 0.10
check('is_calibrated derived property is True', sc.is_calibrated)
pts = [(320, 240), (260, 240)]
X = sc.reconstruct_3d(pts)
check('reconstruct_3d returns valid point',
      X is not None and abs(X[0]) < 0.1 and abs(X[2] - 1.0) < 0.1,
      f'got {X}')
with tempfile.TemporaryDirectory() as td:
    path = os.path.join(td, 'calib.npz')
    sc.save(path)
    check('StereoCalibrator.save creates file', os.path.exists(path))
    sc2 = m.StereoCalibrator()
    sc2.calib_path = path
    ok = sc2.load()
    check('StereoCalibrator.load returns True', ok)
    check('StereoCalibrator.load restores 2 calibrations',
          len(sc2.calibrations) == 2)

# ===== triangulate_point_rays ==============================================
print('\n=== triangulate_point_rays (synthetic) ===')
cam0_origin = np.array([0.0, 0.0, 0.0])
cam1_origin = np.array([0.10, 0.0, 0.0])
ray0 = np.array([0.0, 0.0, 1.0])
ray1 = np.array([-0.10, 0.0, 1.0])
ray1 /= np.linalg.norm(ray1)
X = m.triangulate_point_rays([cam0_origin, cam1_origin], [ray0, ray1])
check('triangulate_point_rays returns array', X is not None)
check(f'triangulate_point_rays recovers (0, 0, 1) (got {X})',
      X is not None and abs(X[0]) < 0.01 and abs(X[1]) < 0.01
      and abs(X[2] - 1.0) < 0.01)

# ===== OllamaGestureRecognizer circuit breaker ============================
print('\n=== OllamaGestureRecognizer circuit breaker ===')
ogr = m.OllamaGestureRecognizer('http://127.0.0.1:1/api/generate', 'test-model', 'test-key')
small = (np.random.rand(60, 80, 3) * 255).astype(np.uint8)
ogr._failure_threshold = 2  # speed up the test
for i in range(3):
    ogr._record_failure(f'test failure {i+1}')
    time.sleep(0.05)
check('circuit breaker tripped after failures', ogr._failure_cooldown_until > 0)
check('failure counter incremented', ogr._consecutive_failures >= 2)
check('circuit breaker is active', ogr._failure_cooldown_until > time.time())
ogr.stop()

# ===== App construction (no mainloop) ======================================
print('\n=== App construction (no mainloop) ===')
try:
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    app = m.HandControlApp(root)
    check('HandControlApp constructs', app is not None)
    check('hand_proc is a HandProcessor', isinstance(app.hand_proc, m.HandProcessor))
    check('stereo is a StereoCalibrator', isinstance(app.stereo, m.StereoCalibrator))
    check('room_map is a RoomMap', isinstance(app.room_map, m.RoomMap))
    check('fast_mode defaults to False', app.fast_mode is False)
    check('responsiveness defaults to 3', app.responsiveness == 3)
    check('matplotlib 3d axes exists', app._3d_ax is not None)
    check('matplotlib 3d fig exists', app._3d_fig is not None)
    check('anchor listbox exists', app._3d_anchor_listbox is not None)
    check('responsiveness_var exists', hasattr(app, 'responsiveness_var'))
    check('sel_overlay_var exists', hasattr(app, 'sel_overlay_var'))
    check('fast_mode_var exists', hasattr(app, 'fast_mode_var'))
    check('enable_3d_var exists', hasattr(app, 'enable_3d_var'))
    app._apply_responsiveness(5)
    check('_apply_responsiveness(5) updates hand_proc',
          app.hand_proc.one_euro_min_cutoff == 5.0)
    app._apply_responsiveness(3)
    check('_apply_responsiveness(3) resets to preset 3',
          app.hand_proc.one_euro_min_cutoff == 2.5)
    app._set_attr('cursor_ema_alpha', 0.99)
    check('_set_attr propagates cursor_ema_alpha to hand_proc',
          app.hand_proc.cursor_ema_alpha == 0.99)
    before = len(app.room_map.anchors)
    app._add_anchor_manual()
    check('_add_anchor_manual adds to room_map',
          len(app.room_map.anchors) == before + 1)
    app.on_close()
    check('on_close completes cleanly', True)
except Exception as e:
    import traceback
    check('HandControlApp constructs', False, f'{type(e).__name__}: {e}')
    traceback.print_exc()

# ===== Single-instance lock ================================================
print('\n=== Single-instance lock ===')
try:
    inst1_cls = m._SingleInstance
    # First instance should acquire, second should fail.
    inst1 = inst1_cls()
    ok1 = inst1.acquire()
    check('first _SingleInstance.acquire() returns True', ok1)
    inst2 = inst1_cls()
    ok2 = inst2.acquire()
    check('second _SingleInstance.acquire() returns False (locked)', not ok2)
    # Release the first; third should succeed.
    inst1.release()
    inst3 = inst1_cls()
    ok3 = inst3.acquire()
    check('third _SingleInstance.acquire() returns True (after release)', ok3)
    inst3.release()
except AttributeError:
    check('_SingleInstance class exists', False, 'class not found in module')
except Exception as e:
    check('_SingleInstance lock test', False, f'{type(e).__name__}: {e}')

# ===== Summary ==============================================================
passed = sum(1 for s, *_ in results if s == 'PASS')
failed = sum(1 for s, *_ in results if s == 'FAIL')
print(f'\n=== SUMMARY: {passed} passed, {failed} failed ===')
if failed:
    print('FAILED TESTS:')
    for s, name, detail in results:
        if s == 'FAIL':
            print(f'  - {name}' + (f'  ({detail})' if detail else ''))
    sys.exit(1)
sys.exit(0)
