"""Smoke test: build a HandProcessor, feed it a moving landmark, and verify
that predict() extrapolates correctly between detections."""
import os, time, math
import importlib.util
spec = importlib.util.spec_from_file_location(
    'm', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tony_stark_hud_control.py')))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

hp = m.HandProcessor.__new__(m.HandProcessor)
m.HandProcessor.__init__(hp)

# Test 1: defaults
print(f'defaults: min_cutoff={hp.one_euro_min_cutoff} beta={hp.one_euro_beta} '
      f'alpha={hp.cursor_ema_alpha} buf=6 max_dt={hp.predict_max_dt}')

# Test 2: feed a stationary landmark
tip = hp.index_tip
for i in range(5):
    p = hp.smooth(tip, 0.5, 0.5, dt=1/30)
    time.sleep(1/30)
print(f'after 5 stationary frames: predict(t) = {hp.predict(tip)}')
# Should be ~(0.5, 0.5) with zero velocity
assert abs(hp.predict(tip)[0] - 0.5) < 0.01, 'stationary drift detected'
assert abs(hp.predict(tip)[1] - 0.5) < 0.01, 'stationary drift detected'

# Test 3: feed a moving landmark, then predict forward
prev_t = time.time()
for i in range(5):
    x = 0.5 + i * 0.01  # moving right at ~0.3 normalized units/sec
    p = hp.smooth(tip, x, 0.5, dt=1/30)
    time.sleep(1/30)
# Now ask for the position 50ms in the future
future = hp.predict(tip, now=time.time() + 0.05)
print(f'after 5 right-moving frames: predict(+50ms) = {future}')
# Should be slightly to the right of the last filtered position
print(f'  velocity estimate = {hp.velocities[tip]}')
# Velocity should be positive x
assert hp.velocities[tip][0] > 0, 'velocity should be positive in x'
# Predicted x should be > last filtered x (the predictor should extrapolate)
last_filtered = hp.filtered[tip][0]
assert future[0] > last_filtered, (
    f'predict should extrapolate forward (filtered={last_filtered}, '
    f'predicted={future[0]})')

# Test 4: predict_max_dt caps the extrapolation
far_future = hp.predict(tip, now=time.time() + 5.0)
print(f'predict(+5s) = {far_future}  (should be capped near current)')
# Should not run away (max ~0.25s worth of extrapolation past current)

# Test 5: apply responsiveness preset 5 (1:1) and re-check
hp.responsiveness = 5
hp.adjust()
print(f'preset 5: min_cutoff={hp.one_euro_min_cutoff} beta={hp.one_euro_beta} '
      f'alpha={hp.cursor_ema_alpha} max_dt={hp.predict_max_dt} buf_maxlen={hp.buffers[tip].maxlen}')
assert hp.buffers[tip].maxlen == 3
assert hp.predict_max_dt == 0.250

# Test 6: preset 1 (smooth)
hp.responsiveness = 1
hp.adjust()
print(f'preset 1: min_cutoff={hp.one_euro_min_cutoff} beta={hp.one_euro_beta} '
      f'alpha={hp.cursor_ema_alpha} max_dt={hp.predict_max_dt} buf_maxlen={hp.buffers[tip].maxlen}')
assert hp.buffers[tip].maxlen == 10
assert hp.predict_max_dt == 0.080

print('ALL SMOKE TESTS PASSED')
