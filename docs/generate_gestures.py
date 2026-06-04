"""Generate the gesture reference diagram for docs/images/gestures.svg.

Dark-themed figure showing each gesture with a stylized hand and label.
Uses simple matplotlib shapes (no external assets).
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mp
from matplotlib.patches import FancyBboxPatch, Circle, Wedge, Rectangle, FancyArrowPatch

OUT_DIR = os.path.join(os.path.dirname(__file__), "images")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, "gestures.svg")

BG = "#0d1117"
FG = "#e6edf3"
SKIN = "#f0c987"
ACCENT = "#58a6ff"
SUCCESS = "#56d364"
WARN = "#f0883e"
MUTED = "#8b949e"
PALM = "#1f6feb"
TEXT = "#e6edf3"

fig, ax = plt.subplots(figsize=(13, 8), dpi=120)
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(0, 13)
ax.set_ylim(0, 8)
ax.set_axis_off()
ax.set_title("Gesture reference - what each gesture does",
             color=FG, fontsize=15, weight="bold", pad=10, loc="left")
ax.text(0.1, 7.6, "All gestures are recognized by MediaPipe HandLandmarker (21 landmarks) + custom heuristics.",
        color=MUTED, fontsize=10)


def hand_silhouette(ax, cx, cy, gesture, label):
    """Draw a stylized hand for the given gesture at (cx, cy)."""
    # Palm (base circle)
    ax.add_patch(Circle((cx, cy), 0.45, color=SKIN, ec=PALM, lw=2, zorder=2))
    if gesture == "open_palm":
        # 5 fingers up (vertical lines)
        for i, dx in enumerate([-0.30, -0.15, 0.0, 0.15, 0.30]):
            ax.add_patch(Rectangle((cx+dx-0.05, cy+0.40), 0.10, 0.55,
                                   color=SKIN, ec=PALM, lw=1.5, zorder=2))
    elif gesture == "fist":
        # 5 fingers curled (small circles at top of palm)
        for i, dx in enumerate([-0.30, -0.15, 0.0, 0.15, 0.30]):
            ax.add_patch(Circle((cx+dx, cy+0.35), 0.10, color=SKIN, ec=PALM, lw=1.5, zorder=2))
    elif gesture == "click_index":
        # Index up, others curled. Thumb to index.
        ax.add_patch(Rectangle((cx-0.15-0.05, cy+0.40), 0.10, 0.65, color=SKIN, ec=PALM, lw=1.5, zorder=2))
        for i, dx in enumerate([-0.30, 0.0, 0.15, 0.30]):
            ax.add_patch(Circle((cx+dx, cy+0.35), 0.10, color=SKIN, ec=PALM, lw=1.5, zorder=2))
        # Click indicator
        ax.text(cx+0.6, cy+0.2, "CLICK", color=SUCCESS, fontsize=10, weight="bold")
    elif gesture == "click_middle":
        ax.add_patch(Rectangle((cx-0.30-0.05, cy+0.40), 0.10, 0.55, color=SKIN, ec=PALM, lw=1.5, zorder=2))
        ax.add_patch(Rectangle((cx+0.0-0.05, cy+0.40), 0.10, 0.65, color=SKIN, ec=PALM, lw=1.5, zorder=2))
        for dx in [-0.15, 0.15, 0.30]:
            ax.add_patch(Circle((cx+dx, cy+0.35), 0.10, color=SKIN, ec=PALM, lw=1.5, zorder=2))
        ax.text(cx+0.6, cy+0.2, "RIGHT", color=WARN, fontsize=10, weight="bold")
    elif gesture == "swipe":
        # Stylized motion blur
        for i, dx in enumerate([0.0, 0.4, 0.8]):
            alpha = 0.8 - i*0.25
            ax.add_patch(Circle((cx-dx, cy), 0.45, color=SKIN, ec=PALM, lw=2, alpha=alpha, zorder=2))
        for i, dx in enumerate([0.0, 0.4, 0.8]):
            alpha = 0.8 - i*0.25
            ax.add_patch(Rectangle((cx-dx-0.05, cy+0.40), 0.10, 0.55,
                                   color=SKIN, ec=PALM, lw=1.5, alpha=alpha, zorder=2))
        ax.text(cx+1.0, cy, ">", color=ACCENT, fontsize=20, weight="bold")
    # Label
    ax.text(cx, cy-0.7, label, ha="center", color=TEXT, fontsize=10, weight="bold")


gestures = [
    ("open_palm",  "Open palm\n(hold 0.6s)"),
    ("fist",        "Closed fist\n(disengages)"),
    ("click_index", "Thumb + index\n(Enter / click)"),
    ("click_middle","Thumb + middle\n(right-click)"),
    ("swipe",       "Swipe\n(Tab/Shift+Tab/Arrow)"),
]

# Layout: 5 gestures in a row
y_row = 4.0
spacing = 13.0 / 6
for i, (g, label) in enumerate(gestures):
    cx = (i + 0.5) * spacing
    hand_silhouette(ax, cx, y_row, g, label)

# Distance threshold visualization
ax.text(6.5, 1.8, "How click detection works:", color=FG, fontsize=11, weight="bold", ha="center")
ax.text(6.5, 1.4,
        "Normalized 2D distance between thumb tip and each other fingertip. "
        "If < 0.05 -> 'click' fires.",
        color=MUTED, fontsize=9, ha="center")
ax.text(6.5, 1.0,
        "How swipe detection works: predicted index-finger velocity > 300 px/s for 0.5s window.",
        color=MUTED, fontsize=9, ha="center")
ax.text(6.5, 0.6,
        "How engage works: is_palm_open() true for 0.6s of frames, averaged over ring buffer.",
        color=MUTED, fontsize=9, ha="center")

plt.tight_layout()
plt.savefig(OUT_PATH, facecolor=BG, bbox_inches="tight", format="svg")
print(f"Wrote {OUT_PATH} ({os.path.getsize(OUT_PATH)//1024} KB)")
