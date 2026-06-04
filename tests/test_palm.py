"""Test the fixed is_palm_open() against multiple hand poses."""
import math
import importlib.util
spec = importlib.util.spec_from_file_location(
    'm', r'C:/Users/Bernardo/tony_stark_hand_control/tony_stark_hud_control.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class L:
    """Minimal MediaPipe-shaped landmark (just .x, .y, .z)."""
    __slots__ = ('x', 'y', 'z')
    def __init__(self, x, y, z=0):
        self.x, self.y, self.z = x, y, z


def make_hand(wrist=(0.5, 0.9, 0), extended=True, num_fingers=4):
    """Build a 21-landmark hand. If `extended` is True, the fingers
    are straight and the tip is far from the wrist. If False, the
    fingers are curled (tip close to the wrist, near the PIP joint)."""
    lms = [L(*wrist)]  # 0: wrist
    # 1-4: thumb
    if extended and num_fingers >= 1:
        lms += [L(wrist[0] - 0.05, wrist[1] - 0.05),
                L(wrist[0] - 0.10, wrist[1] - 0.10),
                L(wrist[0] - 0.15, wrist[1] - 0.15),
                L(wrist[0] - 0.20, wrist[1] - 0.20)]
    else:
        lms += [L(0, 0)] * 4
    # 5-8: index (MCP, PIP, DIP, TIP)
    if extended and num_fingers >= 1:
        lms += [L(wrist[0] + 0.00, wrist[1] - 0.05),  # MCP
                L(wrist[0] + 0.00, wrist[1] - 0.15),  # PIP
                L(wrist[0] + 0.00, wrist[1] - 0.25),  # DIP
                L(wrist[0] + 0.00, wrist[1] - 0.35)]  # TIP far from wrist
    else:
        lms += [L(wrist[0] + 0.00, wrist[1] - 0.05),  # MCP
                L(wrist[0] + 0.00, wrist[1] - 0.12),  # PIP (bent closer)
                L(wrist[0] + 0.00, wrist[1] - 0.13),  # DIP
                L(wrist[0] + 0.00, wrist[1] - 0.13)]  # TIP just past PIP (curled)
    # 9-12: middle
    if extended and num_fingers >= 2:
        lms += [L(wrist[0] + 0.05, wrist[1] - 0.05),
                L(wrist[0] + 0.05, wrist[1] - 0.15),
                L(wrist[0] + 0.05, wrist[1] - 0.25),
                L(wrist[0] + 0.05, wrist[1] - 0.35)]
    else:
        lms += [L(wrist[0] + 0.05, wrist[1] - 0.05),
                L(wrist[0] + 0.05, wrist[1] - 0.12),
                L(wrist[0] + 0.05, wrist[1] - 0.13),
                L(wrist[0] + 0.05, wrist[1] - 0.13)]
    # 13-16: ring
    if extended and num_fingers >= 3:
        lms += [L(wrist[0] + 0.10, wrist[1] - 0.05),
                L(wrist[0] + 0.10, wrist[1] - 0.15),
                L(wrist[0] + 0.10, wrist[1] - 0.25),
                L(wrist[0] + 0.10, wrist[1] - 0.35)]
    else:
        lms += [L(wrist[0] + 0.10, wrist[1] - 0.05),
                L(wrist[0] + 0.10, wrist[1] - 0.12),
                L(wrist[0] + 0.10, wrist[1] - 0.13),
                L(wrist[0] + 0.10, wrist[1] - 0.13)]
    # 17-20: pinky
    if extended and num_fingers >= 4:
        lms += [L(wrist[0] + 0.15, wrist[1] - 0.05),
                L(wrist[0] + 0.15, wrist[1] - 0.15),
                L(wrist[0] + 0.15, wrist[1] - 0.25),
                L(wrist[0] + 0.15, wrist[1] - 0.35)]
    else:
        lms += [L(wrist[0] + 0.15, wrist[1] - 0.05),
                L(wrist[0] + 0.15, wrist[1] - 0.12),
                L(wrist[0] + 0.15, wrist[1] - 0.13),
                L(wrist[0] + 0.15, wrist[1] - 0.13)]
    return lms


# Test 1: full open palm, 4 fingers extended
hand = make_hand(num_fingers=4, extended=True)
ok = m.HandProcessor.is_palm_open(hand)
print(f'Test 1 (4 fingers extended): {ok}  (expected True)')
assert ok, 'should detect open palm'

# Test 2: closed fist
hand = make_hand(num_fingers=0, extended=False)
ok = m.HandProcessor.is_palm_open(hand)
print(f'Test 2 (closed fist): {ok}  (expected False)')
assert not ok, 'should detect closed fist'

# Test 3: only 2 fingers extended -> not a palm
hand = make_hand(num_fingers=2, extended=True)
ok = m.HandProcessor.is_palm_open(hand)
print(f'Test 3 (only 2 fingers extended): {ok}  (expected False)')
assert not ok, 'should NOT detect 2-finger as open palm'

# Test 4: 3 fingers extended (the threshold) -> palm
hand = make_hand(num_fingers=3, extended=True)
ok = m.HandProcessor.is_palm_open(hand)
print(f'Test 4 (3 fingers extended): {ok}  (expected True)')
assert ok, 'should detect 3-finger partial palm'

# Test 5: empty/None input
assert not m.HandProcessor.is_palm_open(None), 'None should be False'
assert not m.HandProcessor.is_palm_open([]), 'empty list should be False'

# Test 6: Y-flipped hand (selfie camera mirror) -- should STILL detect palm
# In a mirrored camera, the y axis is inverted. The wrist-relative
# test (distance from wrist) is invariant to mirroring, so it should
# still work.
hand = make_hand(num_fingers=4, extended=True)
# Mirror y: y -> 1 - y
for lm in hand:
    lm.y = 1.0 - lm.y
ok = m.HandProcessor.is_palm_open(hand)
print(f'Test 6 (mirrored Y axis): {ok}  (expected True)')
assert ok, 'should detect palm even with Y mirrored (selfie camera)'

print('ALL is_palm_open TESTS PASSED')
