# Create Desktop Shortcut (PowerShell)
# This script drops a Windows .lnk on the current user's desktop that launches
# the Tony Stark hand control GUI via the system Python.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File create_desktop_shortcut.ps1
#
# It is a dependency-free alternative to the Python `winshell`/`pywin32` path.

$ErrorActionPreference = 'Stop'

# Resolve paths
$scriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Definition
# Project root is one level up from the scripts/ directory
$projectRoot = Resolve-Path (Join-Path $scriptDir '..')
$pythonExe   = (Get-Command python.exe -ErrorAction Stop).Source
$targetScript = Join-Path $projectRoot 'tony_stark_hud_control.py'
if (-not (Test-Path $targetScript)) {
    throw "Could not find $targetScript. Run this from the project root."
}

$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'Tony Stark Hand Control.lnk'

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath       = $pythonExe
$shortcut.Arguments        = "`"$targetScript`""
$shortcut.WorkingDirectory = $projectRoot
$shortcut.IconLocation     = "$pythonExe,0"
$shortcut.WindowStyle      = 1   # normal
$shortcut.Description      = 'Launch the Tony Stark Hand Control GUI'
$shortcut.Save()

Write-Host "Shortcut created: $shortcutPath"
Write-Host "Target: $pythonExe `"$targetScript`""
