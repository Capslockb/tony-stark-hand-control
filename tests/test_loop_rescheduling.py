"""Deterministic regression coverage for Issue #16.

This module inspects the application source instead of importing it, so the
check stays independent of cameras, MediaPipe workers, Tk displays, and host
GUI configuration.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


SOURCE_PATH = Path(__file__).resolve().parents[1] / "tony_stark_hud_control.py"


def _load_class() -> tuple[str, ast.ClassDef]:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SOURCE_PATH))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "HandControlApp":
            return source, node
    raise AssertionError("HandControlApp was not found in the application source")


def _method(class_node: ast.ClassDef, name: str) -> ast.FunctionDef:
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"HandControlApp.{name} was not found")


def _is_self_attribute(node: ast.AST, *attrs: str) -> bool:
    current = node
    for attr in reversed(attrs):
        if not isinstance(current, ast.Attribute) or current.attr != attr:
            return False
        current = current.value
    return isinstance(current, ast.Name) and current.id == "self"


def _schedules_next_loop(method: ast.FunctionDef) -> bool:
    for node in ast.walk(method):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Call):
            continue
        if not _is_self_attribute(value.func, "root", "after"):
            continue
        if len(value.args) < 2 or not _is_self_attribute(value.args[1], "loop"):
            continue

        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(_is_self_attribute(target, "loop_id") for target in targets):
            return True
    return False


class LoopReschedulingOwnershipTests(unittest.TestCase):
    def test_loop_schedules_the_next_iteration(self) -> None:
        source, class_node = _load_class()
        loop = _method(class_node, "loop")
        loop_source = ast.get_source_segment(source, loop) or ""

        self.assertTrue(
            _schedules_next_loop(loop),
            "HandControlApp.loop must assign self.loop_id from "
            "self.root.after(wait_ms, self.loop)",
        )
        self.assertIn(
            "max(15.0, min(60.0, target_fps))",
            loop_source,
            "The existing 15–60 FPS pacing clamp must remain in loop()",
        )
        self.assertIn(
            "if wait_ms < 1:",
            loop_source,
            "loop() must preserve the minimum 1 ms Tk scheduling delay",
        )

    def test_redraw_canvas_is_render_only(self) -> None:
        _, class_node = _load_class()
        redraw = _method(class_node, "_redraw_canvas")

        loaded_names = {
            node.id
            for node in ast.walk(redraw)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        self.assertTrue(
            {"live_fps", "loop_t0"}.isdisjoint(loaded_names),
            "_redraw_canvas must not reference loop()-owned pacing locals",
        )
        self.assertFalse(
            _schedules_next_loop(redraw),
            "_redraw_canvas must not schedule the application processing loop",
        )


if __name__ == "__main__":
    unittest.main()
