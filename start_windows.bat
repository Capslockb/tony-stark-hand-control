@echo off
REM Tony Stark Hand Control - Windows launcher
REM Activates the venv if present, then launches the app.

setlocal
cd /d "%~dp0"

REM If a venv exists, activate it. Otherwise use the system Python.
if exist ".venv\Scripts\activate.bat" (
    echo Using venv...
    call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    echo Using venv...
    call "venv\Scripts\activate.bat"
) else (
    echo No venv found; using system Python. Run install_wizard.py to set up a venv.
)

REM Launch the app
python tony_stark_hud_control.py %*

endlocal
