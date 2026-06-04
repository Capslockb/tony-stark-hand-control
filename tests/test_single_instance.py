"""Test the _SingleInstance lock by acquiring it twice in a row.
The second acquire() should return False (already running)."""
import os, sys, time
import importlib.util
spec = importlib.util.spec_from_file_location(
    'm', r'C:/Users/Bernardo/tony_stark_hand_control/tony_stark_hud_control.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

print('=== Test 1: first acquire should succeed ===')
inst1 = m._SingleInstance()
ok1 = inst1.acquire()
print(f'  first acquire: {ok1}')
assert ok1, 'first acquire should return True'
# Get the second instance. It should fail to acquire.
print('=== Test 2: second acquire should fail (already running) ===')
inst2 = m._SingleInstance()
ok2 = inst2.acquire()
print(f'  second acquire: {ok2}')
assert not ok2, 'second acquire should return False'
# Release the first, third should succeed
print('=== Test 3: after release, third acquire should succeed ===')
inst1.release()
inst3 = m._SingleInstance()
ok3 = inst3.acquire()
print(f'  third acquire: {ok3}')
assert ok3, 'third acquire (after first release) should return True'
inst3.release()
print('\nAll single-instance tests PASSED.')
