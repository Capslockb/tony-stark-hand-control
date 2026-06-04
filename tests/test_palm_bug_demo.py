"""Demonstrate the OLD is_palm_open bug: it returns wrong answer for
mirrored Y axis (selfie cameras)."""
import importlib.util
spec = importlib.util.spec_from_file_location(
    'm', r'C:/Users/Bernardo/tony_stark_hand_control/tony_stark_hud_control.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def old_is_palm_open(landmarks):
    """The original Y-flip implementation."""
    if not landmarks:
        return False
    fingers = []
    for tip, pip in [(8, 6), (12, 10), (16, 14), (20, 18)]:
        fingers.append(landmarks[tip].y < landmarks[pip].y)
    return sum(fingers) >= 3


class L:
    __slots__ = ('x', 'y', 'z')
    def __init__(self, x, y, z=0):
        self.x, self.y, self.z = x, y, z


def make_normal_palm(wrist=(0.5, 0.9, 0)):
    lms = [L(*wrist)]
    for j in range(4):
        lms.append(L(wrist[0] - 0.05 - j*0.05, wrist[1] - 0.05 - j*0.05))
    for j in range(4):
        lms.append(L(wrist[0] + 0.00, wrist[1] - 0.05 - j*0.10))  # tips at 0.35
    for j in range(4):
        lms.append(L(wrist[0] + 0.05, wrist[1] - 0.05 - j*0.10))
    for j in range(4):
        lms.append(L(wrist[0] + 0.10, wrist[1] - 0.05 - j*0.10))
    for j in range(4):
        lms.append(L(wrist[0] + 0.15, wrist[1] - 0.05 - j*0.10))
    return lms


hand = make_normal_palm()
print(f'Normal:    old={old_is_palm_open(hand)}  new={m.HandProcessor.is_palm_open(hand)}')

mirrored = [L(lm.x, 1.0 - lm.y, lm.z) for lm in hand]
print(f'Mirrored:  old={old_is_palm_open(mirrored)}  new={m.HandProcessor.is_palm_open(mirrored)}')

print('---')
print('Bug: the OLD code returns False for a mirrored (selfie) palm, even')
print('though the user has an open palm. The NEW code returns True correctly.')
