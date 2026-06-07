# Installation

Detailed setup instructions for Tony Stark Hand Control.

## Requirements

### Hardware

- **CPU**: any modern x86-64 (Intel or AMD)
- **RAM**: 4 GB minimum, 8 GB recommended (the app itself uses ~200 MB; the rest is for OS + browser)
- **GPU**: optional. The app runs on CPU. A CUDA-capable GPU helps only with the *optional* Ollama/LLM gesture recognition.
- **Camera**: any USB webcam or built-in laptop camera. Multiple cameras recommended for 3D reconstruction.
- **Disk**: 500 MB (Python + dependencies + the MediaPipe model)

### Software

- **Python** ≥ 3.10 (3.11+ recommended)
- **Operating systems supported**:
  - Windows 10 / 11 (tested)
  - macOS 12+ (should work; not heavily tested)
  - Linux with Tkinter (usually preinstalled; `sudo apt install python3-tk` on Debian/Ubuntu)
- **Webcam drivers**: whatever your OS provides (UVC on Linux, MSMF/DSHOW on Windows, AVFoundation on macOS)

## Quick install (Windows)

```cmd
git clone https://github.com/Capslockb/tony-stark-hand-control.git
cd tony-stark-hand-control
python install_wizard.py
start_windows.bat
```

The install wizard will:
1. Verify Python ≥ 3.10
2. `pip install -r requirements.txt` (opencv-python, mediapipe, matplotlib, pyautogui, pywin32, winshell, Pillow)
3. Download `hand_landmarker.task` (~7 MB) from the MediaPipe model registry
4. Create a desktop shortcut
5. Verify all imports work

If the install wizard fails at any step, fix the issue and re-run. Each step is independent.

## Quick install (Linux / WSL)

```bash
git clone https://github.com/Capslockb/tony-stark-hand-control.git
cd tony-stark-hand-control
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python install_wizard.py
python3 tony_stark_hud_control.py
```

## Quick install (macOS)

```bash
git clone https://github.com/Capslockb/tony-stark-hand-control.git
cd tony-stark-hand-control
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python install_wizard.py
python3 tony_stark_hud_control.py
```

> **Note on macOS**: the `pywin32` and `winshell` packages are Windows-only and skipped via the `sys_platform` marker in `requirements.txt`. Everything else should work.

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

After install, run the test suite:

```bash
python -m unittest discover tests -v
```

You should see **77 tests pass** across:
- `RoomMap` (12 tests)
- `HandProcessor` (17 tests)
- `CameraManager` (11 tests)
- `StereoCalibrator` (5 tests)
- `triangulate_point_rays` (2 tests)
- `OllamaGestureRecognizer` circuit breaker (2 tests)
- `HandControlApp` construction (28 tests)

If any fail, the rest of the docs assume a working baseline.

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
