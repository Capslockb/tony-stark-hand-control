import ast
from pathlib import Path
import re
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
        if "a4 pdf" in text:
            self.fail("Calibration dialog still promises a bundled A4 PDF")
        if "desktop" in text:
            self.fail("Calibration dialog still promises a Desktop-created file")

    def test_dialog_points_to_canonical_calibration_guidance(self) -> None:
        text = _start_calibration_text().lower()
        if "docs/calibration.md" not in text:
            self.fail("Calibration dialog must point users to docs/calibration.md")

    def test_dialog_preserves_checkerboard_requirements(self) -> None:
        text = _start_calibration_text().lower()
        if "9x6" not in text:
            self.fail("Calibration dialog must preserve the 9x6 pattern requirement")
        if re.search(r"\b25\s*mm\b", text) is None:
            self.fail("Calibration dialog must require the calibrator's fixed 25 mm square size")
        if re.search(r"\b25\s*-\s*30\s*mm\b", text) is not None:
            self.fail("Calibration dialog must not advertise a 25-30 mm range while calibration is fixed to 25 mm")


if __name__ == "__main__":
    unittest.main()
