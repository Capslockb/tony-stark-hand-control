"""Benchmark: measure the main loop time with and without the optimizations.

The key question: is detect() now actually non-blocking?

We simulate the main loop with a real BGR frame and time how long
detect() takes (in the calling thread). If our worker thread is
working, detect() should return in <1ms regardless of how slow the
actual MediaPipe inference is.

Also measure end-to-end throughput: how many frames/sec can we
process if the worker keeps up."""
import time
import numpy as np
import cv2
import importlib.util
spec = importlib.util.spec_from_file_location(
    'm', r'C:/Users/Bernardo/tony_stark_hand_control/tony_stark_hud_control.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


hp = m.HandProcessor.__new__(m.HandProcessor)
m.HandProcessor.__init__(hp)

# Use a synthetic frame (random noise so MediaPipe doesn't lock on)
frame = (np.random.rand(360, 480, 3) * 255).astype(np.uint8)
frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

# Wait for the worker to do its first detection
print('Warming up worker...')
hp.detect(frame_bgr)
time.sleep(0.5)  # let worker process

# Benchmark detect() call time (should be sub-ms if non-blocking)
N = 200
t0 = time.perf_counter()
for _ in range(N):
    hp.detect(frame_bgr)
elapsed = (time.perf_counter() - t0) / N * 1000
print(f'detect() call time (no Fast Mode):  {elapsed:6.3f} ms  (target: <1 ms)')

# With Fast Mode enabled
hp.fast_mode = True
t0 = time.perf_counter()
for _ in range(N):
    hp.detect(frame_bgr)
elapsed = (time.perf_counter() - t0) / N * 1000
print(f'detect() call time (Fast Mode 240p): {elapsed:6.3f} ms  (target: <1 ms)')

# Measure actual end-to-end throughput
print('\nEnd-to-end benchmark (60 calls, sleep 50ms between = ~20 calls/s effective):')
hp.fast_mode = False
t0 = time.perf_counter()
for i in range(60):
    hp.detect(frame_bgr)
    time.sleep(0.05)  # simulate the camera read time
# Wait for the worker to drain
time.sleep(0.5)
elapsed = time.perf_counter() - t0
print(f'60 calls in {elapsed:.2f}s ({60/elapsed:.1f} detect calls/s sustained)')

# Cleanup
hp._stop_worker = True
time.sleep(0.6)
print('Worker stopped.')
