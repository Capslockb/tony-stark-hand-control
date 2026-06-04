"""Generate the 3D room mapping diagram for docs/images/3d_room.svg.

Dark-themed matplotlib 3D figure showing:
  - Camera frustums at calibrated world positions
  - Live hand position
  - Anchor placement (walls, zones, hotspots)
  - View buttons (top-down, front, side, 3/4)
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

OUT_DIR = os.path.join(os.path.dirname(__file__), "images")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, "3d_room.svg")

BG = "#101418"
FG = "#88FF88"
ACCENT = "#00aaff"
HAND = "#00ff66"
WALL = "#aa8866"
ZONE = "#66aaff"
HOT = "#ff6644"

# Synthetic room: 2 cameras + 1 hand + 4 anchors
# Camera 0 at (0, 0, 0), Camera 1 at (0.10, 0, 0)
# Hand at (0.02, 0.01, 0.6) (in front of the cameras)
# Anchors: a wall, a zone, a hotspot, a piece of furniture
anchors = [
    {"x": -0.5, "y": 0.0, "z": 0.5, "type": "wall", "name": "wall_north"},
    {"x": 0.0,  "y": 0.6, "z": 0.0, "type": "wall", "name": "wall_east"},
    {"x": 0.2,  "y": 0.3, "z": 0.2, "type": "zone", "name": "kitchen"},
    {"x": 0.4,  "y": 0.4, "z": 1.2, "type": "hotspot", "name": "lamp"},
]
hand = (0.02, 0.01, 0.6)
cams = [
    {"pos": (0, 0, 0),     "forward": (0, 0, 1), "name": "cam0"},
    {"pos": (0.10, 0, 0),  "forward": (-0.1, 0, 1), "name": "cam1"},
]

fig = plt.figure(figsize=(10, 7), dpi=120)
fig.patch.set_facecolor(BG)
ax = fig.add_subplot(111, projection="3d")
ax.set_facecolor(BG)
ax.xaxis.pane.set_visible(False)
ax.yaxis.pane.set_visible(False)
ax.zaxis.pane.set_visible(False)
ax.set_xlabel("X (m)", color=FG)
ax.set_ylabel("Y (m)", color=FG)
ax.set_zlabel("Z (m)", color=FG)
ax.tick_params(colors=FG)
ax.set_title("Room map - top-down view (drag to rotate)",
             color=FG, fontsize=12, loc="left")
ax.view_init(elev=70, azim=-90)

# Cameras
for c in cams:
    px, py, pz = c["pos"]
    fx, fy, fz = c["forward"]
    L = 0.3
    # Forward ray
    ax.plot([px, px+L*fx], [py, py+L*fy], [pz, pz+L*fz], color=ACCENT, lw=2)
    # Frustum cone (4 rays)
    for ang in (0, 90, 180, 270):
        a = np.radians(ang)
        dx = 0.1*np.cos(a)
        dy = 0.1*np.sin(a)
        tip_x, tip_y, tip_z = px+L*fx, py+L*fy, pz+L*fz
        ax.plot([tip_x, tip_x+dx], [tip_y, tip_y+dy], [tip_z, tip_z],
               color=ACCENT, lw=0.5, alpha=0.6)
    ax.text(px, py, pz+0.05, c["name"], color=ACCENT, fontsize=8, ha="center")

# Anchors
type_color = {"wall": WALL, "zone": ZONE, "hotspot": HOT}
for a in anchors:
    c = type_color.get(a["type"], FG)
    ax.scatter([a["x"]], [a["y"]], [a["z"]], color=c, s=100, marker="o",
               edgecolors="white", linewidths=0.5)
    ax.text(a["x"], a["y"], a["z"]+0.04, a["name"], color="white", fontsize=7, ha="center")

# Hand
hx, hy, hz = hand
ax.scatter([hx], [hy], [hz], color=HAND, s=160, marker="*",
           edgecolors="white", linewidths=0.5)
ax.text(hx, hy, hz+0.06, "HAND", color=HAND, fontsize=9, ha="center", weight="bold")

# Auto-fit
all_pts = list(c["pos"] for c in cams) + [(a["x"], a["y"], a["z"]) for a in anchors] + [hand]
pts = np.array(all_pts)
center = pts.mean(axis=0)
spread = max(0.6, float(np.linalg.norm(pts - center, axis=1).max()) * 1.4)
ax.set_xlim(center[0]-spread, center[0]+spread)
ax.set_ylim(center[1]-spread, center[1]+spread)
ax.set_zlim(0, center[2]+spread)

plt.tight_layout()
plt.savefig(OUT_PATH, facecolor=BG, bbox_inches="tight", format="svg")
print(f"Wrote {OUT_PATH} ({os.path.getsize(OUT_PATH)//1024} KB)")
