# Installation

Detailed setup instructions for Tony Stark Hand Control.

> **Current `main` runtime status:** installation can complete even though live processing is presently blocked by the loop-rescheduling regression tracked in [Issue #16](https://github.com/Capslockb/tony-stark-hand-control/issues/16). A source checkout may show the first processed frame and then stop updating after **Start**. Successful installation or import smoke testing does not validate the camera and gesture runtime until a reviewed fix lands.

## Requirements

### Hardware

- **CPU / architecture**: prebuilt releases target 64-bit Windows (`x64`) and Linux (`x86_64`). Source installs on other architectures, including Apple Silicon, are not currently validated.
- **Memory**: no repository-wide minimum has been validated. Runtime use varies with camera count and resolution, display tabs, backend buffering, and optional local model services. Leave enough headroom for the operating system and other applications, and monitor the app's live RAM readout on the Windows path.
- **GPU**: optional. At startup, the application first attempts MediaPipe's GPU delegate when it is supported by the installed MediaPipe build and platform, and falls back to CPU if delegate initialization fails. A separately configured local Ollama-compatible model server may also use its own GPU; a remote endpoint uses the remote server's hardware, not your local GPU.
- **Camera**: a USB webcam or built-in laptop camera supported by the operating system and OpenCV. At least two overlapping camera views are required for the experimental stereo path, whose live coordinates remain unvalidated while [Issue #6](https://github.com/Capslockb/tony-stark-hand-control/issues/6) is open.
- **Disk**: allow space for the Python environment, platform-specific wheels, the MediaPipe model, and pip's download cache. The total varies by platform and dependency versions. The wizard downloads MediaPipe's current `latest` float16 model, so its exact size is not a stable repository requirement.

### Software and platform status

- **Python** ≥ 3.10 (3.11+ recommended)
- **Windows 10 / 11** is the primary tested and documented path.
- **Linux and macOS** have source-install guidance below, but they are not yet first-class parity targets. Focus discovery and the persistent selection overlay still require platform-specific work tracked in [ROADMAP.md](https://github.com/Capslockb/tony-stark-hand-control/blob/main/ROADMAP.md#v110--ux-polish--platform-parity).
- **WSL** is not equivalent to a native Linux desktop for this camera-and-GUI application. Use the native Windows path unless you have deliberately configured GUI and webcam forwarding.
- **Webcam drivers**: whatever your OS provides (UVC on Linux, MSMF/DSHOW on Windows, AVFoundation on macOS).

## Quick install (Windows)

```cmd
git clone https://github.com/Capslockb/tony-stark-hand-control.git
cd tony-stark-hand-control
python install_wizard.py
start_windows.bat
```

The install wizard will:
1. Verify Python ≥ 3.10
2. Run `python -m pip install -r requirements.txt --upgrade`
3. Smoke-test required imports
4. Download `hand_landmarker.task` from MediaPipe's current float16 model URL
5. Attempt to create a desktop shortcut on Windows, or skip that step on other platforms

The wizard stops at the first failing required step: Python validation, dependency installation, import smoke testing, or model download. A Windows shortcut-creation failure is warning-only; the wizard still reports installation complete and prints the appropriate launch commands. It does not start the app automatically.

## Experimental source install (Linux)

```bash
git clone https://github.com/Capslockb/tony-stark-hand-control.git
cd tony-stark-hand-control
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python install_wizard.py
python3 tony_stark_hud_control.py
```

This is a source-install path, not a claim of feature parity with Windows. In particular, focus discovery and the persistent selection overlay may be incomplete depending on the desktop session and display server.

## Experimental source install (macOS)

```bash
git clone https://github.com/Capslockb/tony-stark-hand-control.git
cd tony-stark-hand-control
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python install_wizard.py
python3 tony_stark_hud_control.py
```

The `pywin32` and `winshell` packages are Windows-only and are skipped through `sys_platform` markers in `requirements.txt`. That prevents those packages from being installed on macOS; it does not establish feature parity. Focus tracking still needs the planned macOS accessibility bridge described in the roadmap.

## Manual install

If the wizard doesn't work for you:

```bash
# 1. Create a venv (recommended)
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS

# 2. Install
pip install -r requirements.txt

# 3. Download the model (one of these)
# Method A: via the wizard
python install_wizard.py
# Method B: manually
curl -L -o hand_landmarker.task https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task
# Method C: let the app do it on first launch
python tony_stark_hud_control.py
# The app will download it if missing.

# 4. (Windows only) Desktop shortcut
python tony_stark_hud_control.py --create-shortcut

# 5. Run
python tony_stark_hud_control.py
```

## Verifying the install

The files under `tests/` mix pytest-style functions, executable assertion and benchmark scripts, and a manual camera/Tk integration audit. Run the deterministic checks explicitly from the repository root as documented in [`tests/README.md`](https://github.com/Capslockb/tony-stark-hand-control/blob/main/tests/README.md).

Examples:

```bash
python -m pytest -q tests/test_v100_hotfix.py
python tests/test_predict_smoke.py
python tests/test_palm.py
python tests/test_single_instance.py
```

Run the live integration audit separately only on a machine with a graphical display and suitable camera access:

```bash
python tests/test_app.py
```

Do not use `python -m unittest discover tests -v` or an unfiltered `pytest` command as a general hosted or headless verification step. Collection can import modules that perform work immediately, including the live camera/Tk audit. Treat the explicit commands in `tests/README.md` and the GitHub Actions run for the exact commit as the validation sources of truth. Current `main` CI remains tracked in [Issue #3](https://github.com/Capslockb/tony-stark-hand-control/issues/3).

## Next steps

- **[Calibration](calibration.md)** — print the checkerboard and run calibration for 3D room mapping
- **[Gestures](gestures.md)** — what each gesture does
- **[Performance tuning](performance.md)** — user-facing controls, internal pacing values, and performance trade-offs

## Troubleshooting

See [troubleshooting.md](troubleshooting.md) for common issues:
- `import cv2` fails with WinError 1455
- Cameras show as black
- MediaPipe GPU delegate unavailable
- Single-instance lock not releasing
- Ollama cloud endpoint timing out
