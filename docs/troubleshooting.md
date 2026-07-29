# Troubleshooting

Common issues and how to fix them. If your issue isn't here, open a GitHub issue with:
- Your OS and Python version (`python --version`)
- The full output of `python install_wizard.py`
- The relevant log snippet from the app's `Main` tab
- If it's a camera issue: how many cameras you have, what brand/model, and what OS

## Installation issues

### `import cv2` fails with `WinError 1455` (paging file too small)

This error means Windows could not reserve more committed memory. The system commit limit is backed by physical RAM and page files, so the cause can be a nearly exhausted commit limit, a paging file that is too small or slow to grow, insufficient free disk space for paging-file growth, or a process reserving unusually large amounts of memory. It is not proof that the physical RAM is defective, and a process's CPU time or working-set size alone does not prove that it is hung.

1. Open Task Manager → **Performance** → **Memory** and check **Committed**. If the first value is close to the limit, close applications you recognize and retry.
2. Check likely background servers with `tasklist | findstr /I "llama ollama python"`. Confirm the PID and owner before terminating an abandoned process; use `taskkill /PID <PID> /F` rather than killing every process with that executable name.
3. Ensure the Windows paging file is enabled—preferably **System managed**—and that its drive has enough free space. If Windows cannot grow it quickly enough, set a larger initial size, restart, and retry. See [Microsoft's page-file guidance](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/how-to-determine-the-appropriate-page-file-size-for-64-bit-versions-of-windows).
4. If the error persists, include the Task Manager **Committed** values, paging-file setting, free disk space, and exact error in the issue report. Never post API keys or other credentials.

### `pip install mediapipe` fails

MediaPipe wheel availability varies by MediaPipe release, Python version, operating system, and CPU architecture. The repository allows `mediapipe>=0.10.14,<0.11`, but that range does not mean every release in it provides a compatible wheel for every interpreter and platform.

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If pip reports that no matching distribution is available, include the exact Python version, OS, architecture, and complete pip error in the issue report. Python 3.12 on Windows x64 is the primary fallback path. The configured CI matrix covers Python 3.11–3.13, but it is currently red—including Windows dependency installation—under [Issue #3](https://github.com/Capslockb/tony-stark-hand-control/issues/3), so it is not a green compatibility guarantee.

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

The app requests a 1.5-second open timeout and a 0.8-second read timeout from OpenCV, but the current probe constructs `cv2.VideoCapture(idx, backend)` before setting those properties. A backend or driver can therefore block during the constructor, and some backends may ignore the timeout properties entirely. There is no reliable end-to-end 30-second cap in the current implementation.

Close applications that may hold a camera, disconnect unused capture devices, and retry. If one index or backend consistently stalls, include the console output, OpenCV version, camera model, and operating system in the issue report. Correcting the probe order or moving camera discovery off the GUI thread requires a separately reviewed camera-runtime PR.

### Camera preview updates once and then freezes

The current source line has a known main-loop scheduling regression tracked in [Issue #16](https://github.com/Capslockb/tony-stark-hand-control/issues/16). After **Start**, camera capture and gesture processing can complete one loop iteration and then stop while the last rendered frame remains visible.

This is not fixed by changing camera backends, frame-rate settings, responsiveness presets, or restarting calibration. There is no supported configuration workaround. Treat recurring live camera and gesture processing as unavailable until a reviewed runtime fix lands; use Issue #16 for the exact implementation and validation status.

## MediaPipe issues

### `GPU processing is disabled in build flags`

This message means the installed MediaPipe build and current environment could not initialize the GPU delegate for Hand Landmarker. The application attempts the GPU delegate at startup and falls back to CPU when delegate creation fails. Do not infer from this log that every official Windows wheel is universally CPU-only; delegate availability depends on the installed build, platform, runtime, driver, and model compatibility.

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

The app uses two process-owned locks: a Windows named mutex (`Global\TonyStarkHandControl_v1`) and an advisory lock on `%TEMP%\tony_stark_hud.lock`. The operating system releases both locks when the owning process exits, including after a crash. The zero-byte lock file may remain in `%TEMP%`, but its presence alone does not mean another instance is running, and deleting it does not release a lock held by a live process.

1. Check Task Manager for the packaged app, `python.exe`, or `pythonw.exe`. Confirm the process owner and command line before closing anything; another Python application may be unrelated.
2. Because the mutex uses the Windows `Global\` namespace, check other signed-in desktop sessions for a running copy of the app.
3. Close a verified existing instance normally. Use **End task** only for a verified unresponsive copy.
4. If no instance exists in any session but the warning persists, restart Windows and report the exact launch method, app version or commit, process list, and message. Do not include credentials or unrelated environment data.

A leftover `%TEMP%\tony_stark_hud.lock` file can be ignored. Do not treat deleting the file as the primary fix, and do not delete it while a verified instance is running.

## GitHub / build issues

### `gh auth status` shows not authenticated

Run [`gh auth login --web`](https://cli.github.com/manual/gh_auth_login) and complete the browser flow. GitHub CLI normally stores the resulting token in the system credential store when one is available. Do not use `--insecure-storage`, paste tokens into shell history, include them in logs or issue reports, or commit token files.

For non-interactive automation, inject a narrowly scoped `GH_TOKEN` through the runner or host secret store rather than a command-line argument, committed `.env` file, script, or persistent plaintext token file. See the [GitHub CLI environment-variable reference](https://cli.github.com/manual/gh_help_environment), then verify the active account with `gh auth status` while keeping token values redacted.

### Release workflow fails with "no PyInstaller spec"

The workflow uses a single-file build with `--onefile --windowed`. If you have a custom spec file, you can replace the `pyinstaller` line with `pyinstaller tony_stark_hud_control.spec`.
