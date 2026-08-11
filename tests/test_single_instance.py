"""Deterministic tests for the application single-instance lock."""

from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
import uuid
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tony_stark_hud_control.py"
SPEC = importlib.util.spec_from_file_location("tony_stark_hud_control", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SingleInstanceTests(unittest.TestCase):
    def test_second_acquire_fails_without_opening_interactive_ui(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            lock_path = os.path.join(temporary_directory, "instance.lock")
            mutex_name = f"Local\\TonyStarkHandControl_Test_{uuid.uuid4().hex}"
            first = MODULE._SingleInstance(lock_path=lock_path, mutex_name=mutex_name)
            second = MODULE._SingleInstance(lock_path=lock_path, mutex_name=mutex_name)
            third = MODULE._SingleInstance(lock_path=lock_path, mutex_name=mutex_name)
            surfaced: list[bool] = []
            second._surface_existing_window = lambda: surfaced.append(True)

            try:
                self.assertTrue(first.acquire())
                self.assertFalse(second.acquire())
                self.assertEqual(surfaced, [True])

                first.release()
                self.assertTrue(third.acquire())
            finally:
                second.release()
                third.release()
                first.release()


if __name__ == "__main__":
    unittest.main()
