# Click-Through Tkinter Focus Highlight Overlay

The accessibility-navigation mode needs a visible cue every time a swipe fires. A full-screen border + a big "Focus: <DIRECTION>" label works. The trick is that the overlay must be **click-through** (so it never blocks the user's interaction with the app they're navigating) and **not appear in the taskbar**. The recipe is below; it works on Windows out of the box and degrades gracefully elsewhere.

## The full pattern

```python
# In HandControlApp.__init__ (right after root setup):
import ctypes

self.overlay = tk.Toplevel(self.root)
self.overlay.withdraw()                                 # start hidden
self.overlay.overrideredirect(True)                     # no title bar / no taskbar entry
self.overlay.attributes('-topmost', True)               # always on top
try:
    self.overlay.attributes('-transparentcolor', 'white')  # 'white' is the click-through color
except Exception:
    pass

# Make the window itself click-through on Windows
try:
    hwnd = int(self.overlay.frame(), 0) if hasattr(self.overlay, 'frame') else 0
    if hwnd:
        GWL_EXSTYLE = -20
        WS_EX_TRANSPARENT = 0x20       # clicks pass through
        WS_EX_LAYERED    = 0x80000     # allow per-pixel alpha / transparentcolor
        WS_EX_TOOLWINDOW = 0x80        # hide from taskbar
        HWND_TOPMOST     = -1
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        ctypes.windll.user32.SetWindowPos(
            hwnd, HWND_TOPMOST, 0, 0, 0, 0,
            0x0002 | 0x0001 | 0x0010)   # NOMOVE | NOSIZE | NOACTIVATE
except Exception:
    pass

self.overlay_canvas = tk.Canvas(self.overlay, bg='white', highlightthickness=0)
self.overlay_canvas.pack(fill='both', expand=True)
self.overlay_label = None
self._overlay_after_id = None
```

The `bg='white'` matters: it's the same color as `transparentcolor`, so the entire canvas body is invisible except for the drawn border and label.

## Flash method

```python
def flash_overlay(self, direction, duration_ms=400):
    if not hasattr(self, 'overlay'):
        return
    # Cancel any pending hide so rapid swipes extend the flash
    if self._overlay_after_id is not None:
        try:
            self.overlay.after_cancel(self._overlay_after_id)
        except Exception:
            pass
        self._overlay_after_id = None
    sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
    # Convert hex color (#RRGGBB) to a name Tkinter understands, or pass a hex string
    c = self.focus_highlight_color
    thickness = max(1, int(self.focus_highlight_thickness))
    self.overlay.geometry(f"{sw}x{sh}+0+0")
    self.overlay_canvas.config(width=sw, height=sh)
    self.overlay_canvas.delete('all')
    # Four rectangles form a border
    self.overlay_canvas.create_rectangle(0, 0, sw, thickness, fill=c, outline=c)
    self.overlay_canvas.create_rectangle(0, sh - thickness, sw, sh, fill=c, outline=c)
    self.overlay_canvas.create_rectangle(0, 0, thickness, sh, fill=c, outline=c)
    self.overlay_canvas.create_rectangle(sw - thickness, 0, sw, sh, fill=c, outline=c)
    # Big label
    label = f"Focus: {direction.replace('swipe_', '').upper()}"
    self.overlay_label = self.overlay_canvas.create_text(
        sw // 2, sh // 2, text=label,
        font=("Segoe UI", 96, "bold"), fill=c)
    self.overlay.deiconify()
    self.overlay.lift()
    self._overlay_after_id = self.overlay.after(duration_ms, self._hide_overlay)

def _hide_overlay(self):
    try:
        self.overlay.withdraw()
    except Exception:
        pass
    self._overlay_after_id = None
```

## Pitfalls

- **`transparentcolor` must match the canvas `bg` exactly.** If the canvas is `bg='white'`, the attribute must be `'white'`. Off-by-one color and the overlay stops being click-through.
- **`overrideredirect(True)`** is required to suppress the title bar and the taskbar entry. Without it, the overlay shows up as a tiny blank window in the taskbar.
- **`hasattr(self.overlay, 'frame')` may be False on some Tk builds.** The `int(..., 0) if hasattr(...) else 0` line guards against that. If the ctypes block silently fails, the overlay still works visually — it just isn't click-through. Verify by clicking "through" the overlay; if it eats the click, the ctypes block didn't take.
- **`after_cancel`** on a hidden/already-cancelled id raises `TclError`. Always wrap in `try/except`.
- **Color setting**: Tkinter accepts `#RRGGBB` strings directly for `fill=`. No need to convert to a tuple.
- **Dwell lock**: combine with a `self._dwell_until` timestamp set in `accessibility_focus()` and checked at the top of the same method, so swipes within `focus_dwell` seconds of the last navigation are ignored.

## Reusability

This pattern is useful anywhere you need a non-blocking, click-through visual cue in a Tkinter app — focus indicators, edge-glow notifications, "do not disturb" overlays, or full-screen presentation mode that still lets the user click into the underlying app.

## Persistent Selection Overlay (tracks the currently-focused UI element)

The flash overlay above is **transient** — it only shows for 400ms after a swipe. To know **at all times** what the next click/Enter will activate, you need a **persistent** border that hugs the currently-focused UI element. This is the "selection" the user is selecting.

Two pieces:

### 1. Find the focused control (Win32 `GetGUIThreadInfo`)

The Win32 API call `GetGUIThreadInfo(threadId, GUITHREADINFO*)` returns the focused control HWND for a thread. The caller must populate the struct's `cbSize` field, **otherwise the call returns zeros** and you get the whole screen.

```python
import ctypes
from ctypes import wintypes
import struct

# GUITHREADINFO layout (64-bit):
#   DWORD  cbSize         (offset 0,  4 bytes)
#   DWORD  flags          (offset 4,  4 bytes)
#   HWND   hwndActive     (offset 8,  8 bytes)
#   HWND   hwndFocus      (offset 16, 8 bytes)
#   HWND   hwndCapture    (offset 24, 8 bytes)
#   HWND   hwndMenuOwner  (offset 32, 8 bytes)
#   HWND   hwndMoveSize   (offset 40, 8 bytes)
#   HWND   hwndCaret      (offset 48, 8 bytes)
#   RECT   rcCaret        (offset 56, 16 bytes)
#   Total: 72 bytes.
# CRITICAL: cbSize at offset 0 must be set or the call returns zeros.
GUI_INFO = ctypes.create_string_buffer(72)
struct.pack_into('I', GUI_INFO, 0, 72)   # cbSize = 72

hwnd_fg = ctypes.windll.user32.GetForegroundWindow()
thread_id = ctypes.windll.user32.GetWindowThreadProcessId(hwnd_fg, None)
ok = ctypes.windll.user32.GetGUIThreadInfo(thread_id, GUI_INFO)
if not ok:
    return None
focus_hwnd = struct.unpack_from('P', GUI_INFO, 16)[0]  # offset of hwndFocus
target = focus_hwnd if focus_hwnd else hwnd_fg
rect = ctypes.wintypes.RECT()
ctypes.windll.user32.GetWindowRect(target, ctypes.byref(rect))
# rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
```

Works for native Win32, UWP, and most modern apps. Some embedded Edge/WPF controls may report their inner focus as a tiny rect; the 4-px padding in the overlay helps.

### 2. Poll at ~10 Hz and update a click-through Toplevel

Re-use the same `WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW` window style from the flash overlay, but with a Toplevel **sized to the focused element** instead of the full screen. Schedule the next refresh with `self.root.after(100, ...)` (10 Hz is enough — the human eye can't see sub-100ms changes anyway).

```python
def refresh_selection_overlay(self):
    rect = self._get_focused_element_rect()
    if rect is None:
        # No foreground window; just hide
        self.selection_overlay.withdraw()
    else:
        x, y, w, h = rect
        pad = 4
        sw, sh = w + 2*pad, h + 2*pad
        self.selection_overlay.geometry(f"{sw}x{sh}+{x-pad}+{y-pad}")
        self.selection_canvas.config(width=sw, height=sh)
        self.selection_canvas.delete('all')
        # Chunky ring border
        c = self.focus_highlight_color
        t = max(2, self.focus_highlight_thickness)
        for coords in [(0, 0, sw, t), (0, sh - t, sw, sh),
                       (0, 0, t, sh), (sw - t, 0, sw, sh)]:
            self.selection_canvas.create_rectangle(*coords, fill=c, outline=c)
        # Small "SELECTED" label
        self.selection_canvas.create_text(
            sw - 8, 8, text="SELECTED", anchor="ne",
            font=("Segoe UI", 9, "bold"), fill=c)
        self.selection_overlay.deiconify()
        self.selection_overlay.lift()
    # Schedule next refresh
    self._selection_after_id = self.root.after(100, self.refresh_selection_overlay)
```

### Pitfalls specific to the persistent overlay

- **`GetGUIThreadInfo` requires `cbSize` to be set.** Forgetting `struct.pack_into('I', GUI_INFO, 0, 72)` returns zeros and you draw a full-screen border. Always set the cbSize; the API documents this but most code samples skip it.
- **Must cancel `after` on `Stop()` and `on_close()`.** Otherwise the after-loop keeps firing and the cancelled Toplevels leak. Mirror the pattern in `stop()`.
- **Poll cadence matters.** 10 Hz is plenty; 30+ Hz wastes CPU. Under 5 Hz the border visibly lags focus changes from the keyboard.
- **Foreground-thread focus is a moving target.** When the user clicks on another app, `hwnd_focus` jumps. The `withdraw()` fallback for `rect is None` covers the brief "no focused element" gap.
- **Multi-monitor**: `GetForegroundWindow` returns the foreground on the active monitor. The selection overlay appears on the correct monitor automatically because its `geometry(x, y, w, h)` uses absolute screen coords.
- **Padded ring (4 px) on tiny elements.** Buttons smaller than ~20px tall look bad with a 6px ring on top of them. Cap the ring thickness relative to the element size, or fall back to the parent window rect for very small focused controls.

### Refresh-loop lifecycle

```python
# In __init__:
self.selection_overlay = None
self._selection_after_id = None

# In start(): kick off the loop (if user has it enabled)
if self.show_selection_overlay and self._selection_after_id is None:
    self.refresh_selection_overlay()

# In stop() / on_close(): cancel + withdraw
if self._selection_after_id is not None:
    self.root.after_cancel(self._selection_after_id)
    self._selection_after_id = None
if self.selection_overlay is not None:
    self.selection_overlay.withdraw()
```

### What this is good for beyond hand-tracking

The same pattern (click-through Tkinter Toplevel + Win32 `GetGUIThreadInfo` poll at 10 Hz) is useful for:

- **Accessibility review tooling** (highlight every focused element as a user navigates — useful for screenshot tutorials and bug reports)
- **Magnifier on hover** (the overlay could be a translucent magnifier of the focused element)
- **"Where am I?" persistent indicators** for screen-reader users

The Toplevel stays click-through because the `WS_EX_TRANSPARENT` style is set on the **window** (not the canvas) — clicks always reach whatever is behind it.
