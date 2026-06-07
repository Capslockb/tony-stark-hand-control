#!/usr/bin/env python3
"""
Local WebSocket connector: bridges browser hand gestures → pyautogui.
Run alongside the hand-control-webapp:
    python3 local_connector.py

Accepts WebSocket connections on 127.0.0.1:8124.
Sends: cursor positions, click events, swipe events, and gesture state.
"""

import asyncio
import json
import sys
import time

try:
    import pyautogui
    pyautogui.FAILSAFE = False
except (KeyError, ImportError, OSError):
    pyautogui = None  # Will operate in "preview" mode (log only)

try:
    import websockets
except ImportError:
    print("ERROR: 'websockets' not installed. Run: pip install websockets")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 8124

# Smoothing / scaling
SMOOTHING = 0.45       # cursor smoothing factor (0-1, lower = smoother)
SCALE_X = 1.0          # horizontal sensitivity multiplier
SCALE_Y = 1.0          # vertical sensitivity multiplier
CLICK_HYSTERESIS = 0.3 # seconds between clicks
SCROLL_SPEED = 40      # pixels per scroll tick

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
class ControllerState:
    def __init__(self):
        self.screen_w, self.screen_h = pyautogui.size() if pyautogui else (1920, 1080)
        self.last_click_time = 0.0
        self.last_scroll_time = 0.0
        self.drag_active = False
        self.fist_cooldown = 0.0
        self.open_palm_active = False  # engagement toggle

    def cursor_move(self, x_norm: float, y_norm: float):
        """Move mouse to normalized [0,1] coordinates."""
        if not pyautogui:
            return
        sx = x_norm * self.screen_w * SCALE_X
        sy = y_norm * self.screen_h * SCALE_Y
        sx = max(0, min(self.screen_w - 1, sx))
        sy = max(0, min(self.screen_h - 1, sy))
        pyautogui.moveTo(sx, sy, duration=0.0, _pause=False)

    def click_left(self):
        now = time.time()
        if now - self.last_click_time < CLICK_HYSTERESIS:
            return
        self.last_click_time = now
        if pyautogui:
            pyautogui.click(button='left', _pause=False)
        print("[CLICK] Left")

    def click_right(self):
        now = time.time()
        if now - self.last_click_time < CLICK_HYSTERESIS:
            return
        self.last_click_time = now
        if pyautogui:
            pyautogui.click(button='right', _pause=False)
        print("[CLICK] Right")

    def scroll(self, delta_y: int):
        now = time.time()
        if now - self.last_scroll_time < 0.05:
            return
        self.last_scroll_time = now
        if pyautogui:
            pyautogui.scroll(delta_y, _pause=False)
        print(f"[SCROLL] delta={delta_y}")

    def swipe(self, direction: str):
        """Map swipe direction to Alt+Left / Alt+Right (browser back/forward)."""
        if not pyautogui:
            return
        if direction == 'left':
            pyautogui.hotkey('alt', 'left', _pause=False)
            print("[SWIPE] ← Back")
        elif direction == 'right':
            pyautogui.hotkey('alt', 'right', _pause=False)
            print("[SWIPE] → Forward")

    def open_palm(self):
        """Toggle engagement: enable/disable cursor control."""
        self.open_palm_active = not self.open_palm_active
        status = "ENGAGED" if self.open_palm_active else "DISENGAGED"
        print(f"[PALM] {status}")

    def fist(self):
        """Fist = emergency disengage or toggle."""
        now = time.time()
        if now - self.fist_cooldown < 1.0:
            return
        self.fist_cooldown = now
        self.open_palm_active = False
        print("[FIST] Disengaged")


ctrl = ControllerState()

# ---------------------------------------------------------------------------
# WebSocket handler
# ---------------------------------------------------------------------------
async def handler(websocket):
    print(f"[+] Bridge connected: {websocket.remote_address}")
    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            t = msg.get("type", "")

            if t == "cursor":
                x, y = msg.get("x", 0.5), msg.get("y", 0.5)
                if ctrl.open_palm_active:
                    ctrl.cursor_move(x, y)

            elif t == "click":
                btn = msg.get("button", "left")
                if ctrl.open_palm_active:
                    if btn == "left":
                        ctrl.click_left()
                    elif btn == "right":
                        ctrl.click_right()

            elif t == "swipe":
                direction = msg.get("direction", "left")
                # Swipes work regardless of palm state
                ctrl.swipe(direction)

            elif t == "open_palm":
                ctrl.open_palm()

            elif t == "fist":
                ctrl.fist()

            else:
                print(f"[?] Unknown message type: {t}")

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        print(f"[-] Bridge disconnected: {websocket.remote_address}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    print(f"╔══════════════════════════════════════╗")
    print(f"║  Hand Control WebApp — Local Bridge  ║")
    print(f"║  ws://{HOST}:{PORT}                    ║")
    print(f"║  pyautogui: {'yes' if pyautogui else 'NO (preview mode)'}          ║")
    print(f"║  Screen: {ctrl.screen_w}×{ctrl.screen_h}                 ║")
    print(f"╚══════════════════════════════════════╝")
    print()
    print("Starting hand tracking is ENABLED (open palm to engage cursor).")

    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
