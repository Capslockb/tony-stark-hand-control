"""Tony Stark Hand Control - cross-platform install wizard.

Verifies the Python environment, installs dependencies, downloads the
MediaPipe hand-landmark model, and (on Windows) creates a desktop
shortcut. Runs as a normal Python script -- no admin needed for
the user-site install path.

Usage:
    python install_wizard.py
"""
from __future__ import annotations

import os
import sys
import platform
import subprocess
import shutil
import urllib.request
from pathlib import Path

# ---- Constants ----
MIN_PY = (3, 10)
SCRIPT_DIR = Path(__file__).resolve().parent
HAND_LANDMARKER_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
)
HAND_LANDMARKER_DEST = SCRIPT_DIR / "hand_landmarker.task"


def header(text: str) -> None:
    bar = "=" * 60
    print(f"\n{bar}\n{text}\n{bar}")


def ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def step_python() -> bool:
    header("Step 1/5: Python version check")
    pv = sys.version_info
    if (pv.major, pv.minor) >= MIN_PY:
        ok(f"Python {pv.major}.{pv.minor}.{pv.micro} >= {MIN_PY[0]}.{MIN_PY[1]}")
        return True
    fail(f"Python {pv.major}.{pv.minor} is too old (need >= {MIN_PY[0]}.{MIN_PY[1]})")
    print("  Download a newer Python from https://www.python.org/downloads/")
    return False


def step_pip() -> bool:
    header("Step 2/5: pip + dependencies")
    try:
        import pip  # noqa: F401
    except ImportError:
        fail("pip is not available")
        return False
    ok("pip is available")
    req = SCRIPT_DIR / "requirements.txt"
    if not req.exists():
        fail(f"requirements.txt not found at {req}")
        return False
    print(f"  Installing from {req.name} ...")
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(req), "--upgrade"]
    try:
        subprocess.check_call(cmd)
        ok("Dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        fail(f"pip install failed (exit {e.returncode})")
        print("  Try manually:  python -m pip install -r requirements.txt")
        return False


def step_imports() -> bool:
    header("Step 3/5: Import smoke test")
    modules = ["cv2", "mediapipe", "numpy", "tkinter", "matplotlib"]
    if platform.system() == "Windows":
        modules += ["win32com", "winshell", "PIL"]
    all_ok = True
    for m in modules:
        try:
            __import__(m)
            ok(f"import {m}")
        except Exception as e:
            fail(f"import {m}: {e}")
            all_ok = False
    return all_ok


def step_model() -> bool:
    header("Step 4/5: MediaPipe hand_landmarker.task")
    if HAND_LANDMARKER_DEST.exists() and HAND_LANDMARKER_DEST.stat().st_size > 1_000_000:
        ok(f"Already present at {HAND_LANDMARKER_DEST.name} "
           f"({HAND_LANDMARKER_DEST.stat().st_size // 1024 // 1024} MB)")
        return True
    print(f"  Downloading {HAND_LANDMARKER_URL}")
    print(f"  -> {HAND_LANDMARKER_DEST}")
    try:
        with urllib.request.urlopen(HAND_LANDMARKER_URL, timeout=30) as r, \
             open(HAND_LANDMARKER_DEST, "wb") as f:
            shutil.copyfileobj(r, f)
        size_mb = HAND_LANDMARKER_DEST.stat().st_size // 1024 // 1024
        if size_mb < 1:
            fail(f"Downloaded file is suspiciously small ({size_mb} MB)")
            return False
        ok(f"Downloaded ({size_mb} MB)")
        return True
    except Exception as e:
        fail(f"Download failed: {e}")
        print("  The app can also download the model itself on first launch.")
        return False


def step_shortcut() -> bool:
    header("Step 5/5: Desktop shortcut (Windows only)")
    if platform.system() != "Windows":
        ok("Skipped (not on Windows)")
        return True
    try:
        # Delegate to the script's own --create-shortcut flag
        subprocess.check_call([sys.executable, str(SCRIPT_DIR / "tony_stark_hud_control.py"),
                               "--create-shortcut"])
        ok("Desktop shortcut created")
        return True
    except subprocess.CalledProcessError as e:
        warn(f"Shortcut creation failed (exit {e.returncode}). You can create it manually.")
        return True  # not fatal


def main() -> int:
    print("Tony Stark Hand Control - install wizard")
    print(f"Script dir: {SCRIPT_DIR}")
    print(f"Python:     {sys.executable} ({platform.python_version()})")
    print(f"OS:         {platform.system()} {platform.release()}")
    print()
    steps = [step_python, step_pip, step_imports, step_model, step_shortcut]
    for s in steps:
        if not s():
            print("\nInstallation failed at:", s.__name__)
            print("Fix the issue above and re-run this script.")
            return 1
    header("Install complete")
    print("To start the app:")
    if platform.system() == "Windows":
        print("  - Double-click the desktop shortcut 'Tony Stark Hand Control', or")
        print("  - Run:  start_windows.bat")
    else:
        print("  - Run:  python3 tony_stark_hud_control.py")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
