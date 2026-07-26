# Troubleshooting

Common issues and how to fix them. If your issue isn't here, open a GitHub issue with:
- Your OS and Python version (`python --version`)
- The full output of `python install_wizard.py`
- The relevant log snippet from the app's `Main` tab
- If it's a camera issue: how many cameras you have, what brand/model, and what OS

## Installation issues

### `import cv2` fails with `WinError 1455` (pagefile too small)

This is a **pagefile exhaustion** problem, not a RAM problem. Something is using your swap file. Common culprits:

1. **Orphan `llama-server.exe` processes** — check with `tasklist | findstr llama`. Each one uses 1-2 GB of swap. Kill them with `taskkill /F /IM llama-server.exe`.
2. **Orphan `ollama` processes** — same idea. `taskkill /F /IM ollama.exe`.
3. **A hung Python process** — `Get-Process python | Format-Table Id, CPU, WS`. If `CPU` is in the thousands and `WS` (working set) is small but the process has been running for hours, it's stuck. Kill it.

Free up the swap and re-run the app.

### `pip install mediapipe` fails on Python 3.13

MediaPipe 0.10.14+ supports Python 3.13. If you have an older version:

```bash
pip install --upgrade mediapipe
```

If that doesn't work, use Python 3.12 (the most-tested version).

### `tkinter` not found (Linux)

```bash
sudo apt install python3-tk
# or on RHEL/Fedora
sudo dnf install python3-tkinter
```

## Camera issues

### All cameras show as black

1. Check that the cameras are not in use by another application (Zoom, Skype, browser).
2. Run `python -c "import cv2; print(cv2.getBuildInformation())"` and confirm DSHOW is listed.
3. In the **Cameras** tab, click **Test** next to each camera. If a camera shows up as "dead" but works in another app, the index might be different. The app auto-detects indices 0-3.
4. On Windows 10, check Settings → Privacy → Camera and confirm "Let desktop apps access your camera" is ON.

### "Auto-detected camera 0 (backend=700) @ 480x360 30fps" but feed is still black

The DSHOW backend (700 = CAP_DSHOW) successfully opened the camera, but the feed is black. This usually means:

1. **Camera is in use by another app** — close other apps and retry.
2. **Camera lens is covered** — physical check.
3. **Camera needs a USB reset** — unplug and re-plug.
4. **Camera resolution mismatch** — try a different resolution in the Cameras tab.

### Only some cameras detected

The app probes indices 0-3 with three backends. If you have 4 cameras and only 2 are detected:

1. Check Windows Device Manager to see if all 4 are listed.
2. Some USB cameras share an index (two cams on one USB hub may both show as index 2). Try a different USB port.
3. Some webcams only work with MSMF (not DSHOW). The app tries both, but check the console output to see which backend succeeded for each index.

### Camera detection takes 30+ seconds

The app has a 1.5-second timeout per `cap.open()` and a 0.8-second timeout per `cap.read()`. With 4 indices × 3 backends, the worst case is ~30 seconds. This is normal on slow webcam drivers.

If it's worse, the issue is probably **another app holding the camera**. Close other apps and retry.

## MediaPipe issues

### `GPU processing is disabled in build flags`

This is **expected** on this build of MediaPipe for Windows. The GPU delegate doesn't work with the official MediaPipe pip wheel on Windows. The app falls back to CPU automatically — you'll see a log line `HandProcessor: GPU delegate unavailable -> CPU`.

CPU inference measured roughly 30 ms per submitted frame on the recorded development machine. The current app uses one shared asynchronous MediaPipe worker; it does **not** run an independent 30 fps inference stream for every enabled camera. Cameras contend for that shared submission/result path, and completed results are not yet owned per camera. Treat throughput as aggregate and host-dependent; see [Issue #7](https://github.com/Capslockb/tony-stark-hand-control/issues/7).

### Hand detection is jittery

1. Check the **One-Euro filter** parameters in the Tracking tab. Default `min_cutoff=2.5, beta=0.05` is good for most users. Lower `min_cutoff` to 1.0 for more smoothing.
2. Improve lighting. MediaPipe's accuracy degrades in low light.
3. Make sure the background is uniform. A cluttered background (bookshelf, plants) can confuse the model.

### Hand is detected but only sometimes

1. MediaPipe needs to see the **whole hand** — wrist to fingertips. If your hand is cut off at the bottom of the frame, it'll be missed.
2. Hands at extreme angles (fingers pointing straight at the camera) are hard to detect. Try rotating your hand 30-45 degrees.
3. Gloves are not supported. Use bare hands.

## Performance issues

### App uses 100% CPU

1. Check the **Performance** readout in the Main tab. A `loop` value consistently above 50 ms means the measured work exceeds a 20 fps budget, but it does not identify MediaPipe as the sole cause. Profile camera capture, vision work, rendering, and optional integrations before attributing the load.
2. Enable **Fast Mode** in the Tracking tab. The 240p pre-downscale may reduce MediaPipe work; the approximately 30% improvement cited in source comments is specific to the development setup, not a guarantee.
3. Disable unused cameras in the Main tab to reduce capture, rendering, and shared-worker contention.
4. `mediapipe_skip` is an internal value and has no Tracking-tab control. Changing it requires a reviewed code change and does not correct the per-camera result-ownership problem tracked in [Issue #7](https://github.com/Capslockb/tony-stark-hand-control/issues/7).
5. The **Responsiveness** preset tunes smoothing and prediction behavior; it is not a supported CPU-limit control and does not create independent per-camera inference workers.

### Cursor lags behind hand by 100+ ms

1. Increase the **Responsiveness** preset to 4 or 5 in the Tracking tab.
2. If the loop is slow, see "App uses 100% CPU" above.
3. The predictor horizon has no independent Tracking-tab control. It is managed by the responsiveness preset; preset 5 selects the longest current horizon (0.25 s).

### Selection border doesn't appear

1. Check the **Accessibility** tab — "Show persistent selection border" must be checked.
2. The border is shown via a `tk.Toplevel` window with `WS_EX_TRANSPARENT | WS_EX_LAYERED`. On some Windows versions with certain themes, the border may be invisible. Try changing your Windows theme to a light theme to see if the border is being drawn in the wrong color.
3. If you're running the app as a different user than your desktop user, the overlay may not be visible to the desktop session.

## Ollama / cloud issues

### Ollama cloud endpoint times out

The current source default is the complete generation endpoint `https://ollama.com/api/generate`. Cloud latency varies; the recorded test environment took roughly 5-8 seconds per inference. The Ollama worker is asynchronous and keeps only one queued frame, so slow requests delay optional model-recognized gestures and drop stale submissions rather than changing the local MediaPipe gesture path.

1. Confirm the endpoint includes `/api/generate`, the selected model is available, and you are using your own API key. Do not reuse the exposed credential-like default tracked in [Issue #5](https://github.com/Capslockb/tony-stark-hand-control/issues/5), and do not paste credentials into issue reports or logs.
2. Increase **Query cooldown** if you want fewer remote submission attempts. The current control defaults to 0.5 seconds and supports 0.1-3.0 seconds; this setting does not make a multi-second provider response real-time.
3. If remote inference is unnecessary, uncheck **Enable Ollama**, click **Save (rebuild Ollama worker)**, and continue with the local MediaPipe detector. All built-in engage, click, and swipe gestures remain available without Ollama.

### Ollama circuit breaker keeps tripping

The circuit breaker trips after 3 consecutive failures and stays tripped for 30 seconds. Repeated trips usually indicate an invalid endpoint, unavailable model, rejected credential, network failure, or provider outage.

**Fix**: verify the complete endpoint and model, use your own valid credential when the endpoint requires one, or disable Ollama and rebuild the worker. The circuit breaker recovering does not prove that the next request will be accepted.

## Single-instance lock issues

### "Another instance is already running" but the app isn't running

The lock file is stale. The app uses two locks for safety:
1. `%TEMP%\tony_stark_hud.lock` (msvcrt file lock)
2. `Global\TonyStarkHandControl_v1` (Windows named mutex)

If the app crashed without releasing either, the locks persist. To clear:

```cmd
del "%TEMP%\tony_stark_hud.lock"
```

The named mutex is released automatically when the process exits, even on crash. So if the file lock is cleared, the next launch should work.

If it still says "already running" after deleting the file, restart the computer (releases the named mutex).

## GitHub / build issues

### `gh auth status` shows not authenticated

Run `gh auth login` and follow the prompts. Or use a personal access token:
```cmd
set GITHUB_TOKEN=ghp_xxxxx
gh auth login --with-token < token.txt
```

### Release workflow fails with "no PyInstaller spec"

The workflow uses a single-file build with `--onefile --windowed`. If you have a custom spec file, you can replace the `pyinstaller` line with `pyinstaller tony_stark_hud_control.spec`.