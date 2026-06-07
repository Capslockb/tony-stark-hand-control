"""Targeted regression test for the two bugs from the v1.0.0 release:

1. RoomMap.add() with numpy 0-d arrays (from matplotlib proj3d.inv_transform)
   previously failed with TypeError: only 0-dimensional arrays can be
   converted to Python scalars.

2. flash_overlay() with a hex color string previously failed with
   _tkinter.TclError: unknown color name "00FF00" because the code stripped
   the '#' but then passed the bare hex to tk.Canvas.create_rectangle.
"""
import os, sys, importlib.util
import numpy as np
import tkinter as tk

# Load the main app module
spec = importlib.util.spec_from_file_location(
    'm', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tony_stark_hud_control.py')))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_roommap_add_handles_numpy_0d():
    """RoomMap.add() must accept numpy 0-d arrays (and 1-d arrays,
    lists, and Python numbers). The old code crashed with:
        TypeError: only 0-dimensional arrays can be converted to Python scalars
    """
    rm = m.RoomMap()
    # numpy 0-d arrays (the matplotlib inv_transform return type)
    a1 = rm.add(np.float64(1.5), np.float64(2.5), np.float64(3.5))
    assert a1['x'] == 1.5 and a1['y'] == 2.5 and a1['z'] == 3.5
    # 1-d arrays
    a2 = rm.add(np.array([4.0]), np.array([5.0]), np.array([6.0]))
    assert a2['x'] == 4.0 and a2['y'] == 5.0 and a2['z'] == 6.0
    # Python floats (regular case)
    a3 = rm.add(7.0, 8.0, 9.0)
    assert a3['x'] == 7.0 and a3['y'] == 8.0 and a3['z'] == 9.0
    # ints should be promoted
    a4 = rm.add(10, 11, 12)
    assert a4['x'] == 10.0 and a4['y'] == 11.0 and a4['z'] == 12.0
    # And the JSON round-trip must still work
    rm.path = os.path.join(os.path.dirname(__file__), '_test_roommap.json')
    try:
        rm.save()
        rm2 = m.RoomMap()
        rm2.path = rm.path
        rm2.load()
        assert len(rm2.anchors) == 4
        for orig, loaded in zip(rm.anchors, rm2.anchors):
            assert orig['x'] == loaded['x']
            assert orig['y'] == loaded['y']
            assert orig['z'] == loaded['z']
    finally:
        try: os.unlink(rm.path)
        except: pass
    print("  [PASS] RoomMap.add handles numpy 0-d / 1-d / lists / numbers")


def test_flash_overlay_color_format():
    """flash_overlay() must accept hex color strings in BOTH forms
    (with and without leading '#') and pass a valid color to tk.

    The old code stripped the '#' and then passed '00FF00' to
    tk.Canvas.create_rectangle, which raises:
        _tkinter.TclError: unknown color name "00FF00"
    """
    # Build a minimal app instance (no mainloop)
    # HandControlApp takes a tk.Tk root. Import tkinter as tk.
    import tkinter as _tk
    app = m.HandControlApp(_tk.Tk())
    # Hide the window so it doesn't pop up
    app.root.withdraw()

    # Test with the # form
    app.focus_highlight_color = '#00FF00'
    try:
        app.flash_overlay('test_left')
        print("  [PASS] flash_overlay accepts '#00FF00'")
    except tk.TclError as e:
        print(f"  [FAIL] flash_overlay('#00FF00') raised TclError: {e}")
        raise

    # Test with the bare-hex form (the old bug)
    app.focus_highlight_color = 'FF00FF'
    try:
        app.flash_overlay('test_right')
        print("  [PASS] flash_overlay accepts 'FF00FF' (bare hex)")
    except tk.TclError as e:
        print(f"  [FAIL] flash_overlay('FF00FF') raised TclError: {e}")
        raise

    # Test with a named color
    app.focus_highlight_color = 'red'
    try:
        app.flash_overlay('test_up')
        print("  [PASS] flash_overlay accepts 'red'")
    except tk.TclError as e:
        print(f"  [FAIL] flash_overlay('red') raised TclError: {e}")
        raise

    # Test with None
    app.focus_highlight_color = None
    try:
        app.flash_overlay('test_down')
        print("  [PASS] flash_overlay accepts None (falls back to #00FF00)")
    except tk.TclError as e:
        print(f"  [FAIL] flash_overlay(None) raised TclError: {e}")
        raise

    # Clean up
    try: app.root.destroy()
    except: pass


if __name__ == "__main__":
    print("=== v1.0.0 hot-fix regression tests ===")
    test_roommap_add_handles_numpy_0d()
    test_flash_overlay_color_format()
    print("All v1.0.0 hot-fix tests PASSED")
