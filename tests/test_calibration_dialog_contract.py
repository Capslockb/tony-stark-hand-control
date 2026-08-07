import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "tony_stark_hud_control.py"


def _start_calibration_text() -> str:
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"), filename=str(APP_PATH))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "HandControlApp":
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "start_calibration":
                    return "\n".join(
                        constant.value
                        for constant in ast.walk(item)
                        if isinstance(constant, ast.Constant) and isinstance(constant.value, str)
                    )
    raise AssertionError("HandControlApp.start_calibration was not found")


class CalibrationDialogContractTests(unittest.TestCase):
    def test_dialog_does_not_promise_a_bundled_desktop_pdf(self) -> None:
        text = _start_calibration_text().lower()
        self.assertNotIn("a4 pdf", text)
        self.assertNotIn("desktop", text)

    def test_dialog_points_to_canonical_calibration_guidance(self) -> None:
        text = _start_calibration_text().lower()
        self.assertIn("docs/calibration.md", text)

    def test_dialog_preserves_checkerboard_requirements(self) -> None:
        text = _start_calibration_text().lower()
        self.assertIn("9x6", text)
        self.assertIn("25", text)


if __name__ == "__main__":
    unittest.main()
