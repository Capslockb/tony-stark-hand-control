# Installation

Detailed setup instructions for Tony Stark Hand Control.

## Requirements

### Hardware

- **CPU**: any modern x86-64 (Intel or AMD)
- **RAM**: 4 GB minimum, 8 GB recommended (the app itself uses ~200 MB; the rest is for OS + browser)
- **GPU**: optional. The app runs on CPU. A CUDA-capable GPU helps only with the *optional* Ollama/LLM gesture recognition.
- **Camera**: any USB webcam or built-in laptop camera. Multiple cameras recommended for 3D reconstruction.
- **Disk**: 500 MB (Python + dependencies + the MediaPipe model)

### Software and platform status

- **Python** ≥ 3.10 (3.11+ recommended)
- **Windows 10 / 11** is the primary tested and documented path.
- **Linux and macOS** have source-install guidance below, but they are not yet first-class parity targets. Focus discovery and the persistent selection overlay still require platform-specific work tracked in [ROADMAP.md](../ROADMAP.md#v110--ux-polish--platform-parity).
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
4. Download `hand_landmarker.task` (~7 MB) from the MediaPipe model registry
5. Create a desktop shortcut on Windows, or skip that step on other platforms

The wizard stops at the first failing step. After all five steps succeed, it prints the appropriate launch command; it does not start the app automatically.

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

After install, run repository-wide test discovery:

```bash
python -m unittest discover tests -v
```

The original core audit in `tests/test_app.py` contains 77 assertions covering RoomMap, HandProcessor, CameraManager, StereoCalibrator, `triangulate_point_rays`, Ollama gesture recognition, and application construction. Repository-wide discovery includes additional regression and benchmark modules, so its total is not fixed.

Treat the command's final summary and the GitHub Actions run for the exact commit as the source of truth. The CI matrix is currently failing and is tracked in [Issue #3](https://github.com/Capslockb/tony-stark-hand-control/issues/3); do not infer a passing installation from an old fixed test count.

## Next steps

- **[Calibration](calibration.md)** — print the checkerboard and run calibration for 3D room mapping
- **[Gestures](gestures.md)** — what each gesture does
- **[Performance tuning](performance.md)** — what each slider in the GUI controls

## Troubleshooting

See [troubleshooting.md](troubleshooting.md) for common issues:
- `import cv2` fails with WinError 1455
- Cameras show as black
- MediaPipe GPU delegate unavailable
- Single-instance lock not releasing
- Ollama cloud endpoint timing out