"""Generate the architecture diagram for docs/images/architecture.svg.

Dark-themed diagram showing the 5 main subsystems and how data flows:
  cameras -> HandProcessor (worker) -> HandControlApp -> tk/3D/overlay
  RoomMap, StereoCalibrator, Ollama (optional), single-instance lock

Uses matplotlib (already a dep). No external assets.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mp
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT_DIR = os.path.join(os.path.dirname(__file__), "images")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, "architecture.svg")

# Color palette (dark theme)
BG = "#0d1117"
FG = "#e6edf3"
ACCENT = "#58a6ff"
WARN = "#f0883e"
SUCCESS = "#56d364"
MUTED = "#8b949e"
BOX_BG = "#161b22"
BOX_EDGE = "#30363d"
HIGHLIGHT = "#1f6feb"

# Layout helpers
def box(ax, xy, w, h, label, sub=None, color=ACCENT, edge=BOX_EDGE, bg=BOX_BG, fontsize=11, sub_size=8):
    """Draw a rounded box with title + optional subtitle."""
    x, y = xy
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                       linewidth=1.5, edgecolor=edge, facecolor=bg)
    ax.add_patch(p)
    # Title centered
    ax.text(x + w/2, y + h - 0.32, label, ha="center", va="top",
            color=color, fontsize=fontsize, weight="bold")
    if sub:
        ax.text(x + w/2, y + h - 0.65, sub, ha="center", va="top",
                color=MUTED, fontsize=sub_size)


def arrow(ax, start, end, color=MUTED, lw=1.5, style="-|>"):
    a = FancyArrowPatch(start, end, arrowstyle=style,
                        mutation_scale=15, linewidth=lw, color=color)
    ax.add_patch(a)


# Canvas
fig, ax = plt.subplots(figsize=(14, 9), dpi=120)
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(0, 14)
ax.set_ylim(0, 9)
ax.set_axis_off()
ax.set_title("Tony Stark Hand Control - Architecture",
             color=FG, fontsize=16, weight="bold", pad=10, loc="left")
ax.text(0.1, 8.7, "Multi-camera hand tracking -> 3D reconstruction -> PC control (accessibility-first)",
        color=MUTED, fontsize=10, transform=ax.transData)

# --- Layer 1: Camera inputs (left column) ---
box(ax, (0.2, 5.5), 2.4, 1.2, "Cameras (1-4)", "DSHOW / MSMF / ANY\n480x360 @ 30 fps", color=ACCENT)
box(ax, (0.2, 3.9), 2.4, 1.2, "CameraManager", "is_feed_live()\nauto-blacklist\nOPEN/READ timeouts", color=SUCCESS)
box(ax, (0.2, 2.3), 2.4, 1.2, "StereoCalibrator", "Phase A intrinsics\nPhase B shared frame\ncalibration.npz", color=SUCCESS)

# --- Layer 2: HandProcessor (center, the brain) ---
box(ax, (3.3, 3.5), 3.2, 3.2, "HandProcessor (worker thread)",
    "MediaPipe HandLandmarker (VIDEO mode)\n"
    "One-Euro filter (per-tip)\n"
    "Velocity tracker\n"
    "Predictor (dead reckoning + decay)\n"
    "is_palm_open (wrist-relative)\n"
    "engage / disengage heuristic",
    color=HIGHLIGHT, fontsize=11)

# --- Layer 3: Output systems (right column) ---
box(ax, (7.0, 6.5), 3.2, 1.0, "3D Reconstruction",
    "undistort + K^-1 + ray triangulation\n5 fingertips -> 3D world point", color=SUCCESS)
box(ax, (7.0, 5.0), 3.2, 1.0, "Gesture Engine",
    "thumb+index = Enter\nswipe = Tab/Arrow\npalm-hold = engage", color=ACCENT)
box(ax, (7.0, 3.5), 3.2, 1.0, "HUD Overlay",
    "Static base cached, np.maximum blit\n5 fingertip markers per cam", color=ACCENT)
box(ax, (7.0, 2.0), 3.2, 1.0, "Selection Border",
    "Win32 GetGUIThreadInfo\ncbSize MUST be set\n10 Hz refresh", color=ACCENT)
box(ax, (7.0, 0.5), 3.2, 1.0, "3D / Room Tab",
    "matplotlib 3D viewport\nclick-to-place anchors\nroom_map.json", color=ACCENT)

# --- Layer 4: Top / cross-cutting (very right) ---
box(ax, (10.6, 6.5), 3.0, 1.0, "Ollama (optional)",
    "cloud or local LLM\ncircuit breaker (3 fail -> 30s)\nOFF by default", color=WARN)
box(ax, (10.6, 5.0), 3.0, 1.0, "RoomMap",
    "add/remove/clear/save/load\nJSON, auto-saves on close", color=SUCCESS)
box(ax, (10.6, 3.5), 3.0, 1.0, "Single-Instance Lock",
    "Win32 named mutex\nmsvcrt file lock\n+ SetForegroundWindow on dup", color=WARN)
box(ax, (10.6, 2.0), 3.0, 1.0, "Performance Readout",
    "win32 GetProcessTimes\nGetProcessMemoryInfo\nloop ms, cpu%, ram, threads", color=SUCCESS)
box(ax, (10.6, 0.5), 3.0, 1.0, "Tkinter GUI",
    "6 tabs: Main / Ollama / Tracking\n       Access / 3D / Cameras\nasync startup, throttled redraw", color=ACCENT, fontsize=11)

# --- Arrows: data flow ---
# Camera -> CameraManager
arrow(ax, (1.4, 5.5), (1.4, 5.1), color=ACCENT)
# CameraManager -> HandProcessor
arrow(ax, (2.6, 4.5), (3.3, 4.8), color=ACCENT)
# StereoCalibrator -> HandProcessor (3D)
arrow(ax, (2.6, 2.9), (3.3, 4.0), color=SUCCESS)
# HandProcessor -> 3D Reconstruction
arrow(ax, (6.5, 6.0), (7.0, 6.8), color=SUCCESS)
# HandProcessor -> Gesture Engine
arrow(ax, (6.5, 5.5), (7.0, 5.3), color=ACCENT)
# HandProcessor -> HUD
arrow(ax, (6.5, 5.0), (7.0, 4.0), color=ACCENT)
# HandProcessor -> Selection Border (via gesture output)
arrow(ax, (6.5, 4.5), (7.0, 2.5), color=ACCENT)
# 3D Reconstruction -> 3D / Room Tab
arrow(ax, (10.2, 6.8), (10.6, 0.8), color=SUCCESS, style="->")
# RoomMap <-> 3D / Room Tab
arrow(ax, (10.2, 1.0), (10.6, 0.8), color=SUCCESS)
arrow(ax, (10.6, 0.8), (10.2, 1.0), color=SUCCESS)
# Ollama -> Gesture Engine (optional)
arrow(ax, (10.6, 6.8), (10.2, 5.5), color=WARN, style="->")
# Selection Border -> Tk GUI (consumes focus rect)
arrow(ax, (10.6, 2.5), (10.6, 1.0), color=ACCENT)

# Legend
ax.text(0.2, 1.2, "Legend:", color=FG, fontsize=10, weight="bold")
ax.scatter([0.9], [1.2], s=80, c=ACCENT, transform=ax.transData)
ax.text(1.05, 1.2, "Core pipeline", color=FG, fontsize=9, va="center")
ax.scatter([2.6], [1.2], s=80, c=SUCCESS, transform=ax.transData)
ax.text(2.75, 1.2, "3D / persistence", color=FG, fontsize=9, va="center")
ax.scatter([4.3], [1.2], s=80, c=WARN, transform=ax.transData)
ax.text(4.45, 1.2, "Optional / cross-cutting", color=FG, fontsize=9, va="center")
ax.scatter([6.4], [1.2], s=80, c=HIGHLIGHT, transform=ax.transData)
ax.text(6.55, 1.2, "HandProcessor (worker)", color=FG, fontsize=9, va="center")

# Save
plt.tight_layout()
plt.savefig(OUT_PATH, facecolor=BG, bbox_inches="tight", format="svg")
print(f"Wrote {OUT_PATH}")
print(f"Size: {os.path.getsize(OUT_PATH) // 1024} KB")
