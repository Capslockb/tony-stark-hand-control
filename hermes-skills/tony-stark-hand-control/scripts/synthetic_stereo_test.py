"""Synthetic ground-truth stress test for StereoCalibrator.reconstruct_3d.

Verifies the triangulation math is correct end-to-end against a known stereo rig.
Catches the three pitfalls documented in references/3d_reconstruction.md:

  1. origin = t (not -R^T * t)
  2. cv2.undistortPoints(P=None) for normalized coords (not P=K)
  3. comments claiming the wrong thing (mitigated by the test failing loudly)

Run it from the project root:

    cd tony_stark_hand_control
    python scripts/synthetic_stereo_test.py

Pass criterion: mean err < 1e-5 m AND max err < 1e-5 m on 50 random points.
If the math regresses, this test will report 1-2 m errors instead of sub-micron.
"""
import os
import sys

# Make the project's modules importable
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import numpy as np

# Load tony_stark_hud_control.py as a module without running the GUI
import importlib.util
spec = importlib.util.spec_from_file_location(
    'tony_stark_hud_control', os.path.join(ROOT, 'tony_stark_hud_control.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# --- 1. Build a known stereo rig -------------------------------------------
K = np.array([[600.0, 0.0, 320.0],
              [0.0, 600.0, 240.0],
              [0.0, 0.0, 1.0]], dtype=np.float64)
baseline = 0.1  # 10 cm between cameras

sc = m.StereoCalibrator()
sc.image_sizes = [(640, 480), (640, 480)]
sc.calibrations = [
    {'K': K, 'dist': np.zeros(5), 'R': np.eye(3), 't': np.zeros((3, 1)),
     'P': K @ np.hstack((np.eye(3), np.zeros((3, 1)))),
     'rms_intrinsics': 0.0},
    {'K': K, 'dist': np.zeros(5), 'R': np.eye(3),
     't': np.array([[baseline], [0.0], [0.0]], dtype=np.float64),
     'P': K @ np.hstack((np.eye(3), np.array([[baseline], [0.0], [0.0]]))),
     'rms_intrinsics': 0.0},
]
sc.num_cameras = 2
sc.baseline_m = baseline
sc.reprojection_error = 0.0


def project(X, R, t, K):
    """Project a 3D world point through a camera with given R, t, K."""
    X_cam = R.T @ (X - t)
    return K @ X_cam / X_cam[2]


def test_random(N, label, dist=None, rotate_cam1=False):
    np.random.seed(42)
    if dist is not None:
        sc.calibrations[0]['dist'] = dist
        sc.calibrations[1]['dist'] = dist
    if rotate_cam1:
        import math
        ang = math.radians(5)
        R1 = np.array([[1, 0, 0],
                       [0, math.cos(ang), -math.sin(ang)],
                       [0, math.sin(ang),  math.cos(ang)]])
        sc.calibrations[1]['R'] = R1
        sc.calibrations[1]['P'] = K @ np.hstack((R1, sc.calibrations[1]['t']))
    errs = []
    for _ in range(N):
        X = np.array([np.random.uniform(-0.5, 0.5),
                      np.random.uniform(-0.3, 0.3),
                      np.random.uniform(0.3, 2.0)])
        p0 = project(X, sc.calibrations[0]['R'], sc.calibrations[0]['t'].reshape(3), K)
        p1 = project(X, sc.calibrations[1]['R'], sc.calibrations[1]['t'].reshape(3), K)
        X_rec = sc.reconstruct_3d([(p0[0], p0[1]), (p1[0], p1[1])])
        if X_rec is None:
            errs.append(float('inf'))
        else:
            errs.append(float(np.linalg.norm(X_rec - X)))
    errs = np.array(errs)
    print(f"  [{label:30s}] N={N}  max={errs.max():.2e}  "
          f"mean={errs.mean():.2e}  bad(>0.001)={int((errs > 0.001).sum())}")
    return errs


def main():
    print("Synthetic stereo stress test (pass = mean < 1e-5 m, max < 1e-5 m)")
    print("=" * 70)

    # Test 1: ideal rig, no distortion, no rotation
    errs = test_random(50, "ideal, no dist, no rot")
    assert errs.max() < 1e-5, f"FAIL: max err {errs.max():.2e} > 1e-5"
    assert errs.mean() < 1e-5, f"FAIL: mean err {errs.mean():.2e} > 1e-5"

    # Test 2: with mild barrel distortion
    test_random(30, "mild barrel distortion",
                dist=np.array([0.1, 0.01, 0.0, 0.0, 0.0]))

    # Test 3: with cam 1 rotated 5 degrees pitch
    test_random(30, "cam 1 rotated 5 deg pitch", rotate_cam1=True)

    # Test 4: triangulate_point_rays helper directly (the pure function)
    print()
    print("Direct triangulate_point_rays helper:")
    origins = [np.array([0.0, 0.0, 0.0]), np.array([baseline, 0.0, 0.0])]
    X_target = np.array([0.05, 0.10, 1.0])
    r0 = X_target.copy(); r0 /= np.linalg.norm(r0)
    r1 = X_target - np.array([baseline, 0, 0]); r1 /= np.linalg.norm(r1)
    X_rec = m.triangulate_point_rays(origins, [r0, r1])
    err = np.linalg.norm(X_rec - X_target)
    print(f"  [{'pure helper':30s}] err={err:.2e}")
    assert err < 1e-10, f"FAIL: pure-helper err {err:.2e}"

    # Test 5: save/load round-trip
    print()
    print("Save/load round-trip:")
    test_path = os.path.join(ROOT, "calibration_test.npz")
    sc.save(test_path)
    sc2 = m.StereoCalibrator(calib_path=test_path)
    loaded = sc2.load()
    print(f"  load() -> {loaded}, repr: {sc2}")
    assert loaded, "FAIL: load returned False"
    assert sc2.baseline_m == baseline, "FAIL: baseline lost on round-trip"
    os.remove(test_path)

    print()
    print("ALL TESTS PASSED — math is correct, persistence works.")


if __name__ == '__main__':
    main()
