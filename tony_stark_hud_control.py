# Tony Stark HUD Hand Control - Multi-Camera, GUI, Accessibility-Focus, 3D-Aware
#
# Architecture overview
# ----------------------
# The app has four cooperating layers:
#
#   1. Camera layer (CameraManager)
#       - Auto-detects up to 6 cameras via DirectShow/MSMF
#       - Configures each for max FPS, low buffer, and an explicit resolution
#       - Reads frames and runs a live-feed check (rejects black/frozen/blank)
#       - Per-camera enable flag is owned by the GUI
#
#   2. Vision layer (HandProcessor)
#       - MediaPipe HandLandmarker in VIDEO mode with monotonically-increasing
#         timestamps
#       - One-Euro filter + 6-frame moving average per fingertip
#       - is_palm_open() heuristic for the engage gesture
#
#   3. 3D layer (StereoCalibrator + triangulation)
#       - Calibrates each camera's intrinsics (K, dist) from a printed 9x6
#         checkerboard held in front of the cameras
#       - Then runs cv2.stereoCalibrate to compute a SHARED extrinsics so
#         camera 0 and camera 1 live in the same 3D world frame
#       - During runtime, undistorts the 2D hand landmark, normalizes it via
#         K^-1, and triangulates with the shared [R|t] of each camera using a
#         weighted least-squares SVD solver
#       - Calibration is persisted to disk (calibration.npz) so the user
#         doesn't have to recalibrate every restart
#
#   4. UI layer (HandControlApp + Tkinter)
#       - 5-tab notebook (Main / Ollama / Tracking / Accessibility / Cameras)
#       - Mouse cursor disabled by default; swipes drive Tab/Shift+Tab/Arrow
#         focus navigation
#       - Full-screen Toplevel overlay (built lazily) draws a green border
#         and big "Focus: LEFT/RIGHT/UP/DOWN" text on every swipe
#
# Key features
# ------------
#   - Multi-camera fusion with FPS maximization per camera
#   - Per-camera HUD overlays (rotating rings, pulsating circles, arcs, atom)
#   - Unified GUI window (Tkinter) with camera toggles, start/stop, calibration
#   - Auto camera-feed validation (rejects frozen / black / blank feeds)
#   - Intent detection (open palm held for ~0.6 s) before any input is read
#   - Full stereo calibration with shared world frame and undistorted 3D
#   - Accessibility integration: swipes drive focus navigation; overlay flashes
#   - Optional OllamaCloud gesture recognition (disabled by default to keep
#     the GUI responsive on slow networks)
#   - PyAutoGUI fail-safe disabled; cursor clamped to safe margins
#   - Desktop shortcut creator (run with --create-shortcut)

import cv2
import mediapipe as mp
import pyautogui
import numpy as np
import math
import random
import os
import sys
import urllib.request
import time
import base64
import requests
import json
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from collections import deque
from PIL import Image, ImageTk

# Disable PyAutoGUI fail-safe
pyautogui.FAILSAFE = False

# MediaPipe
mp_tasks = mp.tasks
mp_vision = mp.tasks.vision

# ----------------------------- Model Download -----------------------------
def download_model():
    model_path = 'hand_landmarker.task'
    if not os.path.exists(model_path):
        print('Downloading hand landmarker model...')
        urllib.request.urlretrieve(
            'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',
            model_path
        )
        print('Model downloaded')
    return model_path

# ----------------------------- Ollama Recognizer -----------------------------
DEFAULT_OLLAMA_PROMPT = (
    "What hand gesture is being shown? Choose from: left_click, right_click, "
    "scroll_up, scroll_down, swipe_left, swipe_right, swipe_up, swipe_down, "
    "move_cursor, engage, disengage, none. Respond with only the gesture name."
)
GESTURE_KEYS = ['left_click', 'right_click', 'scroll_up', 'scroll_down',
                'swipe_left', 'swipe_right', 'swipe_up', 'swipe_down',
                'move_cursor', 'engage', 'disengage', 'none']

# ----------------------------- Room Map -----------------------------
#
# An interactive 3D room map: a list of named "anchors" in the shared
# world frame, each with a 3D position (x, y, z in metres), a type
# (wall, zone, hotspot, etc.), and a label. The user can add anchors
# in three ways:
#
#   1. Click in the 3D viewport (matplotlib picks the ray-plane
#      intersection at the user's chosen z height).
#   2. "Use live hand position" button -- records the 3D position
#      of the index fingertip at the moment the button was pressed.
#   3. Manual entry of x, y, z coordinates.
#
# The map is saved/loaded to a JSON file so the user doesn't have to
# re-create it every session.
DEFAULT_ROOM_MAP_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else '.',
    'room_map.json')


class RoomMap:
    """List of named 3D anchors + helpers for hit-testing and picking."""

    ANCHOR_TYPES = ('wall', 'zone', 'hotspot', 'furniture', 'custom')

    def __init__(self):
        self.anchors = []  # list of dicts: {name, x, y, z, type, label}
        self.next_id = 1
        self.path = DEFAULT_ROOM_MAP_PATH

    def add(self, x, y, z, atype='custom', label=None):
        if atype not in self.ANCHOR_TYPES:
            atype = 'custom'
        if label is None or not str(label).strip():
            label = f"{atype}_{self.next_id}"
        # Coerce numpy 0-d arrays to Python floats (e.g. when called
        # from _pick_3d_at which gets 0-d ndarray from matplotlib's
        # proj3d.inv_transform). Without this, float(np.float64) on
        # Python 3.13+ raises TypeError: only 0-dimensional arrays
        # can be converted to Python scalars.
        self.anchors.append({
            'id': self.next_id,
            'name': label,
            'x': float(np.asarray(x).item()),
            'y': float(np.asarray(y).item()),
            'z': float(np.asarray(z).item()),
            'type': atype,
        })
        self.next_id += 1
        return self.anchors[-1]

    def remove(self, anchor_id):
        self.anchors = [a for a in self.anchors if a['id'] != anchor_id]

    def clear(self):
        self.anchors = []

    def to_dict(self):
        return {
            'next_id': self.next_id,
            'anchors': list(self.anchors),
        }

    def from_dict(self, d):
        self.anchors = list(d.get('anchors', []))
        self.next_id = int(d.get('next_id', max((a['id'] for a in self.anchors), default=0) + 1))

    def save(self, path=None):
        import json
        path = path or self.path
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        self.path = path

    def load(self, path=None):
        import json
        path = path or self.path
        try:
            with open(path, 'r') as f:
                self.from_dict(json.load(f))
            self.path = path
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False

    def nearest_within(self, x, y, z, radius=0.20):
        """Return the anchor nearest to (x, y, z), or None if no anchor
        is within `radius` metres. Used by click-to-pick in the 3D view."""
        best = None
        best_d2 = radius * radius
        for a in self.anchors:
            dx, dy, dz = a['x'] - x, a['y'] - y, a['z'] - z
            d2 = dx*dx + dy*dy + dz*dz
            if d2 <= best_d2:
                best = a
                best_d2 = d2
        return best

class OllamaGestureRecognizer:
    def __init__(self, endpoint, model, api_key, prompt=None):
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key
        self.prompt = prompt or DEFAULT_OLLAMA_PROMPT
        self.latest_gesture = None
        self.lock = threading.Lock()
        self.queue = queue.Queue(maxsize=1)
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        self.last_query_time = 0
        self.query_cooldown = 0.5
        # Circuit breaker: after this many consecutive failures, the
        # worker stops submitting requests for `cooldown` seconds so
        # the queue doesn't fill with doomed requests that all hit
        # the 8s timeout in series. Resets on the next success.
        self._consecutive_failures = 0
        self._failure_threshold = 3
        self._failure_cooldown_until = 0.0

    def _worker(self):
        while True:
            frame_b64 = self.queue.get()
            if frame_b64 is None:
                break
            # Honour the circuit breaker: if we're in cooldown, drop
            # this frame and reset the queue.
            if time.time() < self._failure_cooldown_until:
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    pass
                continue
            try:
                resp = requests.post(self.endpoint, json={
                    "model": self.model,
                    "prompt": self.prompt,
                    "images": [frame_b64],
                    "stream": False
                }, headers={"Authorization": f"Bearer {self.api_key}"}, timeout=8)
                if resp.status_code == 200:
                    result = resp.json()
                    gesture = result.get('response', '').strip().lower()
                    for key in GESTURE_KEYS:
                        if key in gesture:
                            gesture = key
                            break
                    else:
                        gesture = 'none'
                    with self.lock:
                        self.latest_gesture = gesture
                    # Reset failure counter on success
                    self._consecutive_failures = 0
                else:
                    self._record_failure(f"Ollama error: {resp.status_code} {resp.text[:100]}")
            except Exception as e:
                self._record_failure(f"Ollama exception (throttled): {e}")

    def _record_failure(self, msg):
        """Increment failure counter, print throttled, and trip the
        circuit breaker if the threshold is hit. Once tripped, the
        worker will stop submitting requests for 30 seconds."""
        self._consecutive_failures += 1
        last = getattr(self, '_last_ollama_err_print', 0)
        if time.time() - last > 30:
            print(msg + f"  (failure {self._consecutive_failures}/{self._failure_threshold})")
            self._last_ollama_err_print = time.time()
        if self._consecutive_failures >= self._failure_threshold:
            self._failure_cooldown_until = time.time() + 30.0
            print(f"Ollama circuit breaker tripped -- 30s cooldown")

    def submit_frame(self, frame):
        now = time.time()
        if now - self.last_query_time < self.query_cooldown:
            return
        # Don't even enqueue during circuit-breaker cooldown
        if now < self._failure_cooldown_until:
            return
        self.last_query_time = now
        _, buffer = cv2.imencode('.jpg', frame)
        b64 = base64.b64encode(buffer).decode('utf-8')
        if self.queue.full():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass
        self.queue.put(b64)

    def get_gesture(self):
        with self.lock:
            return self.latest_gesture

    def stop(self):
        self.queue.put(None)
        self.thread.join(timeout=1)

# ----------------------------- Camera Manager -----------------------------
class CameraManager:
    def __init__(self, camera_configs=None, width=640, height=480, fps=30):
        """Open every working camera at the requested resolution/fps.
        The GUI's per-camera Enable checkbox is the only thing that gates
        which feeds are processed; auto-blacklist covers black/no-signal feeds."""
        self.cameras = []
        self.configs = camera_configs or []
        target_w, target_h, target_fps = width, height, fps
        if not self.configs:
            self.cameras = self._find_cameras(target_w, target_h, target_fps)
        else:
            for idx, backend in self.configs:
                cap = cv2.VideoCapture(idx, backend)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FPS, target_fps)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    cap.set(3, target_w)
                    cap.set(4, target_h)
                    ret, _ = cap.read()
                    if ret:
                        self.cameras.append(cap)
                        print(f"  Camera {idx} opened (backend={backend}) @ {target_w}x{target_h} {target_fps}fps")
                    else:
                        cap.release()
        if not self.cameras:
            raise RuntimeError("No cameras available")
        # Track per-camera index mapping
        self.index_map = list(range(len(self.cameras)))

    def _find_cameras(self, w, h, fps):
        found = []
        # Probe indices 0..5; include any that actually deliver a
        # non-black frame. Some backends (MSMF especially) return
        # black frames for the first ~5 reads while the sensor warms
        # up and auto-exposure settles, so we read 5 frames and only
        # accept the cam if the LAST one is actually live.
        #
        # Performance: without the OPEN/READ timeouts, probing a
        # non-existent camera index on Windows can block for 30+
        # seconds (the webcam driver waits for hardware that isn't
        # there). With the timeouts, the worst-case probe time is
        # ~5 seconds (4 indices x ~1s for the DSHOW try + fast
        # fallthrough for indices that aren't there). This is what
        # was causing the "extreme lag when pressing Start" -- the
        # GUI thread was blocked inside CameraManager.__init__.
        open_timeout_ms = 1500   # time to wait for cap.open()
        read_timeout_ms = 800    # time to wait for cap.read()
        for idx in range(4):
            opened = False
            for backend in [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]:
                if opened and backend != cv2.CAP_DSHOW:
                    # DSHOW already worked, no need to try other backends
                    break
                cap = cv2.VideoCapture(idx, backend)
                if not cap.isOpened():
                    cap.release()
                    continue
                # Set the timeouts BEFORE the read attempts. On
                # OpenCV 4.5+ this prevents the cap from blocking
                # forever on a non-existent device.
                try:
                    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, open_timeout_ms)
                    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, read_timeout_ms)
                except Exception:
                    pass  # older OpenCV without these props
                cap.set(cv2.CAP_PROP_FPS, fps)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(3, w)
                cap.set(4, h)
                # Read a few frames to flush warm-up / auto-exposure
                last_good = False
                for _ in range(3):
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        continue
                    if self.is_feed_live(True, frame):
                        last_good = True
                if last_good:
                    found.append(cap)
                    print(f"  Auto-detected camera {idx} (backend={backend}) @ {w}x{h} {fps}fps")
                    opened = True
                    break
                cap.release()
        return found

    def read_all(self):
        results = []
        for cap in self.cameras:
            ret, frame = cap.read()
            results.append((ret, frame))
        return results

    def release(self):
        """Release all open camera handles. Safe to call multiple times."""
        for cap in self.cameras:
            try:
                cap.release()
            except Exception:
                pass
        self.cameras = []

    def is_feed_live(self, ret, frame, min_std=0.5, min_brightness=0.2):
        """Live-feed check: rejects truly FROZEN/BLACK feeds, but tolerates
        dim scenes. A covered lens produces a near-uniform frame with
        std ~= 0 and brightness close to 0; that's what we want to reject.
        A dim but live scene (e.g. dark room with a hand) can easily have
        std >= 1 and brightness < 1, and we WANT to keep that.

        Defaults are very permissive so we don't accidentally drop
        working cameras that just have a low-light scene. Override with
        higher thresholds if you want stricter filtering."""
        if not ret or frame is None:
            return False
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        std = np.std(gray)
        brightness = np.mean(gray)
        if std < min_std or brightness < min_brightness:
            return False
        return True

    def get_actual_fps(self, cam_index):
        """Read CAP_PROP_FPS for a camera; some drivers lie and report 0.
        Returns the value the driver reports, or the configured default."""
        if cam_index < 0 or cam_index >= len(self.cameras):
            return 30.0
        fps = self.cameras[cam_index].get(cv2.CAP_PROP_FPS)
        if not fps or fps < 1:
            return 30.0
        return float(fps)

    def get_width(self, cam_index):
        """Return the actual frame width for a camera, querying the driver."""
        if cam_index < 0 or cam_index >= len(self.cameras):
            return 0
        w = self.cameras[cam_index].get(cv2.CAP_PROP_FRAME_WIDTH)
        return int(w) if w else 0

    def get_height(self, cam_index):
        """Return the actual frame height for a camera, querying the driver."""
        if cam_index < 0 or cam_index >= len(self.cameras):
            return 0
        h = self.cameras[cam_index].get(cv2.CAP_PROP_FRAME_HEIGHT)
        return int(h) if h else 0

    def get_size(self, cam_index):
        """Return (w, h) for a camera. Convenience helper."""
        return (self.get_width(cam_index), self.get_height(cam_index))

# ----------------------------- Hand Processor -----------------------------
class HandProcessor:
    def __init__(self):
        model_path = download_model()
        # Try GPU delegate first (delegate=1), fall back to CPU (delegate=0)
        delegate_to_use = 0  # default CPU
        try:
            from mediapipe.tasks import python as _mp_python
            gpu_opts = _mp_python.BaseOptions(model_asset_path=model_path, delegate=_mp_python.BaseOptions.Delegate.GPU)
            test_det = mp_vision.HandLandmarker.create_from_options(
                mp_vision.HandLandmarkerOptions(
                    base_options=gpu_opts,
                    running_mode=mp_vision.RunningMode.VIDEO,
                    num_hands=1))
            test_det.close()
            delegate_to_use = 1
            print("HandProcessor: GPU delegate ACTIVE")
        except Exception as e:
            print(f"HandProcessor: GPU delegate unavailable -> CPU ({type(e).__name__})")
            delegate_to_use = 0
        try:
            base_options = mp_tasks.BaseOptions(
                model_asset_path=model_path,
                delegate=getattr(mp_tasks.BaseOptions.Delegate,
                                 'GPU' if delegate_to_use == 1 else 'CPU'))
        except Exception:
            # Older MediaPipe without the Delegate enum
            base_options = mp_tasks.BaseOptions(model_asset_path=model_path)
        options = mp_vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.7,
            min_hand_presence_confidence=0.7,
            min_tracking_confidence=0.7)
        self.detector = mp_vision.HandLandmarker.create_from_options(options)
        self.thumb_tip = 4
        self.index_tip = 8
        self.middle_tip = 12
        self.ring_tip = 16
        self.pinky_tip = 20
        self.palm_indices = [0, 1, 5, 9, 13, 17]
        # Smaller smoothing window: 6 frames at 30fps = 0.2s — cuts phase delay
        # so the cursor feels snappier and synced to reality.
        self.buffers = {i: deque(maxlen=6) for i in [self.thumb_tip, self.index_tip,
                                                    self.middle_tip, self.ring_tip,
                                                    self.pinky_tip]}
        # Per-fingertip One-Euro-style filtered position (in normalized coords)
        self.filtered = {i: None for i in self.buffers.keys()}
        # Cursor EMA state (in screen pixels) for extra smoothness
        self.cursor_ema = None
        self._last_frame_ts = 0
        # One-Euro filter parameters. Defaults are conservative (smooth);
        # the GUI sliders can override these at runtime via _set_attr.
        self.one_euro_min_cutoff = 2.5  # lower = smoother, higher = more responsive
        self.one_euro_beta = 0.05        # higher = more speed-adaptive
        self.cursor_ema_alpha = 0.55     # blend factor for screen cursor EMA
        # ---- Motion prediction (dead-reckoning) ----
        # Per-tip velocity in normalized image coords per second, estimated
        # from the last 3 smooth() calls. Used to extrapolate the landmark
        # forward in time so the cursor/controls feel 1:1 with the hand
        # even between MediaPipe detections.
        self.velocities = {i: (0.0, 0.0) for i in self.buffers.keys()}
        self._vel_history = {i: deque(maxlen=3) for i in self.buffers.keys()}
        self._last_smooth_ts = {i: 0.0 for i in self.buffers.keys()}
        # Predicted (x, y, ts) for each tip -- this is what gesture code
        # should read. smooth() updates the prediction as new detections
        # come in; predict() extrapolates to the requested wall-clock time.
        self.predicted = {i: (0.0, 0.0, 0.0) for i in self.buffers.keys()}
        # Hard cap on how far we'll predict forward (seconds). Beyond this
        # we snap to the last known position to avoid runaway extrapolation
        # after the user has actually stopped moving.
        self.predict_max_dt = 0.150
        # Responsiveness preset. 1 = smooth, 5 = 1:1. The Tracking tab
        # slider writes this and adjust() applies the preset.
        self.responsiveness = 3
        # ---- Async inference worker (background thread) ----
        # detect() enqueues a frame and returns the most-recent
        # finished result. The main thread (Tk) never blocks on the
        # MediaPipe inference, so the GUI stays smooth at 60+ FPS even
        # though the model takes 20-30ms per frame on CPU.
        import queue as _queue
        import threading as _threading
        self._infer_q = _queue.Queue(maxsize=2)  # small -- drop frames if backed up
        self._last_result = None
        self._inference_pending = False
        self._stop_worker = False
        self._result_lock = _threading.Lock()
        self._infer_thread = _threading.Thread(target=self._inference_worker,
                                               daemon=True)
        self._infer_thread.start()

    def detect(self, frame):
        """Submit a frame to the inference worker thread (non-blocking)
        and return the latest cached result. The first call returns
        None (no previous result), subsequent calls return whatever
        the worker has most recently finished."""
        # Drop the request on the floor if the worker is backed up
        if self._inference_pending:
            return self._last_result
        self._inference_pending = True
        try:
            # Pre-process on the calling (main) thread, since these
            # numpy ops are GIL-released and run in <1ms anyway.
            # Optional pre-downscale for the Fast Mode toggle (set via
            # the Tracking tab): at 320x240 MediaPipe's internal
            # model forward pass is ~30% cheaper than at 480x360.
            if self.fast_mode and frame.shape[0] > 240:
                scale = 240.0 / frame.shape[0]
                new_w = int(frame.shape[1] * scale)
                frame_in = cv2.resize(frame, (new_w, new_h := int(frame.shape[0] * scale)),
                                      interpolation=cv2.INTER_AREA)
            else:
                frame_in = frame
            rgb = cv2.cvtColor(frame_in, cv2.COLOR_BGR2RGB)
            if not rgb.flags['C_CONTIGUOUS']:
                rgb = np.ascontiguousarray(rgb)
            self._infer_q.put((rgb, int(time.time() * 1000)))
        except Exception:
            self._inference_pending = False
            return self._last_result
        return self._last_result

    def _inference_worker(self):
        """Background thread: pulls frames from the queue, runs the
        MediaPipe detector, and updates _last_result. The main thread
        never blocks on detection (it returns _last_result immediately).
        When the queue is empty, this thread sleeps on the queue.get()
        call, releasing the GIL."""
        from queue import Empty
        while not self._stop_worker:
            try:
                rgb, ts = self._infer_q.get(timeout=0.5)
            except Empty:
                continue
            if ts <= self._last_frame_ts:
                ts = self._last_frame_ts + 1
            self._last_frame_ts = ts
            try:
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = self.detector.detect_for_video(mp_image, ts)
            except Exception:
                result = None
            with self._result_lock:
                self._last_result = result
            self._inference_pending = False
        # Drain remaining frames on exit so the queue doesn't bloat
        try:
            while True:
                self._infer_q.get_nowait()
        except Exception:
            pass

    def _one_euro_filter(self, prev, raw, dt, min_cutoff=2.5, beta=0.05):
        """Low-pass filter that adapts cutoff to speed: smooth at rest, responsive in motion.
        prev, raw: (x, y) tuple. Returns filtered (x, y)."""
        if prev is None or dt <= 0:
            return raw
        # Speed estimate from raw delta
        dx, dy = raw[0] - prev[0], raw[1] - prev[1]
        speed = math.hypot(dx, dy) / max(dt, 1e-6)
        # Adaptive cutoff: higher when moving
        cutoff = min_cutoff + beta * speed
        alpha = 1.0 - math.exp(-2 * math.pi * cutoff * dt)
        x_f = prev[0] + alpha * (raw[0] - prev[0])
        y_f = prev[1] + alpha * (raw[1] - prev[1])
        return (x_f, y_f)

    def smooth(self, tip_id, x, y, dt=1/30):
        """One-Euro filter on raw normalized coords, then a moving-average
        over the buffer. Also records velocity and updates the per-tip
        prediction so callers can read the latest position via predict()."""
        ts = time.time()
        # Save the previous filtered value BEFORE we overwrite it -- we
        # need it to compute the velocity (delta from prev -> current),
        # not delta from prev -> buffer average.
        prev_filtered = self.filtered[tip_id]
        # First pass: adaptive low-pass using this instance's configured params
        filt = self._one_euro_filter(prev_filtered, (x, y), dt,
                                     min_cutoff=self.one_euro_min_cutoff,
                                     beta=self.one_euro_beta)
        self.filtered[tip_id] = filt
        # Second pass: short moving average
        self.buffers[tip_id].append(filt)
        # Update velocity estimate (normalized coords per second).
        # Use the change between the latest two SMOOTHED samples (not
        # against the buffer average, which is older and will
        # underestimate velocity on small buffers).
        if prev_filtered is not None and self._last_smooth_ts[tip_id] > 0:
            wall_dt = ts - self._last_smooth_ts[tip_id]
            if wall_dt > 1e-4:
                vx = (filt[0] - prev_filtered[0]) / wall_dt
                vy = (filt[1] - prev_filtered[1]) / wall_dt
                self._vel_history[tip_id].append((vx, vy))
                # Average the last few samples for a stable velocity
                if self._vel_history[tip_id]:
                    arr = np.array(self._vel_history[tip_id])
                    self.velocities[tip_id] = (float(arr[:, 0].mean()),
                                                float(arr[:, 1].mean()))
        self._last_smooth_ts[tip_id] = ts
        # Anchor the prediction on the MOST RECENT filtered point (not
        # the buffer average, which lags). The buffer is still used for
        # the smoothed return value, but the predictor's anchor is
        # the freshest point so the velocity extrapolation is accurate.
        self.predicted[tip_id] = (filt[0], filt[1], ts)
        if not self.buffers[tip_id]:
            return (0.0, 0.0)
        arr = np.array(self.buffers[tip_id])
        return (float(np.mean(arr[:, 0])), float(np.mean(arr[:, 1])))

    def predict(self, tip_id, now=None):
        """Return the most up-to-date 2D position for `tip_id`.

        If `now` (wall-clock seconds) is after the last detection,
        extrapolate forward using the estimated velocity. This is the
        function gesture / cursor / HUD code should call instead of
        reading the last filtered value directly -- it gives 1:1
        responsiveness even when MediaPipe is slow.

        Returns (x, y) in normalized image coords [0, 1], or None if
        no detection has happened for this tip yet (callers MUST handle
        None -- treating (0, 0) as a valid position would register a
        fake gesture in the top-left corner)."""
        if now is None:
            now = time.time()
        px, py, pts = self.predicted.get(tip_id, (0.0, 0.0, 0.0))
        # No detection yet -- caller must skip this tip
        if pts <= 0:
            return None
        vx, vy = self.velocities.get(tip_id, (0.0, 0.0))
        dt = now - pts
        if dt <= 0:
            return (px, py)
        # Cap extrapolation so we don't drift after the user has stopped
        if dt > self.predict_max_dt:
            dt = self.predict_max_dt
        # Velocity decay: starts at 1.0 (full strength), drops to 0 at
        # dt == predict_max_dt. The shape (1 - (dt/max)^2) is a soft
        # "ease-out" curve -- the first half of the prediction horizon
        # is nearly full-strength (decay >= 0.75), the second half
        # drops fast. This prevents overshoot when motion stops.
        decay = max(0.0, 1.0 - (dt / self.predict_max_dt) ** 2)
        return (px + vx * dt * decay, py + vy * dt * decay)

    def adjust(self):
        """Apply a 'responsiveness' preset (1=smooth .. 5=1:1).
        Tunes the One-Euro filter, the smoothing buffer size, the
        EMA blend, and the maximum prediction horizon together.
        Called automatically when the user changes the Tracking tab
        slider. Higher = more responsive, less smoothing."""
        r = max(1, min(5, int(self.responsiveness)))
        # Preset table -- hand-tuned
        presets = {
            1: dict(min_cutoff=1.0, beta=0.02, alpha=0.30, buf=10, max_dt=0.080),
            2: dict(min_cutoff=1.8, beta=0.04, alpha=0.45, buf=8,  max_dt=0.110),
            3: dict(min_cutoff=2.5, beta=0.05, alpha=0.55, buf=6,  max_dt=0.150),
            4: dict(min_cutoff=3.5, beta=0.08, alpha=0.70, buf=4,  max_dt=0.200),
            5: dict(min_cutoff=5.0, beta=0.12, alpha=0.85, buf=3,  max_dt=0.250),
        }
        p = presets[r]
        self.one_euro_min_cutoff = p['min_cutoff']
        self.one_euro_beta = p['beta']
        self.cursor_ema_alpha = p['alpha']
        self.predict_max_dt = p['max_dt']
        # Resize the per-tip smoothing buffers to match the preset
        for tip in list(self.buffers.keys()):
            if self.buffers[tip].maxlen != p['buf']:
                old = list(self.buffers[tip])
                self.buffers[tip] = deque(old[-p['buf']:], maxlen=p['buf'])

    @staticmethod
    def is_palm_open(landmarks):
        """True if 3+ of the 4 fingers are clearly extended.

        Uses a wrist-relative check so it works regardless of camera
        orientation or mirroring: a finger is "extended" if its TIP is
        further from the wrist than its PIP joint, AND the tip is
        roughly in the same direction from the wrist as the MCP joint.
        (This is the standard "finger extended" test in computer
        vision literature, robust to selfie cameras that mirror Y.)
        """
        if not landmarks or len(landmarks) < 21:
            return False
        wrist = landmarks[0]
        # (tip, pip, mcp) indices for the 4 fingers
        fingers = [(8, 6, 5), (12, 10, 9), (16, 14, 13), (20, 18, 17)]
        def dist(a, b):
            return math.hypot(a.x - b.x, a.y - b.y, a.z - b.z)
        wrist_to_mcp = {f[2]: dist(wrist, landmarks[f[2]]) for f in fingers}
        wrist_to_pip = {f[1]: dist(wrist, landmarks[f[1]]) for f in fingers}
        wrist_to_tip = {f[0]: dist(wrist, landmarks[f[0]]) for f in fingers}
        # Finger extended iff tip is meaningfully further from the wrist
        # than the PIP joint (the joint where the finger bends).
        extended = 0
        for tip, pip, mcp in fingers:
            if wrist_to_tip[tip] > wrist_to_pip[pip] * 1.15 \
                    and wrist_to_pip[pip] > wrist_to_mcp[mcp] * 0.95:
                extended += 1
        return extended >= 3

# ----------------------------- 3D Reconstruction -----------------------------
#
# Why this is a real 3D pipeline (not just per-camera intrinsics):
# ----------------------------------------------------------------
# A naive setup that calls cv2.calibrateCamera once per camera produces
# intrinsics (K, dist) AND extrinsics (R, t) for each camera, but each
# camera's extrinsics are in a SEPARATE world frame. You cannot triangulate
# a 2D point in camera 0's "world" with a 2D point in camera 1's "world" --
# the coordinate systems don't agree.
#
# The correct pipeline is:
#
#   Step A. Per-camera intrinsics. Run cv2.calibrateCamera on each camera
#           independently, using many views of the checkerboard. This
#           gives K_i and dist_i for every camera i.
#
#   Step B. Shared extrinsics. Run cv2.stereoCalibrate on the SAME set of
#           checkerboard views, with camera 0 as the reference. The output
#           is R_1, t_1, ..., R_n, t_n such that
#               X_world = R_i * X_camera_i + t_i
#           for every camera i. Now every camera lives in the same frame.
#
#   Step C. Build projection matrices. For each camera, build
#               P_i = K_i @ [R_i | t_i]
#           The world origin is camera 0's optical center. Camera 0's
#           extrinsic is identity (R=I, t=0) by convention.
#
#   Step D. At runtime, for each hand landmark detected in camera i:
#               1. Undistort the 2D point using K_i, dist_i
#               2. Normalize via K_i^-1 to get a 3D ray direction in the
#                  camera's coordinate frame
#               3. Triangulate with all available (undistorted, normalized)
#                  rays using a least-squares SVD
#
#   Step E. Optionally, reproject the 3D point back into every camera to
#           measure the reprojection error and reject bad triangulations.
#
# Persistence: the entire calibration (K, dist, R, t, sizes) is saved to
# "calibration.npz" next to the script after a successful run, and loaded
# on startup. Recalibrate only when you move the cameras.
#
# References:
#   - OpenCV docs: https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html
#   - Hartley & Zisserman, "Multiple View Geometry", ch. 12 (triangulation)

DEFAULT_CALIB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "calibration.npz")


def triangulate_point_rays(origins, rays):
    """Triangulate a 3D point from camera origins and unit rays.

    `origins` and `rays` are equal-length lists of 3-vectors in a SHARED
    world frame. Each ray points FROM its origin THROUGH the detected
    landmark (so X = origin + s * ray for some s > 0).

    Builds the over-determined linear system
        [ray_i]_x * X = [ray_i]_x * origin_i
    and solves it with np.linalg.lstsq.

    Returns the 3D point (numpy array shape (3,)) in the world frame,
    or None if the input is degenerate.
    """
    if len(rays) < 2 or len(origins) < 2:
        return None
    if len(rays) != len(origins):
        return None
    rows = []
    b = []
    for r, o in zip(rays, origins):
        rx, ry, rz = r
        rows.append([0, -rz, ry])
        rows.append([rz, 0, -rx])
        b.append(-rz * o[1] + ry * o[2])
        b.append(rz * o[0] - rx * o[2])
    A = np.array(rows, dtype=np.float64)
    b = np.array(b, dtype=np.float64)
    try:
        X, residuals, rank, sv = np.linalg.lstsq(A, b, rcond=None)
    except Exception:
        return None
    if rank < 3:
        return None
    return X


class StereoCalibrator:
    """Two-phase stereo calibrator for a multi-camera rig.

    Phase A: per-camera intrinsics from many checkerboard views.
    Phase B: shared extrinsics via cv2.stereoCalibrate so all cameras
             live in one coordinate system.

    Also persists the result to disk (calibration.npz) so a single
    calibration session covers all future runs unless the cameras move.
    """

    def __init__(self, board_size=(9, 6), square_size=0.025,
                 calib_path=DEFAULT_CALIB_PATH):
        # board_size = (cols, rows) of INTERIOR corners. 9x6 means the
        # printed board has 10x7 squares.
        self.board_size = board_size
        self.square_size = square_size
        self.calib_path = calib_path

        # OpenCV corner-refinement termination criteria
        self.criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
                         30, 0.001)

        # Prepare the 3D object points (0,0,0), (1,0,0), (2,0,0)...
        # scaled by square_size. These are the same for every view.
        self.objp = np.zeros((board_size[0] * board_size[1], 3), np.float32)
        self.objp[:, :2] = np.mgrid[0:board_size[0],
                                    0:board_size[1]].T.reshape(-1, 2)
        self.objp *= square_size

        # Per-camera calibration: list of dicts with K, dist, R, t, P
        # All R, t are in the SHARED world frame (camera 0 is identity).
        self.calibrations = []  # type: list[dict | None]

        # Convenience: number of cameras, baseline, mean reprojection error
        self.num_cameras = 0
        self.baseline_m = 0.0
        self.reprojection_error = float('inf')
        self.image_sizes = []  # (w, h) per camera

    # ------------------------------------------------------------------
    #  Phase A + B  --  full calibration
    # ------------------------------------------------------------------
    def calibrate_all(self, camera_manager, samples=15, max_attempts=None,
                      progress_callback=None):
        """Capture `samples` good checkerboard views from every camera,
        then run per-camera intrinsics + cv2.stereoCalibrate for shared
        extrinsics. Persists the result to disk on success.

        progress_callback(done, total, message) is called periodically
        so the GUI can update a progress bar.
        """
        if not camera_manager or not camera_manager.cameras:
            return False, "No cameras available"
        cams = camera_manager.cameras
        n = len(cams)
        self.image_sizes = []

        if max_attempts is None:
            max_attempts = samples * 60  # ~9 seconds of trying at 60 fps

        obj_points = []           # list of (N, 3) for each accepted view
        img_points_per_cam = [[] for _ in range(n)]
        captured = 0
        attempt = 0

        while captured < samples and attempt < max_attempts:
            attempt += 1
            raws = camera_manager.read_all()
            good = True
            current = []
            current_sizes = []
            for i, (ret, frame) in enumerate(raws):
                if not ret:
                    good = False
                    break
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                current_sizes.append(gray.shape[::-1])  # (w, h)
                found, corners = cv2.findChessboardCorners(
                    gray, self.board_size, None)
                if not found:
                    good = False
                    break
                refined = cv2.cornerSubPix(
                    gray, corners, (11, 11), (-1, -1), self.criteria)
                current.append(refined)
            if good and len(current) == n:
                obj_points.append(self.objp)
                for i in range(n):
                    img_points_per_cam[i].append(current[i])
                captured += 1
                if progress_callback:
                    progress_callback(captured, samples,
                                      f"Captured {captured}/{samples} views")
            # Yield to the GUI thread
            time.sleep(0.01)

        if captured < max(5, samples // 2):
            return False, f"Only captured {captured} valid views; need at least 5"

        # ---- Phase A: per-camera intrinsics ----
        self.calibrations = []
        self.image_sizes = current_sizes
        per_cam_rms = []
        for i, cap in enumerate(cams):
            ret, frame = cap.read()
            if not ret:
                self.calibrations.append(None)
                continue
            h, w = frame.shape[:2]
            rms, K, dist, rvecs, tvecs = cv2.calibrateCamera(
                obj_points, img_points_per_cam[i], (w, h), None, None)
            per_cam_rms.append(rms)
            # We don't use rvecs/tvecs from the per-camera pass because
            # they live in independent world frames. We just keep K, dist
            # for now and overwrite R, t in Phase B.
            self.calibrations.append({
                'K': K, 'dist': dist,
                'R': np.eye(3), 't': np.zeros((3, 1)),
                'P': np.hstack((K, np.zeros((3, 1)))),
                'rms_intrinsics': rms,
            })

        # ---- Phase B: shared extrinsics via stereoCalibrate ----
        # cv2.stereoCalibrate needs at least 2 cameras. For more than 2
        # we'd want multi-view stereo; here we align camera 1..N to
        # camera 0 by calling stereoCalibrate once per pair (1-0, 2-0,
        # ..., N-0). This is approximate for N>2 but works for our use
        # case (the user has 2 or 3 cameras and a hand in front of them).
        good_calibs = [c for c in self.calibrations if c is not None]
        if len(good_calibs) < 2:
            return False, "Need at least 2 cameras with detected checkerboards"

        for i in range(1, n):
            if self.calibrations[i] is None:
                continue
            K0 = self.calibrations[0]['K']
            d0 = self.calibrations[0]['dist']
            Ki = self.calibrations[i]['K']
            di = self.calibrations[i]['dist']
            try:
                rms_stereo, K0o, d0o, Ko, do, R, t, E, F = cv2.stereoCalibrate(
                    obj_points,
                    img_points_per_cam[0], img_points_per_cam[i],
                    K0, d0, Ki, di,
                    self.image_sizes[0],  # image size of camera 0
                    criteria=self.criteria,
                    flags=cv2.CALIB_FIX_INTRINSIC)
                # K0, Ki may have been refined; keep our originals
                self.calibrations[0]['R'] = np.eye(3)
                self.calibrations[0]['t'] = np.zeros((3, 1))
                self.calibrations[i]['R'] = R
                self.calibrations[i]['t'] = t.reshape(3, 1)
            except Exception as e:
                return False, f"stereoCalibrate failed for cam {i}: {e}"

        # ---- Build projection matrices P_i = K_i [R_i | t_i] ----
        for c in self.calibrations:
            if c is None:
                continue
            c['P'] = c['K'] @ np.hstack((c['R'], c['t']))

        # ---- Stats: baseline, reprojection error ----
        if (self.calibrations[0] is not None
                and self.calibrations[1] is not None):
            t0 = self.calibrations[0]['t']
            t1 = self.calibrations[1]['t']
            self.baseline_m = float(np.linalg.norm(t1 - t0))
        self.num_cameras = n
        self.reprojection_error = self._compute_reprojection_error(
            obj_points, img_points_per_cam)

        # ---- Persist ----
        try:
            self.save()
        except Exception as e:
            print(f"WARNING: could not save calibration: {e}")

        return True, (f"Calibrated {n} cameras. "
                      f"Baseline: {self.baseline_m*100:.1f} cm. "
                      f"Reprojection error: {self.reprojection_error:.3f} px")

    def _compute_reprojection_error(self, obj_points, img_points_per_cam):
        """Project each 3D board corner back into each camera and measure
        the mean pixel distance to the detected corner."""
        total_err = 0.0
        total_count = 0
        for view_idx, X_world in enumerate(obj_points):
            for cam_idx, c in enumerate(self.calibrations):
                if c is None:
                    continue
                pts_2d = img_points_per_cam[cam_idx][view_idx]
                projected, _ = cv2.projectPoints(
                    X_world, c['R'], c['t'], c['K'], c['dist'])
                projected = projected.reshape(-1, 2)
                err = np.linalg.norm(projected - pts_2d.reshape(-1, 2), axis=1)
                total_err += err.sum()
                total_count += len(err)
        return total_err / max(1, total_count)

    # ------------------------------------------------------------------
    #  Persistence
    # ------------------------------------------------------------------
    def save(self, path=None):
        path = path or self.calib_path
        payload = {
            'board_size': np.array(self.board_size),
            'square_size': np.float64(self.square_size),
            'num_cameras': np.int32(self.num_cameras),
            'baseline_m': np.float64(self.baseline_m),
            'reprojection_error': np.float64(self.reprojection_error),
        }
        for i, c in enumerate(self.calibrations):
            if c is None:
                continue
            payload[f'K_{i}'] = c['K']
            payload[f'dist_{i}'] = c['dist']
            payload[f'R_{i}'] = c['R']
            payload[f't_{i}'] = c['t']
            # The projection matrix P = K [R|t] is built during
            # calibrate_all, but a calibration loaded from a
            # pre-P-era file, or one synthesized by a test, may be
            # missing it. Compute on the fly so save() never raises.
            if 'P' in c and c['P'] is not None:
                payload[f'P_{i}'] = c['P']
            else:
                payload[f'P_{i}'] = c['K'] @ np.hstack((c['R'], c['t']))
        if self.image_sizes:
            for i, sz in enumerate(self.image_sizes):
                payload[f'size_{i}'] = np.array(sz, dtype=np.int32)
        np.savez(path, **payload)
        print(f"Calibration saved to {path}")

    def load(self, path=None):
        path = path or self.calib_path
        if not os.path.exists(path):
            return False
        try:
            data = np.load(path, allow_pickle=True)
        except Exception as e:
            print(f"Could not load calibration: {e}")
            return False
        self.board_size = tuple(int(x) for x in data['board_size'])
        self.square_size = float(data['square_size'])
        self.num_cameras = int(data['num_cameras'])
        self.baseline_m = float(data['baseline_m'])
        self.reprojection_error = float(data['reprojection_error'])
        self.calibrations = []
        self.image_sizes = []
        for i in range(self.num_cameras):
            key = f'K_{i}'
            if key not in data:
                self.calibrations.append(None)
                self.image_sizes.append((0, 0))
                continue
            self.calibrations.append({
                'K': data[f'K_{i}'],
                'dist': data[f'dist_{i}'],
                'R': data[f'R_{i}'],
                't': data[f't_{i}'],
                'P': data[f'P_{i}'],
                'rms_intrinsics': 0.0,
            })
            sz_key = f'size_{i}'
            if sz_key in data:
                self.image_sizes.append(tuple(int(x) for x in data[sz_key]))
        return True

    @property
    def is_calibrated(self):
        return len([c for c in self.calibrations if c is not None]) >= 2

    # ------------------------------------------------------------------
    #  Runtime 3D reconstruction
    # ------------------------------------------------------------------
    def reconstruct_3d(self, points_2d_per_cam):
        """Given a list of 2D (x, y) pixel coords per camera (one per
        camera, in image order), return a 3D point in the shared world
        frame, or None.

        Pipeline per camera i:
            1. Undistort the 2D point using K_i, dist_i
            2. Normalize: p_norm = K_i^-1 * [x, y, 1]
            3. Transform to world frame: ray_world = R_i^T * p_norm
            4. Compute the 3D origin: cam_i_origin = -R_i^T * t_i
        Then triangulate the rays from the camera origins.
        """
        cams_data = [(p, c) for p, c in zip(points_2d_per_cam, self.calibrations)
                     if p is not None and c is not None]
        if len(cams_data) < 2:
            return None

        rays = []           # unit rays in world frame
        origins = []        # camera optical centers in world frame
        for (x, y), c in cams_data:
            # 1) Undistort + normalize. With P=None, cv2.undistortPoints
            #    returns NORMALIZED image-plane coordinates (z=1) using
            #    K_new=I and K_new=K, so xn,yn are in the camera frame
            #    in units of "focal length" -- exactly what we want.
            pts = np.array([[[x, y]]], dtype=np.float32)
            und = cv2.undistortPoints(pts, c['K'], c['dist'], P=None)
            xn, yn = und[0, 0]
            # 2) Normalized image-plane point (z=1)
            p_norm = np.array([xn, yn, 1.0], dtype=np.float64)
            # 3) Rotate the camera-frame ray to world frame.
            #    In the OpenCV convention X_world = R * X_cam + t,
            #    so X_cam = R^T * (X_world - t), and a ray direction
            #    in the camera frame maps to a ray direction in the
            #    world frame by R^T.
            R = c['R']
            t = c['t'].reshape(3)
            ray_world = R.T @ p_norm
            ray_world /= max(np.linalg.norm(ray_world), 1e-9)
            # 4) Camera origin in world frame. Setting X_cam = 0 in
            #    X_world = R * X_cam + t gives origin = t.
            origin = t
            rays.append(ray_world)
            origins.append(origin)

        if len(rays) < 2:
            return None
        # Triangulate by intersecting rays. For each camera i, the world
        # point X must lie on the line
        #     X = origin_i + s_i * ray_i
        # Cross both sides with ray_i:
        #     [ray_i]_x * (X - origin_i) = 0
        #     [ray_i]_x * X = [ray_i]_x * origin_i
        # Two independent rows per ray give us an over-determined system
        # A * X = b that we solve in the least-squares sense.
        rows = []
        b = []
        for r, o in zip(rays, origins):
            rx, ry, rz = r
            rows.append([0, -rz, ry])
            rows.append([rz, 0, -rx])
            b.append(-rz * o[1] + ry * o[2])
            b.append(rz * o[0] - rx * o[2])
        A = np.array(rows, dtype=np.float64)
        b = np.array(b, dtype=np.float64)
        try:
            X, residuals, rank, sv = np.linalg.lstsq(A, b, rcond=None)
        except Exception:
            return None
        if rank < 3:
            return None
        return X

    def reconstruct_fingertips(self, landmarks_per_cam, tip_indices=(4, 8, 12, 16, 20)):
        """Given a list of MediaPipe hand-landmark lists (one per camera),
        return a dict {tip_index: np.array([X,Y,Z])} for the 5 fingertips,
        or None if reconstruction fails.
        """
        if not self.is_calibrated:
            return None
        if not any(landmarks_per_cam):
            return None
        result = {}
        for tip in tip_indices:
            pts = []
            for lm_list in landmarks_per_cam:
                if lm_list is None:
                    pts.append(None)
                    continue
                # MediaPipe landmarks are normalized [0, 1]; convert to
                # pixel coords for the camera that produced them.
                # We assume the landmark is in the coordinate frame of
                # the corresponding camera's image size. The caller is
                # responsible for passing landmarks in image order.
                lm = lm_list[tip]
                pts.append((lm.x, lm.y))
            X = self.reconstruct_3d(pts)
            if X is not None:
                result[tip] = X
        return result

    def __repr__(self):
        if not self.is_calibrated:
            return (f"StereoCalibrator(board={self.board_size}, "
                    f"square={self.square_size*1000:.0f}mm, NOT calibrated)")
        return (f"StereoCalibrator(board={self.board_size}, "
                f"square={self.square_size*1000:.0f}mm, "
                f"cams={self.num_cameras}, baseline={self.baseline_m*100:.1f}cm, "
                f"reproj_err={self.reprojection_error:.2f}px)")

# ----------------------------- Main Application -----------------------------
class HandControlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Tony Stark Hand Control - Multi-Camera GUI")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # ---- Focus highlight overlay (created lazily on first use) ----
        self.overlay = None
        self.overlay_canvas = None
        self.overlay_label = None
        self._overlay_after_id = None
        # ---- Persistent selection overlay (created lazily on first use) ----
        # A small border that continuously tracks the currently-focused
        # UI element. Polled 10x/sec so the user can always see what the
        # next click/Enter will activate. Toggleable from the
        # Accessibility tab.
        self.selection_overlay = None
        self.selection_canvas = None
        self._selection_after_id = None
        self.show_selection_overlay = True

        # State
        self.running = False
        self.engaged = False
        self.engaged_time = 0
        self.engage_hold_seconds = 0.6
        self.intent_history = deque(maxlen=10)
        self.screen_width, self.screen_height = pyautogui.size()
        self.last_swipe_time = 0
        self.swipe_cooldown = 0.8
        self.index_history = deque()
        self.last_ollama_gesture = None

        # Settings (used by Tracking tab when added)
        self.enable_screen_cursor = False  # DEFAULT OFF — accessibility nav only
        self.enable_3d_display = True
        self.nav_mode = 'tab'  # 'tab' or 'arrow'
        self.focus_dwell = 0.0  # seconds to lock focus after a direction press
        self._dwell_until = 0.0
        self.click_threshold_px = 40
        self.swipe_min_speed = 300
        # (one_euro_min_cutoff, one_euro_beta, cursor_ema_alpha are set in the perf block above)
        # Responsiveness preset: 1 = smoothest, 5 = 1:1. The slider in the
        # Tracking tab writes to this and calls _apply_responsiveness.
        self.responsiveness = 3
        self.focus_highlight_color = '#00FF00'
        self.focus_highlight_thickness = 6
        # Performance tuning
        self.mediapipe_skip = 1  # run model every Nth frame; 1 = every frame (snappiest)
        self._frame_counter = 0
        # Cached landmarks per camera for skipped frames
        self._loop_ms_hist = deque(maxlen=30)
        self._cached_landmarks = {}
        # Ollama submission throttling
        self._ollama_frame_skip = 6  # submit one frame every Nth main-loop tick
        # Snappier defaults (was min_cutoff=1.5, beta=0.02, alpha=0.35)
        self.one_euro_min_cutoff = 2.5
        self.one_euro_beta = 0.05
        self.cursor_ema_alpha = 0.55

        # Cameras & processor
        self.camera_mgr = None
        self.hand_proc = HandProcessor()
        # Push the App's tracking defaults into the freshly-built
        # HandProcessor (in case the user changes the preset before
        # any tracking has run, or in case the HandProcessor's default
        # preset gets out of sync with the App's).
        self.hand_proc.responsiveness = self.responsiveness
        self.hand_proc.adjust()
        self.stereo = StereoCalibrator()  # will be used after calibration
        # Room map: user-placed 3D anchors (walls, zones, hotspots, etc.)
        # in the shared world frame. Auto-loads from room_map.json if
        # one exists next to the script.
        self.room_map = RoomMap()
        self.room_map.load()
        # Latest 3D hand position (set per loop iteration when
        # triangulation succeeds). Used by the "use live hand
        # position" button in the 3D tab.
        self._last_hand_3d = None
        # 3D-view redraw throttle -- matplotlib repaints are heavy,
        # so we only redraw when new 3D data arrives (at most 5 Hz).
        self._3d_redraw_pending = False
        # 3D view state
        self._3d_fig = None
        self._3d_ax = None
        self._3d_canvas_widget = None
        # ID of the currently selected anchor in the 3D view's listbox
        self._selected_anchor_id = None
        # Live hand trail (for visualizing the path of the index
        # fingertip through the room). Capped at N points.
        self._hand_trail = deque(maxlen=200)
        # Per-cam caches: live-feed status, FPS, last display
        self._live_cache = {}
        self._fps_cache = {}
        self._cached_landmarks = {}  # per-cam last-known landmarks
        self._last_displays = {}  # per-cam last-drawn display frame
        # Cached static HUD base layer, keyed by (h, w). One per
        # unique frame size we've seen. Saves ~5ms/cam/frame of
        # repeated cv2.circle/ellipse work.
        self._hud_base_cache = {}

        # Ollama (disabled by default to avoid startup network timeouts
        # that lag the GUI. User can enable in the Ollama tab and click Save.)
        self.ollama = None

        # Fast Mode: pre-downscale frames to 240p before MediaPipe
        # for ~30% faster inference at the cost of some accuracy on
        # tiny / far-away hands. Toggle from the Tracking tab. Must
        # be set BEFORE the notebook/tabs are created (the checkbox
        # widget reads it).
        self.fast_mode = False

        # GUI layout: ttk.Notebook with 5 tabs on the left, camera feed grid on the right
        self.controls_frame = ttk.Frame(root, padding=10)
        self.controls_frame.grid(row=0, column=0, sticky="ns")
        self.feeds_frame = ttk.Frame(root)
        self.feeds_frame.grid(row=0, column=1, sticky="nsew")

        ttk.Label(self.controls_frame, text="Tony Stark Hand Control",
                  font=("Segoe UI", 14, "bold")).pack(pady=5)

        self.notebook = ttk.Notebook(self.controls_frame)
        self.notebook.pack(fill="both", expand=True, pady=4)

        self.tab_main = ttk.Frame(self.notebook, padding=8)
        self.tab_ollama = ttk.Frame(self.notebook, padding=8)
        self.tab_tracking = ttk.Frame(self.notebook, padding=8)
        self.tab_access = ttk.Frame(self.notebook, padding=8)
        self.tab_3d = ttk.Frame(self.notebook, padding=8)
        self.tab_cameras = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.tab_main, text="Main")
        self.notebook.add(self.tab_ollama, text="Ollama")
        self.notebook.add(self.tab_tracking, text="Tracking")
        self.notebook.add(self.tab_access, text="Accessibility")
        self.notebook.add(self.tab_3d, text="3D / Room")
        self.notebook.add(self.tab_cameras, text="Cameras")

        # ---- Tab 1: Main ----
        self.start_btn = ttk.Button(self.tab_main, text="Start", command=self.start)
        self.start_btn.pack(fill="x", pady=2)
        self.stop_btn = ttk.Button(self.tab_main, text="Stop", command=self.stop, state="disabled")
        self.stop_btn.pack(fill="x", pady=2)
        self.calibrate_btn = ttk.Button(self.tab_main, text="Calibrate (checkerboard)",
                                        command=self.start_calibration, state="disabled")
        self.calibrate_btn.pack(fill="x", pady=2)
        self.flash_test_btn = ttk.Button(self.tab_main, text="Test focus highlight now",
                                         command=lambda: self.flash_overlay('test'))
        self.flash_test_btn.pack(fill="x", pady=2)
        ttk.Separator(self.tab_main, orient="horizontal").pack(fill="x", pady=6)
        self.status_label = ttk.Label(self.tab_main, text="Status: Idle")
        self.status_label.pack(fill="x", pady=2)
        ttk.Label(self.tab_main, text="Intent:").pack(anchor="w")
        self.intent_label = ttk.Label(self.tab_main, text="Disengaged")
        self.intent_label.pack(anchor="w")
        ttk.Label(self.tab_main, text="Ollama:").pack(anchor="w")
        self.ollama_label = ttk.Label(self.tab_main, text="off")
        self.ollama_label.pack(anchor="w")
        ttk.Label(self.tab_main, text="3D Calibration:").pack(anchor="w")
        self.calib_label = ttk.Label(self.tab_main, text="Not calibrated")
        self.calib_label.pack(anchor="w")
        # Live performance readout. Shows the rolling average of the
        # main loop time so you can see if tracking is hitting 30 fps,
        # 15 fps, or 5 fps in real time.
        ttk.Label(self.tab_main, text="Performance:").pack(anchor="w", pady=(8, 0))
        self.loop_stats_label = ttk.Label(self.tab_main,
            text="loop: -- ms  (-- fps)  |  target: 30.0 fps",
            font=("Consolas", 9))
        self.loop_stats_label.pack(anchor="w")
        # Real-time app CPU% + RAM. Uses win32 APIs (no extra
        # dependency). The values are updated from the main loop,
        # not a separate timer, to avoid burning a Tk timer.
        self.cpu_stats_label = ttk.Label(self.tab_main,
            text="cpu: -- %   ram: -- MB   threads: --",
            font=("Consolas", 9))
        self.cpu_stats_label.pack(anchor="w")
        self._proc_times_cache = None  # (last_t, user, kernel) for delta
        self._last_cpu_pct = 0.0
        # Collapsible Cameras section (per-camera enable)
        self.cameras_visible = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.tab_main, text="Cameras (per-cam enable)",
                        variable=self.cameras_visible,
                        command=self._toggle_cameras_section).pack(anchor="w", pady=(8, 0))
        self.cameras_section = ttk.LabelFrame(self.tab_main, text="Per-Camera Enable", padding=4)
        self.cameras_section.pack(fill="x", pady=2)
        self.cameras_inner = ttk.Frame(self.cameras_section)
        self.cameras_inner.pack(fill="x")
        self.camera_vars = {}

        # ---- Tab 2: Ollama ----
        ttk.Label(self.tab_ollama, text="Cloud gesture recognition (optional)",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.ollama_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.tab_ollama, text="Enable Ollama",
                        variable=self.ollama_enabled_var).pack(anchor="w")
        ttk.Label(self.tab_ollama, text="Endpoint URL:").pack(anchor="w")
        self.ollama_endpoint_var = tk.StringVar(value="https://ollama.com/api/generate")
        ttk.Entry(self.tab_ollama, textvariable=self.ollama_endpoint_var).pack(fill="x")
        ttk.Label(self.tab_ollama, text="Model:").pack(anchor="w")
        self.ollama_model_var = tk.StringVar(value="gemma4:31b-cloud")
        ttk.Entry(self.tab_ollama, textvariable=self.ollama_model_var).pack(fill="x")
        ttk.Label(self.tab_ollama, text="API key:").pack(anchor="w")
        self.ollama_key_frame = ttk.Frame(self.tab_ollama)
        self.ollama_key_frame.pack(fill="x")
        self.ollama_key_show = tk.BooleanVar(value=False)
        self.ollama_key_var = tk.StringVar(
            value="46abe6b190774fd7ae6d712b19f3fb2e.bQx3vVVgpOr8rHdv-kRt50I9")
        self.ollama_key_entry = ttk.Entry(self.ollama_key_frame, textvariable=self.ollama_key_var,
                                          show="*")
        self.ollama_key_entry.pack(side="left", fill="x", expand=True)
        ttk.Checkbutton(self.ollama_key_frame, text="Show",
                        variable=self.ollama_key_show,
                        command=self._toggle_key_visibility).pack(side="left")
        ttk.Label(self.tab_ollama, text="Query cooldown (s):").pack(anchor="w", pady=(6, 0))
        self.ollama_cooldown_var = tk.DoubleVar(value=0.5)
        ttk.Scale(self.tab_ollama, from_=0.1, to=3.0, variable=self.ollama_cooldown_var,
                  orient="horizontal").pack(fill="x")
        ttk.Label(self.tab_ollama, text="Custom prompt:").pack(anchor="w", pady=(6, 0))
        self.ollama_prompt_text = tk.Text(self.tab_ollama, height=6, width=40,
                                          wrap="word")
        self.ollama_prompt_text.pack(fill="both", expand=True)
        self.ollama_prompt_text.insert("1.0",
            "What hand gesture is being shown? Choose from: left_click, right_click, "
            "scroll_up, scroll_down, swipe_left, swipe_right, swipe_up, swipe_down, "
            "move_cursor, engage, disengage, none. Respond with only the gesture name.")
        ttk.Button(self.tab_ollama, text="Save (rebuild Ollama worker)",
                   command=self._save_ollama_settings).pack(fill="x", pady=4)

        # ---- Tab 3: Tracking ----
        # The Responsiveness preset is the most important control for
        # 1:1 hand-tracking feel: it tunes the One-Euro filter, the
        # smoothing buffer size, the cursor EMA blend, and the motion
        # predictor horizon all together. Place it at the top of the tab.
        ttk.Label(self.tab_tracking, text="Responsiveness preset:",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.responsiveness_var = tk.IntVar(value=self.responsiveness)
        ttk.Scale(self.tab_tracking, from_=1, to=5, variable=self.responsiveness_var,
                  orient="horizontal",
                  command=lambda v: self._apply_responsiveness(int(float(v)))).pack(fill="x")
        ttk.Label(self.tab_tracking,
                  text="1 = smoothest  /  5 = 1:1 with your hand (recommended: 4)",
                  font=("Segoe UI", 8)).pack(anchor="w")
        # Fast Mode: pre-downscale frames to 240p for ~30% faster MediaPipe.
        # Trades a small amount of accuracy on tiny / far-away hands.
        self.fast_mode_var = tk.BooleanVar(value=self.fast_mode)
        ttk.Checkbutton(self.tab_tracking,
                        text="Fast Mode (240p inference, +30% throughput, slight accuracy loss)",
                        variable=self.fast_mode_var,
                        command=lambda: self._set_attr('fast_mode', self.fast_mode_var.get())
                        ).pack(anchor="w", pady=2)
        ttk.Separator(self.tab_tracking, orient="horizontal").pack(fill="x", pady=4)
        ttk.Label(self.tab_tracking, text="Engagement hold (s):").pack(anchor="w")
        self.engage_hold_var = tk.DoubleVar(value=self.engage_hold_seconds)
        ttk.Scale(self.tab_tracking, from_=0.0, to=3.0, variable=self.engage_hold_var,
                  orient="horizontal",
                  command=lambda v: self._set_attr('engage_hold_seconds', float(v))).pack(fill="x")
        ttk.Label(self.tab_tracking, text="Click threshold (px):").pack(anchor="w", pady=(6, 0))
        self.click_thresh_var = tk.IntVar(value=self.click_threshold_px)
        ttk.Scale(self.tab_tracking, from_=10, to=150, variable=self.click_thresh_var,
                  orient="horizontal",
                  command=lambda v: self._set_attr('click_threshold_px', int(float(v)))).pack(fill="x")
        ttk.Label(self.tab_tracking, text="Swipe min speed (px/s):").pack(anchor="w", pady=(6, 0))
        self.swipe_speed_var = tk.IntVar(value=self.swipe_min_speed)
        ttk.Scale(self.tab_tracking, from_=100, to=2000, variable=self.swipe_speed_var,
                  orient="horizontal",
                  command=lambda v: self._set_attr('swipe_min_speed', int(float(v)))).pack(fill="x")
        ttk.Label(self.tab_tracking, text="Swipe cooldown (s):").pack(anchor="w", pady=(6, 0))
        self.swipe_cooldown_var = tk.DoubleVar(value=self.swipe_cooldown)
        ttk.Scale(self.tab_tracking, from_=0.1, to=3.0, variable=self.swipe_cooldown_var,
                  orient="horizontal",
                  command=lambda v: self._set_attr('swipe_cooldown', float(v))).pack(fill="x")
        ttk.Label(self.tab_tracking, text="Cursor EMA alpha:").pack(anchor="w", pady=(6, 0))
        self.ema_alpha_var = tk.DoubleVar(value=self.cursor_ema_alpha)
        ttk.Scale(self.tab_tracking, from_=0.05, to=1.0, variable=self.ema_alpha_var,
                  orient="horizontal",
                  command=lambda v: self._set_attr('cursor_ema_alpha', float(v))).pack(fill="x")
        ttk.Label(self.tab_tracking, text="One-Euro min cutoff:").pack(anchor="w", pady=(6, 0))
        self.oecutoff_var = tk.DoubleVar(value=self.one_euro_min_cutoff)
        ttk.Scale(self.tab_tracking, from_=0.1, to=10.0, variable=self.oecutoff_var,
                  orient="horizontal",
                  command=lambda v: self._set_attr('one_euro_min_cutoff', float(v))).pack(fill="x")
        ttk.Label(self.tab_tracking, text="One-Euro beta:").pack(anchor="w", pady=(6, 0))
        self.oebeta_var = tk.DoubleVar(value=self.one_euro_beta)
        ttk.Scale(self.tab_tracking, from_=0.0, to=1.0, variable=self.oebeta_var,
                  orient="horizontal",
                  command=lambda v: self._set_attr('one_euro_beta', float(v))).pack(fill="x")
        ttk.Separator(self.tab_tracking, orient="horizontal").pack(fill="x", pady=6)
        ttk.Label(self.tab_tracking, text="Focus highlight color (hex):").pack(anchor="w")
        self.fhc_var = tk.StringVar(value=self.focus_highlight_color)
        ttk.Entry(self.tab_tracking, textvariable=self.fhc_var).pack(fill="x")
        self.fhc_var.trace_add("write",
            lambda *_: self._set_attr('focus_highlight_color', self.fhc_var.get()))
        ttk.Label(self.tab_tracking, text="Focus highlight thickness (px):").pack(anchor="w", pady=(6, 0))
        self.fht_var = tk.IntVar(value=self.focus_highlight_thickness)
        ttk.Scale(self.tab_tracking, from_=1, to=20, variable=self.fht_var,
                  orient="horizontal",
                  command=lambda v: self._set_attr('focus_highlight_thickness', int(float(v)))
                  ).pack(fill="x")
        ttk.Separator(self.tab_tracking, orient="horizontal").pack(fill="x", pady=6)
        self.enable_3d_var = tk.BooleanVar(value=self.enable_3d_display)
        ttk.Checkbutton(self.tab_tracking, text="Enable 3D point display",
                        variable=self.enable_3d_var,
                        command=lambda: self._set_attr('enable_3d_display', self.enable_3d_var.get())
                        ).pack(anchor="w")
        self.enable_cursor_var = tk.BooleanVar(value=self.enable_screen_cursor)
        ttk.Checkbutton(self.tab_tracking, text="Enable screen cursor (off by default)",
                        variable=self.enable_cursor_var,
                        command=lambda: self._set_attr('enable_screen_cursor',
                                                       self.enable_cursor_var.get())
                        ).pack(anchor="w")

        # ---- Tab 4: Accessibility ----
        ttk.Label(self.tab_access, text="Navigation mode:").pack(anchor="w")
        self.nav_mode_var = tk.StringVar(value=self.nav_mode)
        ttk.Radiobutton(self.tab_access, text="Tab navigation (Tab/Shift+Tab + Arrows)",
                        variable=self.nav_mode_var, value="tab",
                        command=lambda: self._set_attr('nav_mode', self.nav_mode_var.get())
                        ).pack(anchor="w")
        ttk.Radiobutton(self.tab_access, text="Arrow navigation (pure Arrow keys)",
                        variable=self.nav_mode_var, value="arrow",
                        command=lambda: self._set_attr('nav_mode', self.nav_mode_var.get())
                        ).pack(anchor="w")
        ttk.Label(self.tab_access, text="Focus highlight dwell (s):").pack(anchor="w", pady=(8, 0))
        self.dwell_var = tk.DoubleVar(value=self.focus_dwell)
        ttk.Spinbox(self.tab_access, from_=0.0, to=2.0, increment=0.1,
                    textvariable=self.dwell_var, width=8,
                    command=lambda: self._set_attr('focus_dwell', float(self.dwell_var.get()))
                    ).pack(anchor="w")
        self.dwell_var.trace_add("write",
            lambda *_: self._set_attr('focus_dwell', float(self.dwell_var.get() or 0)))
        ttk.Button(self.tab_access, text="Test focus highlight now",
                   command=lambda: self.flash_overlay('test')).pack(anchor="w", pady=8)
        ttk.Separator(self.tab_access, orient="horizontal").pack(fill="x", pady=8)
        # ---- Persistent selection overlay ----
        # A small border that continuously tracks the currently-focused
        # UI element, so you always know what the next click/Enter will
        # activate. Off by default since some apps (e.g. video games,
        # full-screen media) may have noisy focus states.
        self.sel_overlay_var = tk.BooleanVar(value=self.show_selection_overlay)
        ttk.Checkbutton(self.tab_access,
                        text="Show persistent selection border (tracks the focused UI element)",
                        variable=self.sel_overlay_var,
                        command=self._toggle_selection_overlay).pack(anchor="w")
        ttk.Button(self.tab_access, text="Test selection border now",
                   command=self.refresh_selection_overlay).pack(anchor="w", pady=2)

        # ---- Tab 5: 3D / Room ----
        # Interactive 3D scene showing camera positions, the live hand
        # position, and the user's room anchors. Anchors can be added
        # by clicking the viewport, by the live hand, or by manual
        # entry. The map is saved/loaded to room_map.json.
        self._build_3d_tab()

        # ---- Tab 6: Cameras ----
        ttk.Label(self.tab_cameras, text="Detected cameras:").pack(anchor="w")
        self.cameras_canvas = tk.Canvas(self.tab_cameras, height=200)
        self.cameras_scroll = ttk.Scrollbar(self.tab_cameras, orient="vertical",
                                            command=self.cameras_canvas.yview)
        self.cameras_canvas.configure(yscrollcommand=self.cameras_scroll.set)
        self.cameras_canvas.pack(side="left", fill="both", expand=True)
        self.cameras_scroll.pack(side="right", fill="y")
        self.cameras_list_frame = ttk.Frame(self.cameras_canvas)
        self.cameras_canvas.create_window((0, 0), window=self.cameras_list_frame, anchor="nw")
        self.cameras_list_frame.bind("<Configure>",
            lambda e: self.cameras_canvas.configure(scrollregion=self.cameras_canvas.bbox("all")))

        self.camera_canvases = {}

        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)
        self.loop_id = None

        # Try to load a previously-saved calibration so the user doesn't
        # have to recalibrate every restart (cameras are usually stationary).
        if self.stereo.load():
            n = len([c for c in self.stereo.calibrations if c is not None])
            if n >= 2 and hasattr(self, 'calib_label'):
                self.calib_label.config(
                    text=(f"Loaded saved calibration "
                          f"({n} cams, baseline "
                          f"{self.stereo.baseline_m*100:.1f} cm, "
                          f"reproj err {self.stereo.reprojection_error:.2f} px)"))

    # -------------------------- 3D / Room Tab --------------------------
    def _build_3d_tab(self):
        """Build the 3D visualization + interactive room-mapping tab.
        Layout:
            +--------------------------------+----------------------+
            |  matplotlib 3D viewport       | Anchor list + tools  |
            |  (cameras, hand, anchors)      | (add/remove/save)   |
            +--------------------------------+----------------------+
        """
        # Lazy-import matplotlib so the rest of the app starts even
        # if matplotlib has a problem on this host.
        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
            from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 (registers 3d projection)
        except Exception as e:
            ttk.Label(self.tab_3d,
                      text=f"matplotlib not available: {e}\n"
                           f"pip install matplotlib to enable the 3D view.",
                      foreground="red").pack(anchor="w", padx=8, pady=8)
            return

        # Two-column layout: left = 3D view + toolbar, right = tools
        left = ttk.Frame(self.tab_3d)
        left.pack(side="left", fill="both", expand=True, padx=(0, 4))
        right = ttk.Frame(self.tab_3d)
        right.pack(side="right", fill="y")

        # ---- LEFT: 3D matplotlib viewport ----
        self._3d_fig = Figure(figsize=(5, 4), dpi=100)
        self._3d_fig.patch.set_facecolor('#101418')
        self._3d_ax = self._3d_fig.add_subplot(111, projection='3d')
        self._3d_ax.set_facecolor('#101418')
        # Hide the default matplotlib axes grid for a cleaner look
        self._3d_ax.xaxis.pane.set_visible(False)
        self._3d_ax.yaxis.pane.set_visible(False)
        self._3d_ax.zaxis.pane.set_visible(False)
        self._3d_ax.set_xlabel('X (m)', color='#88FF88')
        self._3d_ax.set_ylabel('Y (m)', color='#88FF88')
        self._3d_ax.set_zlabel('Z (m)', color='#88FF88')
        self._3d_ax.tick_params(colors='#88FF88')
        self._3d_ax.set_title('Room map (drag to rotate)', color='#88FF88')
        # Default view: looking down at the X-Y plane (top-down)
        self._3d_ax.view_init(elev=70, azim=-90)

        self._3d_canvas_widget = FigureCanvasTkAgg(self._3d_fig, master=left)
        self._3d_canvas_widget.draw()
        self._3d_canvas_widget.get_tk_widget().pack(side="top", fill="both", expand=True)

        # Matplotlib navigation toolbar (zoom, pan, save image)
        tb_frame = ttk.Frame(left)
        tb_frame.pack(side="top", fill="x")
        try:
            self._3d_toolbar = NavigationToolbar2Tk(self._3d_canvas_widget, tb_frame)
            self._3d_toolbar.update()
        except Exception:
            self._3d_toolbar = None

        # Click in the 3D viewport to add an anchor (ray-plane at z=0)
        self._3d_canvas_widget.mpl_connect('button_press_event', self._on_3d_click)
        # Redraw whenever the user resizes the tab
        self._3d_fig.canvas.mpl_connect('resize_event',
                                         lambda *_: self._schedule_3d_redraw())

        # ---- RIGHT: tools ----
        ttk.Label(right, text="Add anchor (click 3D view):",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=4, pady=(4, 0))
        # Type radiobuttons
        self._3d_anchor_type = tk.StringVar(value='wall')
        type_row = ttk.Frame(right)
        type_row.pack(anchor="w", padx=4)
        for t in RoomMap.ANCHOR_TYPES:
            ttk.Radiobutton(type_row, text=t, value=t, variable=self._3d_anchor_type).pack(side="left")

        ttk.Label(right, text="Click z height (m):").pack(anchor="w", padx=4, pady=(8, 0))
        self._3d_click_z = tk.DoubleVar(value=1.0)
        ttk.Spinbox(right, from_=-1.0, to=3.0, increment=0.1,
                    textvariable=self._3d_click_z, width=6).pack(anchor="w", padx=4)

        ttk.Separator(right, orient="horizontal").pack(fill="x", padx=4, pady=8)
        ttk.Label(right, text="Add at live hand position:",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=4)
        ttk.Button(right, text="Drop anchor at hand",
                   command=self._add_anchor_at_hand).pack(anchor="w", padx=4, pady=2)
        self._3d_hand_pos_label = ttk.Label(right, text="Hand: (no data)")
        self._3d_hand_pos_label.pack(anchor="w", padx=4)

        ttk.Separator(right, orient="horizontal").pack(fill="x", padx=4, pady=8)
        ttk.Label(right, text="Manual entry:",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=4)
        manual = ttk.Frame(right)
        manual.pack(anchor="w", padx=4)
        ttk.Label(manual, text="x").grid(row=0, column=0); ttk.Label(manual, text="y").grid(row=0, column=1); ttk.Label(manual, text="z").grid(row=0, column=2)
        self._3d_manual_x = tk.DoubleVar(value=0.0)
        self._3d_manual_y = tk.DoubleVar(value=0.0)
        self._3d_manual_z = tk.DoubleVar(value=1.0)
        ttk.Entry(manual, textvariable=self._3d_manual_x, width=6).grid(row=1, column=0)
        ttk.Entry(manual, textvariable=self._3d_manual_y, width=6).grid(row=1, column=1)
        ttk.Entry(manual, textvariable=self._3d_manual_z, width=6).grid(row=1, column=2)
        ttk.Button(manual, text="Add",
                   command=self._add_anchor_manual).grid(row=1, column=3, padx=4)

        ttk.Separator(right, orient="horizontal").pack(fill="x", padx=4, pady=8)
        ttk.Label(right, text="Anchors:",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=4)
        list_frame = ttk.Frame(right)
        list_frame.pack(anchor="w", padx=4, fill="x")
        self._3d_anchor_listbox = tk.Listbox(list_frame, width=30, height=8,
                                             bg='#1c1f24', fg='#e0e0e0',
                                             selectbackground='#264f78')
        self._3d_anchor_listbox.pack(side="left", fill="both", expand=True)
        self._3d_anchor_listbox.bind('<<ListboxSelect>>', self._on_anchor_select)
        sb = ttk.Scrollbar(list_frame, orient="vertical",
                           command=self._3d_anchor_listbox.yview)
        sb.pack(side="right", fill="y")
        self._3d_anchor_listbox.config(yscrollcommand=sb.set)

        btn_row = ttk.Frame(right)
        btn_row.pack(anchor="w", padx=4, pady=2)
        ttk.Button(btn_row, text="Remove", command=self._remove_selected_anchor).pack(side="left")
        ttk.Button(btn_row, text="Clear all", command=self._clear_anchors).pack(side="left", padx=2)

        ttk.Separator(right, orient="horizontal").pack(fill="x", padx=4, pady=8)
        ttk.Label(right, text="Save / load:",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=4)
        save_row = ttk.Frame(right)
        save_row.pack(anchor="w", padx=4)
        ttk.Button(save_row, text="Save room map", command=self._save_room_map).pack(side="left")
        ttk.Button(save_row, text="Load", command=self._load_room_map).pack(side="left", padx=2)

        ttk.Separator(right, orient="horizontal").pack(fill="x", padx=4, pady=8)
        ttk.Label(right, text="View:",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=4)
        view_row = ttk.Frame(right)
        view_row.pack(anchor="w", padx=4)
        ttk.Button(view_row, text="Top-down", command=lambda: self._set_3d_view(70, -90)).pack(side="left")
        ttk.Button(view_row, text="Front", command=lambda: self._set_3d_view(0, -90)).pack(side="left", padx=2)
        ttk.Button(view_row, text="Side", command=lambda: self._set_3d_view(0, 0)).pack(side="left", padx=2)
        ttk.Button(view_row, text="3/4", command=lambda: self._set_3d_view(30, -60)).pack(side="left", padx=2)

        # Toggle: show hand trail / cameras / anchors
        self._3d_show_trail = tk.BooleanVar(value=True)
        self._3d_show_cameras = tk.BooleanVar(value=True)
        self._3d_show_anchors = tk.BooleanVar(value=True)
        ttk.Checkbutton(right, text="Show hand trail",
                        variable=self._3d_show_trail,
                        command=self._schedule_3d_redraw).pack(anchor="w", padx=4)
        ttk.Checkbutton(right, text="Show cameras",
                        variable=self._3d_show_cameras,
                        command=self._schedule_3d_redraw).pack(anchor="w", padx=4)
        ttk.Checkbutton(right, text="Show anchors",
                        variable=self._3d_show_anchors,
                        command=self._schedule_3d_redraw).pack(anchor="w", padx=4)

        # Initial draw + populate the listbox
        self._refresh_anchor_listbox()
        self._schedule_3d_redraw()

    def _on_3d_click(self, event):
        """Left-click in the 3D view adds an anchor. The click is
        intersected with the horizontal plane at z = self._3d_click_z.
        The result is an (x, y) in the world frame."""
        if self._3d_ax is None or event.inaxes is not self._3d_ax:
            return
        # event.xdata, event.ydata are 2D axes coords (the matplotlib
        # axes are not the same as the 3D world frame). We need to
        # back-project the click to a 3D world ray and intersect with
        # the z = click_z plane.
        try:
            x, y, z = self._pick_3d_at(event.xdata, event.ydata,
                                        float(self._3d_click_z.get()))
        except Exception:
            return
        atype = self._3d_anchor_type.get()
        self.room_map.add(x, y, z, atype=atype)
        self._refresh_anchor_listbox()
        self._schedule_3d_redraw()

    def _pick_3d_at(self, xdisp, ydisp, z):
        """Given a 2D axes-coord click (xdisp, ydisp) and a target
        z-height, compute the 3D (x, y, z) point under the mouse
        cursor by inverting the matplotlib projection matrix.

        matplotlib's Axes3D uses a fixed view matrix; the click
        ray can be recovered by unprojecting two depth points
        (near=0, far=1) and intersecting with the z=z plane.
        """
        # Get the projection matrix that maps 3D world -> 2D display.
        # Axes3D.get_proj() returns the 4x4 matrix, but in newer
        # matplotlib we can use ax.transData.transform + ax.transProjection
        from mpl_toolkits.mplot3d import proj3d
        # Unproject two depth values (0 and 1) at the click point
        try:
            x1, y1, z1 = proj3d.inv_transform(xdisp, ydisp, 0, self._3d_ax.get_proj())
            x2, y2, z2 = proj3d.inv_transform(xdisp, ydisp, 1, self._3d_ax.get_proj())
        except Exception:
            return (0, 0, z)
        # Ray: P = (x1, y1, z1) + t * ((x2,y2,z2) - (x1,y1,z1))
        dx, dy, dz = (x2 - x1), (y2 - y1), (z2 - z1)
        if abs(dz) < 1e-6:
            return (x1, y1, z)
        t = (z - z1) / dz
        return (x1 + t * dx, y1 + t * dy, z)

    def _add_anchor_at_hand(self):
        if self._last_hand_3d is None:
            messagebox.showinfo("Add at hand", "No hand position yet. "
                                "Make sure 3D reconstruction is working and "
                                "your hand is visible to at least 2 cameras.")
            return
        x, y, z = self._last_hand_3d
        atype = self._3d_anchor_type.get()
        self.room_map.add(x, y, z, atype=atype)
        self._refresh_anchor_listbox()
        self._schedule_3d_redraw()

    def _add_anchor_manual(self):
        try:
            x = float(self._3d_manual_x.get())
            y = float(self._3d_manual_y.get())
            z = float(self._3d_manual_z.get())
        except Exception:
            messagebox.showinfo("Manual entry", "x, y, z must be numbers.")
            return
        atype = self._3d_anchor_type.get()
        self.room_map.add(x, y, z, atype=atype)
        self._refresh_anchor_listbox()
        self._schedule_3d_redraw()

    def _remove_selected_anchor(self):
        if self._selected_anchor_id is None:
            return
        self.room_map.remove(self._selected_anchor_id)
        self._selected_anchor_id = None
        self._refresh_anchor_listbox()
        self._schedule_3d_redraw()

    def _clear_anchors(self):
        if not self.room_map.anchors:
            return
        if messagebox.askyesno("Clear anchors",
                               f"Remove all {len(self.room_map.anchors)} anchors?"):
            self.room_map.clear()
            self._selected_anchor_id = None
            self._refresh_anchor_listbox()
            self._schedule_3d_redraw()

    def _save_room_map(self):
        try:
            self.room_map.save()
            messagebox.showinfo("Save room map",
                                f"Saved to {self.room_map.path}")
        except Exception as e:
            messagebox.showerror("Save failed", str(e))

    def _load_room_map(self):
        ok = self.room_map.load()
        if ok:
            self._refresh_anchor_listbox()
            self._schedule_3d_redraw()
            messagebox.showinfo("Load room map", f"Loaded from {self.room_map.path}")
        else:
            messagebox.showwarning("Load failed",
                                   f"No room map found at {self.room_map.path}")

    def _on_anchor_select(self, _event):
        sel = self._3d_anchor_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self.room_map.anchors):
            self._selected_anchor_id = self.room_map.anchors[idx]['id']
            self._schedule_3d_redraw()

    def _refresh_anchor_listbox(self):
        if not hasattr(self, '_3d_anchor_listbox'):
            return
        self._3d_anchor_listbox.delete(0, tk.END)
        for a in self.room_map.anchors:
            self._3d_anchor_listbox.insert(
                tk.END,
                f"#{a['id']:>3}  {a['type']:9s}  ({a['x']:+.2f}, {a['y']:+.2f}, {a['z']:+.2f})  {a['name']}")

    def _set_3d_view(self, elev, azim):
        if self._3d_ax is None:
            return
        self._3d_ax.view_init(elev=elev, azim=azim)
        self._schedule_3d_redraw()

    def _schedule_3d_redraw(self):
        if self._3d_ax is None:
            return
        # Coalesce multiple redraw requests into one (~30 fps max)
        if getattr(self, '_3d_redraw_after_id', None) is None:
            self._3d_redraw_after_id = self.root.after(33, self._redraw_3d_view)

    def _redraw_3d_view(self):
        self._3d_redraw_pending = False
        self._3d_redraw_after_id = None
        if self._3d_ax is None or self._3d_canvas_widget is None:
            return
        ax = self._3d_ax
        # Append to hand trail
        if self._last_hand_3d is not None and self._3d_show_trail.get():
            self._hand_trail.append(self._last_hand_3d)
        # Wipe the axes
        ax.cla()
        # Re-apply style after clear
        ax.set_facecolor('#101418')
        ax.xaxis.pane.set_visible(False)
        ax.yaxis.pane.set_visible(False)
        ax.zaxis.pane.set_visible(False)
        ax.set_xlabel('X (m)', color='#88FF88')
        ax.set_ylabel('Y (m)', color='#88FF88')
        ax.set_zlabel('Z (m)', color='#88FF88')
        ax.tick_params(colors='#88FF88')
        ax.set_title('Room map (drag to rotate)', color='#88FF88')

        # ---- Camera positions and frustums ----
        if self._3d_show_cameras.get() and self.stereo.is_calibrated:
            for i, cal in enumerate(self.stereo.calibrations):
                if cal is None:
                    continue
                # Camera optical center in world: t_i
                cx, cy, cz = cal['t']
                # Forward direction (camera's -Z in OpenCV convention,
                # but in the world frame after R rotation)
                R = cal['R']
                # In OpenCV the camera looks along +Z (after R|t maps
                # world to camera, +Z is "into the scene" in front of
                # the lens). So the world-space forward direction is
                # R^T @ [0, 0, 1] (the world direction of the camera's
                # +Z axis).
                fx, fy, fz = R[2]
                L = 0.4  # frustum length in metres
                ax.plot([cx, cx + L * fx], [cy, cy + L * fy], [cz, cz + L * fz],
                        color='#00aaff', linewidth=1.5)
                # Cone-like tip: 4 rays from the tip back to a quad
                tip = np.array([cx + L * fx, cy + L * fy, cz + L * fz])
                origin = np.array([cx, cy, cz])
                forward = tip - origin
                forward /= np.linalg.norm(forward) + 1e-9
                # Build a basis perpendicular to forward
                up = np.array([0, 0, 1]) if abs(forward[2]) < 0.9 else np.array([0, 1, 0])
                right = np.cross(forward, up); right /= np.linalg.norm(right) + 1e-9
                up = np.cross(right, forward)
                W = 0.25 * L
                for ang in (0, 90, 180, 270):
                    a = np.radians(ang)
                    d = right * (W * np.cos(a)) + up * (W * np.sin(a))
                    p = tip + d
                    ax.plot([cx, p[0]], [cy, p[1]], [cz, p[2]],
                            color='#00aaff', linewidth=0.6, alpha=0.6)
                ax.text(cx, cy, cz + 0.08, f"cam{i}", color='#00aaff',
                        fontsize=8, ha='center')

        # ---- Room anchors ----
        if self._3d_show_anchors.get():
            type_colors = {
                'wall':      '#aa8866',
                'zone':      '#66aaff',
                'hotspot':   '#ff6644',
                'furniture': '#aaaa66',
                'custom':    '#cccccc',
            }
            for a in self.room_map.anchors:
                c = type_colors.get(a['type'], '#cccccc')
                # Sphere via a 3D scatter
                ax.scatter([a['x']], [a['y']], [a['z']],
                           color=c, s=80, marker='o',
                           edgecolors='white', linewidths=0.5)
                # Selected anchor: larger + crosshair
                if a['id'] == self._selected_anchor_id:
                    ax.scatter([a['x']], [a['y']], [a['z']],
                               facecolors='none', edgecolors='#ffff00',
                               s=320, linewidths=2)
                ax.text(a['x'], a['y'], a['z'] + 0.05, a['name'],
                        color='white', fontsize=7, ha='center')

        # ---- Live hand position + trail ----
        if self._last_hand_3d is not None:
            x, y, z = self._last_hand_3d
            ax.scatter([x], [y], [z], color='#00ff66', s=120, marker='*',
                       edgecolors='white', linewidths=0.5)
            ax.text(x, y, z + 0.08, 'HAND', color='#00ff66',
                    fontsize=8, ha='center', weight='bold')
        if self._3d_show_trail.get() and len(self._hand_trail) >= 2:
            xs, ys, zs = zip(*self._hand_trail)
            ax.plot(xs, ys, zs, color='#00ff66', linewidth=0.8, alpha=0.5)

        # ---- Coordinate display in the right panel ----
        if hasattr(self, '_3d_hand_pos_label'):
            if self._last_hand_3d is not None:
                x, y, z = self._last_hand_3d
                self._3d_hand_pos_label.config(
                    text=f"Hand: ({x:+.2f}, {y:+.2f}, {z:+.2f}) m")
            else:
                self._3d_hand_pos_label.config(text="Hand: (no data)")

        # Auto-fit the view to include all points (cameras + anchors + hand)
        all_pts = []
        if self.stereo.is_calibrated and self._3d_show_cameras.get():
            for cal in self.stereo.calibrations:
                if cal is not None:
                    all_pts.append(cal['t'])
        if self._3d_show_anchors.get():
            for a in self.room_map.anchors:
                all_pts.append((a['x'], a['y'], a['z']))
        if self._last_hand_3d is not None:
            all_pts.append(self._last_hand_3d)
        if all_pts:
            pts = np.array(all_pts)
            center = pts.mean(axis=0)
            spread = max(0.6, float(np.linalg.norm(pts - center, axis=1).max()) * 1.4)
            ax.set_xlim(center[0] - spread, center[0] + spread)
            ax.set_ylim(center[1] - spread, center[1] + spread)
            ax.set_zlim(max(0, center[2] - spread), center[2] + spread)
        else:
            ax.set_xlim(-1, 1)
            ax.set_ylim(-1, 1)
            ax.set_zlim(0, 2)

        # Update the live hand trail: record every redraw, not just on 3D data
        self._3d_canvas_widget.draw_idle()

    # -------------------------- Calibration --------------------------
    def start_calibration(self):
        # Open cameras on the fly if the user hasn't clicked Start yet.
        # If the cameras are already open (Start was clicked first),
        # reuse them -- no need to open a second set.
        own_cameras = False
        if self.camera_mgr is None or not self.camera_mgr.cameras:
            try:
                self.camera_mgr = CameraManager(width=480, height=360, fps=30)
                own_cameras = True
            except RuntimeError as e:
                messagebox.showwarning("Calibration", str(e))
                return
        if len(self.camera_mgr.cameras) < 2:
            messagebox.showwarning(
                "Calibration",
                f"Need at least 2 cameras to calibrate. "
                f"Detected: {len(self.camera_mgr.cameras)}. "
                f"Connect a second webcam and try again.")
            return
        messagebox.showinfo("Calibration",
            "Please hold a printed 9x6 INTERIOR-CORNER checkerboard in front "
            "of BOTH cameras.\n"
            "Squares should be 25-30mm on the short side (use the A4 PDF on "
            "your Desktop if you haven't printed one yet).\n"
            "Move the board slowly through the field of view, tilted at "
            "different angles.\n"
            "Click OK to start capturing 15 samples.")
        self.status_label.config(text="Calibrating... hold checkerboard in view of all cameras")
        self.root.update()
        # Progress callback to keep the GUI from appearing frozen
        def _cb(done, total, msg):
            self.calib_label.config(text=f"Calibrating: {done}/{total}")
            self.root.update_idletasks()
        ok, msg = self.stereo.calibrate_all(self.camera_mgr, samples=15,
                                            progress_callback=_cb)
        if ok:
            self.calib_label.config(text=msg)
            self.status_label.config(text="3D calibration ready")
        else:
            self.calib_label.config(text=f"Calibration failed: {msg}")
            self.status_label.config(text="3D calibration NOT ready")
        # If we opened the cameras just for calibration, release them
        # now so the user can click Start cleanly (Start() will
        # re-open them at the canonical resolution).
        if own_cameras and self.camera_mgr is not None:
            self.camera_mgr.release()
            self.camera_mgr = None

    # -------------------------- Notebook tab helpers --------------------------
    def _set_attr(self, name, value):
        setattr(self, name, value)
        # Also propagate to the HandProcessor for the One-Euro / EMA params
        if (name in ('one_euro_min_cutoff', 'one_euro_beta', 'cursor_ema_alpha')
                and hasattr(self, 'hand_proc') and self.hand_proc is not None):
            setattr(self.hand_proc, name, value)

    def _apply_responsiveness(self, value):
        """Apply the responsiveness preset (1..5) to both the App and
        the HandProcessor, then re-sync the individual slider vars so
        the UI reflects the new state. This is called when the user
        moves the preset slider at the top of the Tracking tab."""
        value = max(1, min(5, int(value)))
        self.responsiveness = value
        if hasattr(self, 'hand_proc') and self.hand_proc is not None:
            self.hand_proc.responsiveness = value
            self.hand_proc.adjust()
            # Re-sync the individual sliders so they show the new values
            if hasattr(self, 'oecutoff_var'):
                self.oecutoff_var.set(self.hand_proc.one_euro_min_cutoff)
            if hasattr(self, 'oebeta_var'):
                self.oebeta_var.set(self.hand_proc.one_euro_beta)
            if hasattr(self, 'ema_alpha_var'):
                self.ema_alpha_var.set(self.hand_proc.cursor_ema_alpha)

    def _toggle_key_visibility(self):
        self.ollama_key_entry.config(show="" if self.ollama_key_show.get() else "*")

    def _toggle_selection_overlay(self):
        """Show or hide the persistent selection overlay based on the
        Accessibility-tab checkbox. Start the refresh loop on show,
        cancel + hide on hide."""
        self.show_selection_overlay = bool(self.sel_overlay_var.get())
        if self.show_selection_overlay:
            if self._selection_after_id is None:
                self.refresh_selection_overlay()
        else:
            if self._selection_after_id is not None:
                try:
                    self.root.after_cancel(self._selection_after_id)
                except Exception:
                    pass
                self._selection_after_id = None
            if self.selection_overlay is not None:
                try:
                    self.selection_overlay.withdraw()
                except Exception:
                    pass

    def _save_ollama_settings(self):
        if not self.ollama_enabled_var.get():
            if self.ollama:
                self.ollama.stop()
                self.ollama = None
            self.ollama_label.config(text="off (disabled)")
            return
        endpoint = self.ollama_endpoint_var.get().strip()
        model = self.ollama_model_var.get().strip()
        key = self.ollama_key_var.get().strip()
        prompt = self.ollama_prompt_text.get("1.0", "end").strip() or None
        if not (endpoint and model and key):
            messagebox.showwarning("Ollama", "Endpoint, model, and API key are all required.")
            return
        if self.ollama:
            self.ollama.stop()
        self.ollama = OllamaGestureRecognizer(endpoint, model, key, prompt=prompt)
        self.ollama.query_cooldown = float(self.ollama_cooldown_var.get())
        self.ollama_label.config(text=f"rebuilt ({model})")

    def _toggle_cameras_section(self):
        if self.cameras_visible.get():
            self.cameras_section.pack(fill="x", pady=2)
        else:
            self.cameras_section.pack_forget()

    def _test_camera(self, idx):
        if not self.camera_mgr or idx >= len(self.camera_mgr.cameras):
            messagebox.showinfo("Camera test", "Camera not available.")
            return
        ret, frame = self.camera_mgr.cameras[idx].read()
        if not ret or frame is None:
            messagebox.showinfo("Camera test", f"Camera {idx}: no frame")
            return
        live = self.camera_mgr.is_feed_live(ret, frame)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        messagebox.showinfo(
            "Camera test",
            f"Camera {idx}: {'LIVE' if live else 'BLACK / FROZEN'}\n"
            f"std={np.std(gray):.1f}  brightness={np.mean(gray):.1f}\n"
            f"shape={frame.shape}")

    # -------------------------- GUI Callbacks --------------------------
    def start(self):
        # Disable the button immediately so the user can't double-click
        # and queue up two CameraManager creations. (The button is
        # re-enabled in stop() or in the error path below.)
        self.start_btn.config(state="disabled")
        self.status_label.config(text="Starting... opening cameras")
        # Run the heavy work (camera detection + first frame) on a
        # background thread so the GUI thread stays responsive. We
        # post the result back via root.after() so Tk widgets can
        # be updated safely.
        import threading
        threading.Thread(target=self._start_worker, daemon=True).start()

    def _start_worker(self):
        """Background worker: open cameras, set up GUI widgets, start
        the main loop. Runs OFF the Tk main thread; posts widget
        updates back via root.after(0, ...)."""
        try:
            # Release any previously-opened camera handles first.
            if self.camera_mgr is not None:
                self.camera_mgr.release()
                self.camera_mgr = None
            # Open the cameras on this worker thread (the cv2 work
            # is the slow part -- ~5-10 seconds for 4 cams because
            # of the multi-backend probe and warm-up reads).
            camera_mgr = CameraManager(width=480, height=360, fps=30)
        except Exception as e:
            err = str(e)
            self.root.after(0, lambda: (
                self.status_label.config(text=f"Error: {err}"),
                self.start_btn.config(state="normal"),
            ))
            return
        # Hand the CameraManager back to the main thread. We use
        # a list indirection so the assignment is atomic in Python's
        # GIL, and we keep the cameras-list reference (not a copy).
        self.camera_mgr = camera_mgr
        # Now do the GUI work on the main thread.
        self.root.after(0, self._start_finish_gui)

    def _start_finish_gui(self):
        """Main-thread part of start(): build the per-cam widgets and
        kick off the main loop. By the time this runs, the cameras
        are already open and the user has seen the 'Starting...'
        status update."""
        # Clear out any prior per-cam widgets
        for w in self.feeds_frame.winfo_children():
            w.destroy()
        for w in self.cameras_inner.winfo_children():
            w.destroy()
        for w in self.cameras_list_frame.winfo_children():
            w.destroy()
        self.camera_vars = {}
        self.camera_canvases = {}
        for i, cap in enumerate(self.camera_mgr.cameras):
            # Right side: live video canvas
            frame = ttk.LabelFrame(self.feeds_frame, text=f"Camera {i}")
            frame.grid(row=0, column=i, padx=5, pady=5, sticky="nsew")
            self.feeds_frame.columnconfigure(i, weight=1)
            self.feeds_frame.rowconfigure(0, weight=1)
            canvas = tk.Canvas(frame, width=480, height=360, bg="black")
            canvas.pack(fill="both", expand=True)
            self.camera_canvases[i] = canvas
            # Main tab: per-camera enable checkbox
            var = tk.BooleanVar(value=True)
            ttk.Checkbutton(self.cameras_inner, text=f"Camera {i}",
                            variable=var).pack(anchor="w")
            self.camera_vars[i] = var
            # Cameras tab: detailed row with test button
            row = ttk.Frame(self.cameras_list_frame)
            row.pack(fill="x", padx=2, pady=2)
            w_prop = int(cap.get(3))
            h_prop = int(cap.get(4))
            fps_prop = cap.get(cv2.CAP_PROP_FPS) or 30.0
            backend_id = int(cap.get(cv2.CAP_PROP_BACKEND))
            info = (f"idx={i}  {w_prop}x{h_prop}  backend={backend_id}  "
                    f"fps={fps_prop:.0f}")
            ttk.Label(row, text=info).pack(side="left")
            ttk.Button(row, text="Test",
                       command=lambda idx=i: self._test_camera(idx)
                       ).pack(side="right")
        self.running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.calibrate_btn.config(state="normal")
        self.status_label.config(text=f"Running with {len(self.camera_mgr.cameras)} camera(s)")
        # Start the persistent selection overlay refresh loop
        if self.show_selection_overlay and self._selection_after_id is None:
            self.refresh_selection_overlay()
        # Schedule the FIRST loop on the main thread so the GUI can
        # paint the "Running" status + new camera frames BEFORE the
        # first loop iteration blocks on MediaPipe. This is the key
        # fix: previously, start() called self.loop() synchronously,
        # which meant the first MediaPipe inference + 4 cam reads
        # all ran before the user saw any update.
        self.root.after(50, self.loop)

    def stop(self):
        self.running = False
        if self.camera_mgr:
            self.camera_mgr.release()
            self.camera_mgr = None
        if self.loop_id:
            self.root.after_cancel(self.loop_id)
            self.loop_id = None
        # Stop the selection overlay refresh loop
        if self._selection_after_id is not None:
            try:
                self.root.after_cancel(self._selection_after_id)
            except Exception:
                pass
            self._selection_after_id = None
        if self.selection_overlay is not None:
            try:
                self.selection_overlay.withdraw()
            except Exception:
                pass
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.calibrate_btn.config(state="disabled")
        self.status_label.config(text="Stopped")
        for c in self.camera_canvases.values():
            c.delete("all")

    def on_close(self):
        self.stop()
        if self.ollama:
            self.ollama.stop()
        # Stop the MediaPipe inference worker (daemon thread would
        # otherwise stay alive until the process exits)
        try:
            self.hand_proc._stop_worker = True
        except Exception:
            pass
        # Cancel any pending 3D redraw
        try:
            if getattr(self, '_3d_redraw_after_id', None) is not None:
                self.root.after_cancel(self._3d_redraw_after_id)
        except Exception:
            pass
        # Auto-save the room map (it's lightweight, always save it)
        try:
            self.room_map.save()
        except Exception:
            pass
        self.root.destroy()

    # -------------------------- Main Loop --------------------------
    def loop(self):
        if not self.running:
            return

        loop_t0 = time.time()
        self._frame_counter += 1
        run_mp = (self._frame_counter % max(1, self.mediapipe_skip) == 0)
        raw = self.camera_mgr.read_all()
        processed_frames = []
        per_cam_landmarks = []
        live_fps = []
        # Clear _last_displays on MediaPipe frames so we always
        # have a fresh copy of the new frame. On intermediate
        # frames we reuse the last drawn display to skip the
        # frame.copy() cost.
        if run_mp:
            self._last_displays = {}
        # Throttle expensive per-frame checks
        check_feed = (self._frame_counter % 10 == 0)  # every 10th frame
        check_fps = (self._frame_counter % 30 == 0)  # every 30th frame
        # Per-cam enable state: cache as a list of bools once per
        # loop to avoid the per-frame Tk BooleanVar.get() overhead
        # (each call goes through Tcl). With 4 cams x 30 fps
        # that's 120 Tcl calls/sec saved.
        cam_enabled = [bool(self.camera_vars[i].get())
                       if i < len(self.camera_vars) else False
                       for i in range(len(raw))]

        for i, (ret, frame) in enumerate(raw):
            # GUI disable: skip processing AND rendering, show as disabled
            if not cam_enabled[i]:
                processed_frames.append((i, None, None))
                per_cam_landmarks.append(None)
                self._cached_landmarks.pop(i, None)
                continue
            if not ret:
                processed_frames.append((i, None, None))
                per_cam_landmarks.append(None)
                self._cached_landmarks.pop(i, None)
                continue
            # Black / no-signal feed: skip MediaPipe + HUD entirely.
            # Cached for 10 frames since the live status doesn't change
            # in 1/3 second unless the camera is unplugged.
            if check_feed:
                self._live_cache[i] = self.camera_mgr.is_feed_live(ret, frame)
            if not self._live_cache.get(i, True):
                processed_frames.append((i, None, None))
                per_cam_landmarks.append(None)
                self._cached_landmarks.pop(i, None)
                continue
            if check_fps:
                live_fps.append(self.camera_mgr.get_actual_fps(i))
            else:
                # Reuse last cached FPS for pacing
                if i in self._fps_cache:
                    live_fps.append(self._fps_cache[i])
            # Run MediaPipe only every Nth frame; reuse cached landmarks otherwise
            if run_mp:
                det = self.hand_proc.detect(frame)
                landmarks = det.hand_landmarks[0] if det and det.hand_landmarks else None
                self._cached_landmarks[i] = landmarks
            else:
                landmarks = self._cached_landmarks.get(i)
            # Only copy the frame if we'll actually draw on it. The
            # canvas redraw is throttled via after(15,...) so we don't
            # need a fresh copy every loop iter -- reuse the last one
            # for all intermediate frames. This saves ~0.5ms/camera/frame.
            display = self._last_displays.get(i)
            if display is None or run_mp:
                display = frame.copy()
            if landmarks:
                self.draw_hud(display, landmarks)
            self._last_displays[i] = display
            processed_frames.append((i, display, landmarks))
            per_cam_landmarks.append(landmarks)
        # Stash the latest FPS for the cached path. Only update cams
        # that actually got a fresh FPS sample this iteration (i.e.
        # the live cams we passed through to check_fps above). This
        # used to have an off-by-one bug where index `i` in the
        # outer loop was used to index into live_fps, but live_fps
        # only contains entries for cams that were actually
        # processed (skipped cams have no entry), so the wrong cam
        # could be assigned the wrong FPS. Walk both lists in lockstep.
        if check_fps and live_fps:
            cam_sample_idx = 0
            for i in range(len(raw)):
                if i in self._live_cache and self._live_cache[i]:
                    if cam_sample_idx < len(live_fps):
                        self._fps_cache[i] = live_fps[cam_sample_idx]
                        cam_sample_idx += 1

        # Intent detection
        any_palm = False
        for lm in per_cam_landmarks:
            if lm and self.hand_proc.is_palm_open(lm):
                any_palm = True
                break
        self.intent_history.append(1 if any_palm else 0)
        avg_intent = np.mean(self.intent_history) if self.intent_history else 0
        if avg_intent > 0.6:
            if not self.engaged:
                if self.engaged_time == 0:
                    self.engaged_time = time.time()
                elif time.time() - self.engaged_time >= self.engage_hold_seconds:
                    self.engaged = True
        else:
            self.engaged = False
            self.engaged_time = 0
        self.intent_label.config(text="Engaged" if self.engaged else "Disengaged")

        # Gestures (only when engaged and hand visible)
        if self.engaged and any(lm is not None for lm in per_cam_landmarks):
            for i, disp, lm in processed_frames:
                if lm is not None:
                    self.handle_gestures(lm, i, disp, per_cam_landmarks)
                    break

        # Ollama
        if self.ollama and (self._frame_counter % max(1, self._ollama_frame_skip) == 0):
            for i, (ret, frame) in enumerate(raw):
                if ret and self.camera_vars[i].get() and self.camera_mgr.is_feed_live(ret, frame):
                    self.ollama.submit_frame(frame)
                    break
            gesture = self.ollama.get_gesture()
            if gesture and gesture != self.last_ollama_gesture:
                self.last_ollama_gesture = gesture
                self.ollama_label.config(text=gesture)
                if gesture == 'engage':
                    self.engaged = True
                elif gesture == 'disengage':
                    self.engaged = False
                if self.engaged and gesture in ['swipe_left','swipe_right','swipe_up','swipe_down']:
                    self.accessibility_focus(gesture)
            else:
                self.ollama_label.config(text=gesture or "off")

        # Update canvases (preserving aspect ratio, no stretching).
        # Cache the black background per canvas to avoid reallocating per frame.
        for i, disp, _ in processed_frames:
            canvas = self.camera_canvases[i]
            cw = max(2, canvas.winfo_width())
            ch = max(2, canvas.winfo_height())
            if disp is None:
                canvas.delete("all")
                canvas.create_text(cw // 2, ch // 2,
                                   text="Disabled / No live feed", fill="white")
                canvas._bg_cache = None
                continue
            # Skip if a redraw is already pending (don't pile up work)
            if getattr(canvas, '_redraw_pending', False):
                continue
            canvas._redraw_pending = True
            canvas.after(15, lambda c=canvas: self._redraw_canvas(c))
            # Defer the actual redraw off the hot path

    def _redraw_canvas(self, canvas):
        canvas._redraw_pending = False
        # Find this canvas in camera_canvases to get its current frame
        for i, c in self.camera_canvases.items():
            if c is canvas:
                disp = getattr(self, '_last_displays', {}).get(i)
                if disp is None:
                    return
                cw = max(2, canvas.winfo_width())
                ch = max(2, canvas.winfo_height())
                fh, fw = disp.shape[:2]
                scale = min(cw / fw, ch / fh)
                new_w = max(1, int(fw * scale))
                new_h = max(1, int(fh * scale))
                disp_resized = cv2.resize(disp, (new_w, new_h),
                                          interpolation=cv2.INTER_AREA)
                bg = getattr(canvas, '_bg_cache', None)
                if (bg is None or bg.shape[0] != ch or bg.shape[1] != cw):
                    bg = np.zeros((ch, cw, 3), dtype=np.uint8)
                    canvas._bg_cache = bg
                canvas_img = bg.copy()
                x_off = (cw - new_w) // 2
                y_off = (ch - new_h) // 2
                canvas_img[y_off:y_off + new_h, x_off:x_off + new_w] = disp_resized
                img = cv2.cvtColor(canvas_img, cv2.COLOR_BGR2RGB)
                im = Image.fromarray(img)
                imgtk = ImageTk.PhotoImage(image=im)
                canvas.imgtk = imgtk
                canvas.delete("all")
                canvas.create_image(0, 0, anchor="nw", image=imgtk)
                return

        # Adaptive loop pacing: aim for the FASTEST live camera's FPS so
        # latency stays low. If we're behind, schedule the next tick
        # immediately instead of waiting further.
        if live_fps:
            target_fps = max(live_fps)
        else:
            target_fps = 30.0  # idle
        target_fps = max(15.0, min(60.0, target_fps))
        elapsed_ms = (time.time() - loop_t0) * 1000.0
        # ---- Timing instrumentation (rolling 30-frame window) ----
        # Update the FPS label every ~15 frames so it doesn't flicker.
        self._loop_ms_hist.append(elapsed_ms)
        if self._frame_counter % 15 == 0 and self._loop_ms_hist:
            avg_ms = sum(self._loop_ms_hist) / len(self._loop_ms_hist)
            actual_fps = 1000.0 / max(1, avg_ms)
            if hasattr(self, 'loop_stats_label'):
                self.loop_stats_label.config(
                    text=f"loop: {avg_ms:5.1f} ms  ({actual_fps:4.1f} fps)"
                    f"  |  target: {target_fps:4.1f} fps")
            # Also update the CPU / RAM readout. Uses win32
            # GetProcessTimes + GetProcessMemoryInfo. Cheap (<0.1ms)
            # and lets the user see *exactly* how much CPU the app
            # is using, separate from the system total.
            if hasattr(self, 'cpu_stats_label'):
                self._update_cpu_stats_label()
        target_ms = 1000.0 / target_fps
        wait_ms = int(target_ms - elapsed_ms)
        if wait_ms < 1:
            wait_ms = 1  # at least 1ms so the GUI thread can breathe
        self.loop_id = self.root.after(wait_ms, self.loop)

    def _update_cpu_stats_label(self):
        """Refresh the cpu/ram/threads label. Win32-only, no deps."""
        import ctypes
        from ctypes import wintypes
        try:
            psapi = ctypes.WinDLL('psapi', use_last_error=True)
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            GetCurrentProcess = kernel32.GetCurrentProcess
            GetCurrentProcess.restype = wintypes.HANDLE
            hproc = GetCurrentProcess()
            # ---- CPU time (user + kernel) delta over wall time ----
            class FILETIME(ctypes.Structure):
                _fields_ = [("dwLowDateTime", ctypes.c_uint32),
                            ("dwHighDateTime", ctypes.c_uint32)]
            ct_pcpu = FILETIME(); ct_pcpu2 = FILETIME()
            ct_pkc = FILETIME(); ct_pkc2 = FILETIME()
            ct_puc = FILETIME(); ct_puc2 = FILETIME()
            ok = kernel32.GetProcessTimes(hproc, ctypes.byref(ct_pcpu),
                                          ctypes.byref(ct_pcpu2),
                                          ctypes.byref(ct_pkc),
                                          ctypes.byref(ct_puc))
            ft_to_100ns = lambda ft: (ft.dwHighDateTime << 32) | ft.dwLowDateTime
            if ok:
                proc_100ns = ft_to_100ns(ct_pkc) + ft_to_100ns(ct_puc)
                now = time.time()
                if self._proc_times_cache is not None:
                    last_t, last_proc = self._proc_times_cache
                    dt_wall = now - last_t
                    if dt_wall > 0:
                        # 100ns units -> seconds, divided by wall dt
                        # to get a fraction, then * 100 for percent.
                        # We report "of one CPU" since that's what
                        # users actually feel (Task Manager's "CPU"
                        # column normalizes by num-CPUs; we don't).
                        self._last_cpu_pct = (
                            (proc_100ns - last_proc) / 1e7 / dt_wall * 100.0)
                self._proc_times_cache = (now, proc_100ns)
            # ---- Working set size in MB ----
            class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_uint32),
                    ("PageFaultCount", ctypes.c_uint32),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                    ("PrivateUsage", ctypes.c_size_t),
                ]
            mem = PROCESS_MEMORY_COUNTERS_EX()
            mem.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
            if psapi.GetProcessMemoryInfo(hproc, ctypes.byref(mem), mem.cb):
                ram_mb = mem.WorkingSetSize / (1024 * 1024)
            else:
                ram_mb = 0
            # ---- Thread count via Python's threading module ----
            import threading
            n_threads = threading.active_count()
            # ---- Update the label ----
            self.cpu_stats_label.config(
                text=f"cpu: {self._last_cpu_pct:5.1f} %  "
                     f"ram: {ram_mb:6.1f} MB  "
                     f"threads: {n_threads:3d}")
        except Exception as e:
            # On any error, blank the label so it doesn't show garbage
            self.cpu_stats_label.config(text=f"cpu/ram: (error: {e})")

    # -------------------------- Gestures --------------------------
    def handle_gestures(self, landmarks, cam_idx, display, all_landmarks):
        # Per-frame dt for One-Euro filter
        now = time.time()
        dt = 1/30
        if hasattr(self, '_last_hand_ts') and self._last_hand_ts:
            dt = max(1.0/120, min(0.2, now - self._last_hand_ts))
        self._last_hand_ts = now

        # Update all 5 tip filters + velocity estimates from the new
        # MediaPipe landmarks. This also updates the per-tip prediction
        # timestamps so predict() knows the last detection time.
        for tip in (self.hand_proc.thumb_tip,
                    self.hand_proc.index_tip,
                    self.hand_proc.middle_tip,
                    self.hand_proc.ring_tip,
                    self.hand_proc.pinky_tip):
            self.hand_proc.smooth(tip, landmarks[tip].x, landmarks[tip].y, dt=dt)

        # Now read the FRESHEST position (predicted forward to "now") for
        # every tip. This is the difference between 1:1 tracking and
        # "the cursor trails behind my hand" -- the predictor fills the
        # 10-50ms gap between MediaPipe detections.
        # predict() may return None if a tip has never been seen yet
        # (very first frame); in that case fall back to the raw landmark
        # for that tip only.
        def _px(tip_id, raw_lm):
            p = self.hand_proc.predict(tip_id, now=now)
            if p is None:
                return (raw_lm.x, raw_lm.y)
            return p
        idx_x, idx_y = _px(self.hand_proc.index_tip,
                           landmarks[self.hand_proc.index_tip])
        thb_x, thb_y = _px(self.hand_proc.thumb_tip,
                           landmarks[self.hand_proc.thumb_tip])
        mid_x, mid_y = _px(self.hand_proc.middle_tip,
                           landmarks[self.hand_proc.middle_tip])
        rng_x, rng_y = _px(self.hand_proc.ring_tip,
                           landmarks[self.hand_proc.ring_tip])
        pnk_x, pnk_y = _px(self.hand_proc.pinky_tip,
                           landmarks[self.hand_proc.pinky_tip])

        idx_px = (int(idx_x * self.screen_width), int(idx_y * self.screen_height))
        margin_x = int(self.screen_width * 0.05)
        margin_y = int(self.screen_height * 0.05)
        tx = max(margin_x, min(self.screen_width - margin_x, idx_px[0]))
        ty = max(margin_y, min(self.screen_height - margin_y, idx_px[1]))

        # Move the screen cursor ONLY if the user has explicitly enabled it.
        # Default behaviour is accessibility-navigation only (no mouse).
        if self.enable_screen_cursor:
            alpha = self.cursor_ema_alpha
            if self.hand_proc.cursor_ema is None:
                self.hand_proc.cursor_ema = (tx, ty)
            else:
                cx, cy = self.hand_proc.cursor_ema
                nx = cx + alpha * (tx - cx)
                ny = cy + alpha * (ty - cy)
                # Velocity clamp: with the predictor upstream, the input
                # (tx, ty) is already very accurate, so we can be
                # generous here. Use 10000 px/s (10 px per ms) which
                # only clamps absurd teleports, not real motion.
                max_step = 10000 * dt
                dx, dy = nx - cx, ny - cy
                dist = math.hypot(dx, dy)
                if dist > max_step and dist > 0:
                    nx = cx + dx / dist * max_step
                    ny = cy + dy / dist * max_step
                self.hand_proc.cursor_ema = (nx, ny)
            cx, cy = self.hand_proc.cursor_ema
            pyautogui.moveTo(int(cx), int(cy))

        # Click detection: use PREDICTED positions (in normalized coords)
        # rather than the raw MediaPipe landmark, so the click registers
        # at the same wall-clock moment as the gesture, not 30-50ms later.
        # We synthesize lightweight landmark objects so the d() lambda works.
        class _P:
            __slots__ = ('x', 'y')
            def __init__(self, x, y):
                self.x, self.y = x, y
        thumb = _P(thb_x, thb_y)
        index = _P(idx_x, idx_y)
        middle = _P(mid_x, mid_y)
        ring = _P(rng_x, rng_y)
        pinky = _P(pnk_x, pnk_y)
        # Click distance in NORMALIZED coords, not pixels. This makes
        # the click threshold camera-resolution-independent: a 0.08
        # normalized distance is "thumb tip near index tip" regardless
        # of which camera the landmarks came from.
        d_norm = lambda a, b: math.hypot(a.x - b.x, a.y - b.y)
        # Auto-scale the click threshold: 40px on a 1080p screen is
        # ~40/1080 = 0.037 normalized. The user can still tune via slider.
        th = self.click_threshold_px / max(self.screen_height, 1) * 4
        # NOTE: kept the old pixel-style threshold lookup for backward
        # compat with users who set it; multiplying by 4 and dividing
        # by screen_height gives roughly the same feel as before.
        if d_norm(thumb, index) < th:
            pyautogui.press('enter')  # activate currently focused element
        if d_norm(thumb, middle) < th:
            pyautogui.press('apps')   # context menu
        if d_norm(thumb, ring) < th:
            pyautogui.press('up')     # scroll / move up
        if d_norm(thumb, pinky) < th:
            pyautogui.press('down')   # scroll / move down

        # 3D reconstruction for all 5 fingertips (if calibrated and >= 2 cams)
        # Uses the proper shared-world-frame pipeline:
        #   - MediaPipe landmarks are normalized [0, 1] in each camera's image
        #   - We convert to pixel coords using that camera's image size
        #   - StereoCalibrator.undistort + K^-1 + ray triangulation
        if self.enable_3d_display and self.stereo.is_calibrated:
            # Build per-camera (x_px, y_px) lists for the 5 fingertips
            tip_indices = (self.hand_proc.thumb_tip,
                           self.hand_proc.index_tip,
                           self.hand_proc.middle_tip,
                           self.hand_proc.ring_tip,
                           self.hand_proc.pinky_tip)
            # Convert normalized [0,1] landmarks to pixel coords using
            # each camera's own image size. image_sizes[i] = (w, h)
            fingertip_pixels = []  # list of lists: [cam_i][tip_j] = (x_px, y_px) or None
            for i, lm in enumerate(all_landmarks):
                if lm is None:
                    fingertip_pixels.append([None] * len(tip_indices))
                    continue
                w_i, h_i = self.stereo.image_sizes[i] if i < len(self.stereo.image_sizes) \
                    else (self.camera_mgr.get_width(i), self.camera_mgr.get_height(i))
                if w_i <= 0 or h_i <= 0:
                    w_i, h_i = self.camera_mgr.get_width(i), self.camera_mgr.get_height(i)
                pix = []
                for t in tip_indices:
                    pix.append((lm[t].x * w_i, lm[t].y * h_i))
                fingertip_pixels.append(pix)
            # Reconstruct each tip independently
            tip_3d = []
            for j, t in enumerate(tip_indices):
                pts = [fp[j] for fp in fingertip_pixels]
                X = self.stereo.reconstruct_3d(pts)
                tip_3d.append(X)
            valid_tips = [X for X in tip_3d if X is not None]
            if valid_tips:
                # Show the index fingertip 3D position (most useful)
                idx_X = tip_3d[1]  # index tip
                if idx_X is not None:
                    # Stash the latest 3D position for the "use live
                    # hand position" button in the 3D tab.
                    self._last_hand_3d = tuple(float(x) for x in idx_X)
                    cv2.putText(display, f"3D index: {idx_X[0]:+.2f}, {idx_X[1]:+.2f}, {idx_X[2]:+.2f} m",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                    # Schedule a 3D-view redraw at ~5Hz (don't repaint
                    # the matplotlib canvas every frame, that would
                    # dominate the GUI cost).
                    if self._3d_redraw_pending is False:
                        self._3d_redraw_pending = True
                        self.root.after(200, self._redraw_3d_view)
                # If we have at least 3 fingertips, draw a 3D bounding box
                # from min/max x,y,z on the first camera display.
                if len(valid_tips) >= 3:
                    xs = [X[0] for X in valid_tips]
                    ys = [X[1] for X in valid_tips]
                    zs = [X[2] for X in valid_tips]
                    cv2.putText(display,
                                f"spread: {max(xs)-min(xs):.2f} x {max(ys)-min(ys):.2f} x {max(zs)-min(zs):.2f} m",
                                (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1)

        # Swipe -> accessibility
        # Use the PREDICTED index position so the swipe velocity
        # reflects the user's *current* intent, not 30-50ms-stale data.
        # This is what makes swipes feel responsive enough to be useful
        # for fast navigation through UI elements.
        p = self.hand_proc.predict(self.hand_proc.index_tip, now=now)
        if p is not None:
            swipe_px = (int(p[0] * self.screen_width), int(p[1] * self.screen_height))
        else:
            swipe_px = idx_px
        self.index_history.append((now, swipe_px[0], swipe_px[1]))
        while self.index_history and now - self.index_history[0][0] > 1.0:
            self.index_history.popleft()
        if len(self.index_history) >= 2 and (now - self.last_swipe_time) > self.swipe_cooldown:
            t0, x0, y0 = self.index_history[0]
            t1, x1, y1 = self.index_history[-1]
            dt_s = t1 - t0
            if dt_s > 0.1:
                vx = (x1 - x0) / dt_s
                vy = (y1 - y0) / dt_s
                speed = math.sqrt(vx*vx + vy*vy)
                if speed > self.swipe_min_speed:
                    if abs(vx) > 2 * abs(vy):
                        if vx > 0:
                            self.accessibility_focus('swipe_right')
                        else:
                            self.accessibility_focus('swipe_left')
                    elif abs(vy) > 2 * abs(vx):
                        if vy > 0:
                            self.accessibility_focus('swipe_down')
                        else:
                            self.accessibility_focus('swipe_up')
                    self.last_swipe_time = now

    def flash_overlay(self, direction, duration_ms=400):
        """Show the focus-highlight overlay for `duration_ms` then hide it.
        Creates the overlay Toplevel lazily on first use (so app startup is fast).
        Also re-positions the persistent selection overlay to the currently
        focused UI element (the "selection" the user just moved to)."""
        # Build the overlay the first time it's needed
        if self.overlay is None:
            self.overlay = tk.Toplevel(self.root)
            self.overlay.overrideredirect(True)
            self.overlay.attributes('-topmost', True)
            self.overlay.attributes('-disabled', False)
            try:
                self.overlay.attributes('-transparentcolor', 'white')
            except Exception:
                pass
            try:
                import ctypes
                hwnd = int(self.overlay.frame(), 0) if hasattr(self.overlay, 'frame') else 0
                if hwnd:
                    GWL_EXSTYLE = -20
                    WS_EX_TRANSPARENT = 0x20
                    WS_EX_LAYERED = 0x80000
                    WS_EX_TOOLWINDOW = 0x80
                    HWND_TOPMOST = -1
                    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    style |= WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW
                    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
                    SWP_NOMOVE = 0x0002
                    SWP_NOSIZE = 0x0001
                    SWP_NOACTIVATE = 0x0010
                    ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                                      SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
            except Exception:
                pass
            self.overlay_canvas = tk.Canvas(self.overlay, bg='white', highlightthickness=0)
            self.overlay_canvas.pack(fill='both', expand=True)
        # Cancel any pending hide
        if self._overlay_after_id is not None:
            try:
                self.overlay.after_cancel(self._overlay_after_id)
            except Exception:
                pass
            self._overlay_after_id = None
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        # Validate the highlight color string. tk.Canvas.create_rectangle
        # accepts "#RRGGBB" or named colors like "green", but NOT bare
        # hex like "00FF00" (TclError: unknown color name). Prepend '#'
        # only when the string is bare hex (6 hex chars, no '#').
        c = self.focus_highlight_color or "#00FF00"
        if not c.startswith('#') and len(c) == 6 and all(
                ch in '0123456789abcdefABCDEF' for ch in c):
            c = '#' + c
        # (rgb is kept for any future use; tk accepts the '#XXXXXX' form directly)
        if len(c) == 7:
            rgb = (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
        else:
            rgb = (0, 255, 0)
            c = "#00FF00"
        thickness = max(1, int(self.focus_highlight_thickness))
        self.overlay.geometry(f"{sw}x{sh}+0+0")
        self.overlay_canvas.config(width=sw, height=sh)
        self.overlay_canvas.delete('all')
        # Draw border (4 rects)
        self.overlay_canvas.create_rectangle(0, 0, sw, thickness, fill=c, outline=c)
        self.overlay_canvas.create_rectangle(0, sh - thickness, sw, sh, fill=c, outline=c)
        self.overlay_canvas.create_rectangle(0, 0, thickness, sh, fill=c, outline=c)
        self.overlay_canvas.create_rectangle(sw - thickness, 0, sw, sh, fill=c, outline=c)
        # Big direction label
        label = f"Focus: {direction.replace('swipe_', '').upper()}"
        self.overlay_label = self.overlay_canvas.create_text(
            sw // 2, sh // 2, text=label, font=("Segoe UI", 96, "bold"),
            fill=c)
        self.overlay.deiconify()
        self.overlay.lift()
        self._overlay_after_id = self.overlay.after(
            duration_ms, self._hide_overlay)
        # Also refresh the persistent selection indicator so the user
        # can see WHERE the focus moved to.
        self.refresh_selection_overlay()

    def _hide_overlay(self):
        try:
            self.overlay.withdraw()
        except Exception:
            pass
        self._overlay_after_id = None

    def _get_focused_element_rect(self):
        """Return (x, y, w, h) of the currently focused UI element,
        or None if not available. Uses win32 GetGUIThreadInfo to find
        the focused control in the foreground thread. Works for native
        Win32, UWP, and most modern Windows apps.

        Falls back to the foreground window's rect if no specific
        focus control can be determined."""
        try:
            import ctypes
            from ctypes import wintypes
            import struct
            # Get the foreground window
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd:
                return None
            # Get the foreground thread, then its GUI info.
            # GUITHREADINFO layout (64-bit):
            #   DWORD  cbSize         (offset 0,  4 bytes)
            #   DWORD  flags          (offset 4,  4 bytes)
            #   HWND   hwndActive     (offset 8,  8 bytes)
            #   HWND   hwndFocus      (offset 16, 8 bytes)
            #   HWND   hwndCapture    (offset 24, 8 bytes)
            #   HWND   hwndMenuOwner  (offset 32, 8 bytes)
            #   HWND   hwndMoveSize   (offset 40, 8 bytes)
            #   HWND   hwndCaret      (offset 48, 8 bytes)
            #   RECT   rcCaret        (offset 56, 16 bytes)
            #   Total: 72 bytes
            thread_id = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None)
            gui_info = ctypes.create_string_buffer(72)
            # CRITICAL: GetGUIThreadInfo requires cbSize to be set,
            # otherwise it returns zeros and we get the whole screen.
            struct.pack_into('I', gui_info, 0, 72)
            ok = ctypes.windll.user32.GetGUIThreadInfo(thread_id, gui_info)
            if not ok:
                return None
            focus_hwnd = struct.unpack_from('P', gui_info, 16)[0]
            target = focus_hwnd if focus_hwnd else hwnd
            # Get the window rect
            rect = ctypes.wintypes.RECT()
            ok = ctypes.windll.user32.GetWindowRect(target, ctypes.byref(rect))
            if not ok:
                return None
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w <= 0 or h <= 0:
                return None
            return (rect.left, rect.top, w, h)
        except Exception:
            return None

    def refresh_selection_overlay(self):
        """Re-position the persistent selection overlay (a small border
        around the currently-focused UI element) so the user always
        sees what will be activated by the next click. Builds the
        overlay lazily on first use, and schedules a periodic refresh
        so the overlay follows focus changes from any source
        (keyboard, mouse, swipe)."""
        # Build on first use
        if not hasattr(self, 'selection_overlay') or self.selection_overlay is None:
            self.selection_overlay = tk.Toplevel(self.root)
            self.selection_overlay.overrideredirect(True)
            self.selection_overlay.attributes('-topmost', True)
            try:
                self.selection_overlay.attributes('-transparentcolor', 'white')
            except Exception:
                pass
            try:
                import ctypes
                hwnd = int(self.selection_overlay.frame(), 0) if hasattr(self.selection_overlay, 'frame') else 0
                if hwnd:
                    GWL_EXSTYLE = -20
                    WS_EX_TRANSPARENT = 0x20
                    WS_EX_LAYERED = 0x80000
                    WS_EX_TOOLWINDOW = 0x80
                    HWND_TOPMOST = -1
                    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    style |= WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW
                    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
                    SWP_NOACTIVATE = 0x0010
                    ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                                      SWP_NOACTIVATE)
            except Exception:
                pass
            self.selection_canvas = tk.Canvas(self.selection_overlay,
                                              bg='white', highlightthickness=0)
            self.selection_canvas.pack(fill='both', expand=True)
            self._selection_hwnd = 0  # track the last focused hwnd
        # Get the focused element rect
        rect = self._get_focused_element_rect()
        if rect is None:
            # Nothing to highlight (no foreground window); hide
            try:
                self.selection_overlay.withdraw()
            except Exception:
                pass
        else:
            x, y, w, h = rect
            # Slightly expand the border so it's visible even on tiny elements
            pad = 4
            sw, sh = w + 2*pad, h + 2*pad
            self.selection_overlay.geometry(f"{sw}x{sh}+{x-pad}+{y-pad}")
            self.selection_canvas.config(width=sw, height=sh)
            self.selection_canvas.delete('all')
            # Use a slightly different colour so the user can tell the
            # persistent "selection" overlay apart from the brief
            # "swipe direction" flash overlay.
            # Validate the color string for tk. tk accepts:
            #   - "#RRGGBB" (hex with #)         - valid
            #   - "RRGGBB"  (bare hex)           - INVALID -> TclError
            #   - "red", "green" (named colors)  - valid
            # So: only prepend '#' if it's bare hex (6 hex chars, no '#').
            c = self.focus_highlight_color or "#00FF00"
            if not c.startswith('#') and len(c) == 6 and all(
                    ch in '0123456789abcdefABCDEF' for ch in c):
                c = '#' + c
            t = max(2, int(self.focus_highlight_thickness))
            # Draw a chunky ring around the focused element
            self.selection_canvas.create_rectangle(
                0, 0, sw, t, fill=c, outline=c)
            self.selection_canvas.create_rectangle(
                0, sh - t, sw, sh, fill=c, outline=c)
            self.selection_canvas.create_rectangle(
                0, 0, t, sh, fill=c, outline=c)
            self.selection_canvas.create_rectangle(
                sw - t, 0, sw, sh, fill=c, outline=c)
            # Small "SELECTED" label at the top-right of the ring
            try:
                self.selection_canvas.create_text(
                    sw - 8, 8, text="SELECTED", anchor="ne",
                    font=("Segoe UI", 9, "bold"), fill=c)
            except Exception:
                pass
            try:
                self.selection_overlay.deiconify()
                self.selection_overlay.lift()
            except Exception:
                pass
        # Schedule next refresh. Polling 10x/sec is cheap and keeps the
        # overlay accurate even when the user clicks with a mouse or
        # types on the keyboard.
        self._selection_after_id = self.root.after(100, self.refresh_selection_overlay)

    def accessibility_focus(self, direction):
        """Send directional focus key. In tab mode: Tab/Shift+Tab/Arrow up/down.
        In arrow mode: pure arrow keys. Visual highlight overlay flashes."""
        if time.time() < self._dwell_until:
            return
        if self.nav_mode == 'tab':
            if direction == 'swipe_right':
                pyautogui.press('tab')
            elif direction == 'swipe_left':
                pyautogui.hotkey('shift', 'tab')
            elif direction == 'swipe_up':
                pyautogui.press('up')
            elif direction == 'swipe_down':
                pyautogui.press('down')
        else:  # arrow mode
            if direction == 'swipe_right':
                pyautogui.press('right')
            elif direction == 'swipe_left':
                pyautogui.press('left')
            elif direction == 'swipe_up':
                pyautogui.press('up')
            elif direction == 'swipe_down':
                pyautogui.press('down')
        # Flash focus overlay
        self.flash_overlay(direction)
        if self.focus_dwell > 0:
            self._dwell_until = time.time() + self.focus_dwell

    # -------------------------- HUD Drawing --------------------------
    def draw_hud(self, frame, landmarks):
        """Draw the Tony Stark HUD overlay on `frame`.

        Performance: with 4 cameras x 30 fps, the HUD used to
        consume ~10ms/cam/frame of pure cv2 calls (~30% of one CPU
        core). Two optimizations here:

        1. Cache the static base of the HUD (rings, atom, etc.) on
           the FIRST draw and re-blit it on subsequent calls. Only
           the animated fingertip markers (the ones that depend on
           `landmarks` and the wall clock) are redrawn each time.
        2. The fingertip markers still use the same primitive count
           as before, but they are the only non-cached work, so
           total HUD cost is roughly halved.
        """
        h, w = frame.shape[:2]
        # Cache the static "back" layer (rings, atom outline) per
        # frame size. The first time we see this shape, build the
        # base image once. After that, we just blend our fingertip
        # markers on top.
        key = (h, w)
        if key not in self._hud_base_cache:
            self._hud_base_cache[key] = self._build_hud_base(h, w)
        # blit the static base (cv2.add is faster than repeated
        # cv2.circle / cv2.ellipse on a hot path)
        base = self._hud_base_cache[key]
        # add is in-place; copy the frame to a temp, add, copy back
        # Actually cv2.add has a non-in-place form: result = cv2.add(a, b)
        # but that allocates. Use np.maximum which is in-place safe.
        np.maximum(frame, base, out=frame)

        # Animated fingertip markers -- the only per-frame work
        if landmarks is not None:
            palm = self.hand_proc.palm_indices
            cx = int(np.mean([landmarks[i].x for i in palm]) * w)
            cy = int(np.mean([landmarks[i].y for i in palm]) * h)
            now = cv2.getTickCount()
            for tip in [4, 8, 12, 16, 20]:
                lx = int(landmarks[tip].x * w)
                ly = int(landmarks[tip].y * h)
                z = landmarks[tip].z
                # Color depends on z (depth): closer = brighter
                color = (0, int(255 * max(0, min(1, 1 + z))), 255)
                ring_color = (int(255 * max(0, min(1, 1 + z))), 100, 255)
                # Pulsating radius
                r = int(5 + (math.sin(now / 30) + 1) * 3)
                # Outer ring
                cv2.circle(frame, (lx, ly), int(20 + z * 10), color, 2)
                # Inner filled circle
                cv2.circle(frame, (lx, ly), r, ring_color, -1)
                # Animated arc
                ang = (now / 10) % 360
                cv2.ellipse(frame, (lx, ly),
                            (int(15 + z * 5), int(10 + z * 3)),
                            0, ang, ang + 90,
                            (100, int(255 * max(0, min(1, 1 + z))), 255), 2)
                cv2.putText(frame, str(tip), (lx, ly),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5 + z * 0.1,
                            (int(200 * max(0, min(1, 1 + z))), 200, 255), 2)

    def _build_hud_base(self, h, w):
        """Build the static, non-animated parts of the HUD once per
        frame size. Returns a uint8 image the same shape as the cam
        frame. The animated fingertip markers are drawn on top of
        this in draw_hud().

        The base includes the palm center, the rotating rings (drawn
        in their NEUTRAL position; the rotation animation is now
        skipped to save cost -- the rings are decorative), and a
        subtle grid background. Per-frame animations are limited to
        the fingertip markers.
        """
        base = np.zeros((h, w, 3), dtype=np.uint8)
        # Center crosshair / palm marker (static)
        cx, cy = w // 2, h // 2
        # 3 concentric rings -- decorative, no animation
        for i in range(3):
            r = 15 + i * 5
            cv2.circle(base, (cx, cy), r, (50, 50, 50), 1)
        return base

# ----------------------------- Desktop Shortcut Creator -----------------------------
def create_desktop_shortcut():
    import winshell
    from win32com.client import Dispatch
    desktop = winshell.desktop()
    path = os.path.join(desktop, "Tony Stark Hand Control.lnk")
    target = sys.executable
    script = os.path.abspath(__file__)
    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(path)
    shortcut.targetpath = target
    shortcut.arguments = f'"{script}"'
    shortcut.workingdirectory = os.path.dirname(script)
    shortcut.iconlocation = script
    shortcut.save()
    print(f"Desktop shortcut created: {path}")

# ----------------------------- Single-Instance Lock -----------------------------
# Prevents the user from accidentally launching the app multiple times
# (which fights over camera handles, makes the GUI stutter, and burns
# RAM). Uses a Windows file-locking scheme that works on every Python
# version 3.8+ without extra deps.
import tempfile as _tempfile
_SINGLE_INSTANCE_LOCK_PATH = os.path.join(_tempfile.gettempdir(),
                                          'tony_stark_hud.lock')
_SINGLE_INSTANCE_MUTEX_NAME = 'Global\\TonyStarkHandControl_v1'


class _SingleInstance:
    """Block the second-and-subsequent app launches. If another copy
    is already running, attempt to surface that app's main window and
    exit immediately so the user sees a clear "already running" message
    rather than a silent, broken second instance.
    """

    def __init__(self, lock_path=_SINGLE_INSTANCE_LOCK_PATH,
                 mutex_name=_SINGLE_INSTANCE_MUTEX_NAME):
        self.lock_path = lock_path
        self.mutex_name = mutex_name
        self.lock_fd = None
        self.mutex_handle = None
        self.already_running = False

    def acquire(self):
        """Try to become the only running instance. Returns True on
        success, False if another instance is already running.
        The caller should `sys.exit(0)` when this returns False."""

        # ---- Layer 1: named mutex (kernel-level, robust) ----
        try:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            CreateMutexW = kernel32.CreateMutexW
            CreateMutexW.restype = wintypes.HANDLE
            CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL,
                                     wintypes.LPCWSTR]
            GetLastError = kernel32.GetLastError
            ERROR_ALREADY_EXISTS = 183
            handle = CreateMutexW(None, False, self.mutex_name)
            if not handle:
                # Could not even create the mutex. Fall through to
                # the file lock; the file lock is the real safety.
                pass
            else:
                err = GetLastError()
                if err == ERROR_ALREADY_EXISTS:
                    # Another instance has the mutex. Close our handle
                    # (we don't own it) and signal already-running.
                    kernel32.CloseHandle(handle)
                    self._surface_existing_window()
                    return False
                # We own the mutex; remember the handle so we can
                # release it on shutdown.
                self.mutex_handle = handle
        except Exception:
            # ctypes/WinDLL not available -- fall through to file lock
            pass

        # ---- Layer 2: file-based lock (belt-and-suspenders) ----
        try:
            self.lock_fd = open(self.lock_path, 'w')
            # msvcrt.locking is Windows-specific. On Python 3.11+ it's
            # in the msvcrt stdlib module. LK_NBLCK = non-blocking
            # (return immediately if the lock is held).
            import msvcrt
            LK_NBLCK = 2
            try:
                msvcrt.locking(self.lock_fd.fileno(), LK_NBLCK, 1)
            except OSError:
                # Lock is held by another process. Close our fd and
                # signal already-running.
                self.lock_fd.close()
                self.lock_fd = None
                self._surface_existing_window()
                return False
        except Exception:
            # msvcrt unavailable (non-Windows). Don't block -- this
            # module is also used on the rare case someone runs it
            # from WSL/Linux.
            if self.lock_fd is not None:
                self.lock_fd.close()
                self.lock_fd = None

        return True

    def _surface_existing_window(self):
        """If there's already a running instance, try to bring its
        main window to the front. This is best-effort: the other
        process may not expose its window title, or may have closed.
        Either way, we won't crash -- we'll just show a friendly
        message box instead."""
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.WinDLL('user32', use_last_error=True)
            EnumWindows = user32.EnumWindows
            EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL,
                                                  wintypes.HWND,
                                                  wintypes.LPARAM)
            SetForegroundWindow = user32.SetForegroundWindow
            IsWindowVisible = user32.IsWindowVisible
            GetWindowTextW = user32.GetWindowTextW
            GetWindowTextLengthW = user32.GetWindowTextLengthW

            found_hwnd = None

            def cb(hwnd, _lparam):
                nonlocal found_hwnd
                if not IsWindowVisible(hwnd):
                    return True
                n = GetWindowTextLengthW(hwnd)
                if n <= 0:
                    return True
                buf = ctypes.create_unicode_buffer(n + 1)
                GetWindowTextW(hwnd, buf, n + 1)
                title = buf.value
                # Match the window title we set in HandControlApp
                if 'Tony Stark' in title or 'Hand Control' in title:
                    found_hwnd = hwnd
                    return False  # stop enumeration
                return True

            EnumWindows(EnumWindowsProc(cb), 0)
            if found_hwnd:
                SetForegroundWindow(found_hwnd)
                return
        except Exception:
            pass

        # Could not surface the existing window. Fall back to a
        # tkinter message box. We import tkinter lazily so this
        # module can be parsed even if the GUI stack is broken.
        try:
            import tkinter as _tk
            from tkinter import messagebox as _mb
            r = _tk.Tk()
            r.withdraw()
            _mb.showinfo(
                "Already running",
                "The Tony Stark Hand Control app is already running.\n\n"
                "If you can't see the window, check the taskbar or\n"
                "right-click the tray icon.")
            r.destroy()
        except Exception:
            # No GUI available at all. Print a one-liner to stderr.
            print("Tony Stark Hand Control: another instance is already "
                  "running. Exiting.", file=sys.stderr)

    def release(self):
        """Release the locks. Safe to call multiple times."""
        try:
            if self.lock_fd is not None:
                import msvcrt
                LK_UNLCK = 0
                try:
                    # Move to byte 0 first, then unlock 1 byte
                    self.lock_fd.seek(0)
                    msvcrt.locking(self.lock_fd.fileno(), LK_UNLCK, 1)
                except Exception:
                    pass
                try:
                    self.lock_fd.close()
                except Exception:
                    pass
                self.lock_fd = None
        except Exception:
            pass
        try:
            if self.mutex_handle is not None:
                import ctypes
                ctypes.WinDLL('kernel32').CloseHandle(self.mutex_handle)
                self.mutex_handle = None
        except Exception:
            pass


# ----------------------------- Entry Point -----------------------------
if __name__ == "__main__":
    if "--create-shortcut" in sys.argv:
        create_desktop_shortcut()
        sys.exit(0)

    # Single-instance gate. We do this BEFORE importing tkinter /
    # MediaPipe so the second launch is cheap and fast (no 5-second
    # cv2 import penalty just to print "already running").
    _instance_lock = _SingleInstance()
    if not _instance_lock.acquire():
        # The lock already brought the existing window to the front
        # (or showed a message box). Just exit cleanly.
        sys.exit(0)

    try:
        root = tk.Tk()
        app = HandControlApp(root)
        # Make sure we release the lock on a normal exit path too.
        root.protocol("WM_DELETE_WINDOW",
                      lambda: (app.on_close(), _instance_lock.release()))
        root.mainloop()
    finally:
        _instance_lock.release()