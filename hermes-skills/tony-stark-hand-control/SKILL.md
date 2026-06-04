---
name: tony-stark-hand-control
description: Tony Stark hand-control PC system with 5-tab Tkinter GUI, multi-camera fusion, intent detection, accessibility focus nav (DEFAULT not mouse) with **persistent selection overlay** (Win32 GetGUIThreadInfo, 10 Hz) tracking the focused UI element, swipes (up/down/left/right) with predicted-position velocity, motion prediction (dead reckoning + quadratic decay) for 1:1 feel, **async MediaPipe worker thread** (detect() returns <1ms), Fast Mode 240p pre-downscale, **live loop-time readout**, **in-app win32 CPU/RAM/threads readout**, throttled per-frame probes, Responsiveness preset 1-5, 3D triangulation, **single-instance lock** (Win32 named mutex + msvcrt file lock + SetForegroundWindow on duplicate), **MSMF warm-up fix** (read 5 frames not 1), **GUI-startup worker thread + cv2 OPEN/READ timeouts** (avoids Start-button freeze), interactive matplotlib 3D room-mapping tab. Local llama.cpp BROKEN on RTX 5060 Blackwell. See references for pitfalls.
category: creative
version: 4.5.0
author: Hermes Agent
---

# Tony Stark Hand Control Skill

## Reference map

- `references/audit_2026_06_04_pass2.md` -- second audit pass: predictor velocity from `prev_filtered` (not `predicted`); `predict()` returns `None` for unseen; wrist-relative `is_palm_open` (Y-flip broken on selfie cams); normalized click distance; camera handle leak on calibration; Ollama circuit breaker; persistent selection overlay via `GetGUIThreadInfo` (cbSize MUST be set first); async MediaPipe worker thread; throttled per-frame probes; Fast Mode 240p; velocity clamp 10000 px/s; loop-time readout; matplotlib 3D room-tab patterns; live-feed check thresholds.
- `references/audit_2026_06_04_pass3.md` -- third audit pass + **headless GUI self-test recipe**: dead-code duplicate `release()` methods (Python keeps last def, older is dead); `save()` must compute derived keys if missing (P from K[R|t]); 3D room tab feature list; live runtime test of the actual app via `hermes process log`.
- `references/audit_2026_06_04_pass4.md` -- fourth audit pass: **single-instance lock recipe** (Win32 named mutex + msvcrt file lock, acquire BEFORE tkinter/cv2 imports, SetForegroundWindow on duplicate, release on WM_DELETE_WINDOW + `finally:`); **MSMF camera warm-up fix** (`_find_cameras` reads 5 frames and uses `is_feed_live` on the last, not the first); **pagefile exhaustion failure mode** (orphan llama-server processes silently eating swap -- check `PagedMemorySize` not just `WorkingSet`); web research backend down (SearXNG 404) -- pivot to internal audit when search fails.
- `references/audit_2026_06_04_pass5.md` -- fifth audit pass: **HUD static-base cache + np.maximum blit** (5-10ms/call -> 0.2ms/call, 25-50x speedup on the multi-cam hot path); per-cam enable state cached as a Python list (skips 120 Tcl bridge calls/sec at 4 cams x 30 fps); off-by-one bug in the FPS cache (wrong cam could get wrong FPS when cams 0..N aren't all live); end-to-end single-instance lock test recipe; **cv2 micro-benchmark gotcha** (don't put `np.random.rand(...).astype(uint8)` inside the timed loop -- it's 5ms and drowns the signal); `random.randint` is not free on the hot path; "second app won't start" diagnostic sequence (kill, not relaunch).
- `references/audit_2026_06_04_pass6.md` -- sixth audit pass: **GUI-startup worker thread pattern** (move slow `start()` work to a daemon thread, hand the result back via `root.after(0, ...)`); schedule the FIRST loop with `root.after(50, ...)` instead of synchronously; **OpenCV videoio timeouts** (`CAP_PROP_OPEN_TIMEOUT_MSEC=1500`, `CAP_PROP_READ_TIMEOUT_MSEC=800`) bound the worst-case `cap.read()` block time when probing phantom device indices; class-level lesson extracted to `gui-app-startup` umbrella skill.
- `references/audit_2026_06_04_pass7.md` -- seventh audit pass: **in-app win32 CPU/RAM/threads readout** via ctypes (`GetProcessTimes` + `psapi.GetProcessMemoryInfo`) -- lets the user see the *app's own* load separate from the system total, resolving the "X% load" ambiguity permanently; **orphan-process diagnostic recipe** when "app is at Y% load" but the app is idle; **GitHub upload pre-flight gate** -- when asked to "create a private repo," never push without 4-of-7 confirmations (username, repo name, license, auth, identity, scope, visibility).
- `references/audit_2026_06.md` -- first audit pass: predictor architecture, app-default conventions, docstring table.
- `references/stream_cut_fallback.md` -- Hermes parent-streaming gotcha on this host: single-shot `write_file` and full-file subagent rewrites both fail on >600-line files; use chunked `patch` calls (<80 lines of diff each) with `python -c "import ast; ast.parse(...)\"` between batches.
- `references/camera_troubleshooting.md` -- black-feed check, is_feed_live, per-cam enable, multi-cam directshow pitfalls, MSMF warm-up frame bug, CameraManager handle leak on calibration→Start sequence.
- `scripts/audit_app.py` -- comprehensive runtime test harness (77 assertions across RoomMap, HandProcessor, CameraManager, StereoCalibrator, triangulate_point_rays, OllamaGestureRecognizer circuit breaker, full HandControlApp construction). Run with `python scripts/audit_app.py` (or pass the path to `tony_stark_hud_control.py` as argv[1]). Pattern: synthetic inputs for deterministic subsystems, real cameras only for CameraManager auto-detect, Tk root + .withdraw() to construct the App without mainloop.
- `scripts/multistream_bench.py` -- micro-benchmark for the multi-cam hot path. Pre-generates frames OUTSIDE the timed loop (per pass5 §27 -- including `np.random.rand(...).astype(uint8)` in the loop adds 5ms and drowns the signal), reports per-call `draw_hud` cost AND projected CPU% at the target frame rate. Use this to verify any HUD optimization is real before shipping.
- `references/dual_class_default_state.md` -- pattern: any field used by the *constructor* of another class at app init must be set on the App **before** widget creation (Tracking-tab widgets reading `self.fast_mode`, etc.).
- `references/adaptive_pacing_and_gpu.md` -- loop pacing to fastest live cam, mediapipe_skip, Fast Mode.
- `references/3d_reconstruction.md` -- Phase A intrinsics + Phase B `stereoCalibrate` shared-frame; undistort + K^-1 + R^T ray transform; calibration.npz persistence.
- `references/accessibility_overlay.md` -- Toplevel + WS_EX_TRANSPARENT/LAYERED/TOOLWINDOW; GetGUIThreadInfo layout.
- `references/gui_and_intent.md` -- 5-tab Notebook, engage-hold heuristic, intent_history ring buffer.
- `references/multicamera_fusion.md` -- CameraManager, per-cam processing, autoblacklist.
- `references/ollama_integration.md` -- Circuit breaker pattern, ollama.com vs local.
- `references/smoothing_and_aspect.md` -- One-Euro filter, EMA, letterbox/pillarbox, buffer sizing.

## Pitfalls (the things that bit us in audits 2-7)

- **Single-instance lock MUST run before `import tkinter` or `import cv2`.** Acquiring the lock is the common case (user double-clicks the desktop shortcut). A 5-second cv2 import just to print "already running" is awful UX. See `references/audit_2026_06_04_pass4.md` §18 for the Win32 named mutex + msvcrt file lock recipe.

- **`CameraManager._find_cameras` MUST read 5 frames, not 1.** MSMF warm-up / auto-exposure returns black for the first few reads. Accepting on the first read means cams get added then immediately blacklisted by `is_feed_live`. See pass4 §19.

- **If `import cv2` fails with WinError 1455, the pagefile is the problem, not RAM.** Check `PagedMemorySize` on every process. Orphan `llama-server` / `ollama` / model servers can each page 1-2 GB out to swap while only using 600 MB of physical RAM, and the next `import` of any large C-extension module will fail. See pass4 §20.

- **`save()` is sacred.** It must be idempotent, lossless, and tolerant of old/corrupt/missing keys. See pass3 §17.

- **The HUD is the dominant per-frame cost in multi-cam, not MediaPipe.** The detector is on a worker thread and costs nothing on the GUI side. `draw_hud` runs once per cam per frame and can hit 70% of one core if you don't cache the static base. Cache the static base, use `np.maximum` to blit, only redraw the animated parts. See pass5 §22.

- **Tk `BooleanVar.get()` is a Tcl bridge call, not a Python attr read.** With 4 cams x 30 fps that's 120 Tcl round-trips per second on the hot path. Cache as a plain Python list once per loop. See pass5 §23.

- **The FPS cache index must walk both lists in lockstep.** `zip(range(len(live_fps)), live_fps)` assigns by `live_fps` index, not by camera index — silently wrong when cams 0..N aren't all live. See pass5 §25.

- **Don't put `np.random.rand(...).astype(uint8)` inside a cv2 micro-benchmark loop.** It's ~5ms and drowns the cv2 work you're measuring. Pre-generate frames outside the timed loop, and report both per-call cost AND projected CPU% at the target frame rate. See pass5 §27.

- **`random.randint` is not free on the hot path.** Audit your draw functions for it. Decorative particles (sparks, fire) are usually removable with no visual loss. See pass5 §28.

- **The Start button is a "do X" handler. X must not block.** See pass6 §29 and the `gui-app-startup` umbrella skill. If X involves cv2 device init, GPU work, file/network load, or pip install, move it to a daemon thread and post GUI updates back via `root.after(0, ...)`. Also schedule the first `loop()` / `tick()` call with `root.after(N, ...)` instead of synchronously — that lets the GUI paint the new state before the first iteration blocks.

- **`cap.isOpened()` is a lie on Windows for phantom indices.** Set `CAP_PROP_OPEN_TIMEOUT_MSEC` and `CAP_PROP_READ_TIMEOUT_MSEC` on every `VideoCapture` to bound the worst case. See pass6 §30.

- **"X% load" is ambiguous between system total and the app itself.** Add an in-app CPU/RAM/threads readout (win32 via ctypes, no deps) to the Main tab so the user can disambiguate. See pass7 §31 for the `GetProcessTimes` + `psapi.GetProcessMemoryInfo` recipe. The label updates ~2 Hz from the main loop, throttled to every 15th frame so it doesn't flicker.

- **High system CPU with the app idle is almost always a different stuck process, not the app.** Diagnostic: `Get-Process | Sort CPU -Descending | Select -First 10` — look for high-CPU processes with no `MainWindowTitle`. Check `PagedMemorySize` not just `WorkingSet` (pagefile residency is silent). If `taskkill /F` returns "Access is denied," the process is from another session/elevation context — you need to either escalate, kill the parent first, or wait for reboot. Don't try to record "X process can't be killed" as a durable rule — it's environment-dependent. See pass7 §32.

- **GitHub upload: never push without explicit user confirmation of the auth-bearing fields.** When the user says "upload to a new private github repo," ask for (1) username/org, (2) repo name, (3) license, (4) auth method (token vs `gh` install vs SSH), (5) git identity, (6) scope, (7) visibility. Refuse to start until at least 4 of 7 are confirmed. If the user says "use your best judgment for everything else," you can fill in the rest but **you must never pick a token for them**. See pass7 §33 and the `github-repo-management` umbrella skill.
