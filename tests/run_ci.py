"""Run bounded repository checks in CI.

The legacy ``tests/test_app.py`` module is a manual live-integration script: it
opens real cameras, starts background workers, performs network-adjacent setup,
and constructs a Tk application at import time. Import-based test collection
must not execute it on hosted runners. Run that script directly on a suitable
GUI host with cameras when live validation is required.

The remaining historical ``test_*.py`` files mix three formats: unittest test
cases, pytest-style test functions, and executable assertion/benchmark scripts.
Classify each file from its syntax and invoke the matching runner so script-style
checks are not misreported as ``NO TESTS RAN``.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests"
LIVE_ONLY = {"test_app.py"}
PER_FILE_TIMEOUT_SECONDS = 120


def _is_testcase_base(base: ast.expr) -> bool:
    return isinstance(base, ast.Name) and base.id == "TestCase" or (
        isinstance(base, ast.Attribute) and base.attr == "TestCase"
    )


def _mode_for(test_file: Path) -> str:
    tree = ast.parse(test_file.read_text(encoding="utf-8"), filename=str(test_file))
    if any(
        isinstance(node, ast.ClassDef)
        and any(_is_testcase_base(base) for base in node.bases)
        for node in tree.body
    ):
        return "unittest"
    if any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
        for node in tree.body
    ):
        return "pytest"
    return "script"


def _command_for(test_file: Path, mode: str) -> list[str]:
    if mode == "script":
        return [sys.executable, "-u", str(test_file)]
    if mode == "pytest":
        return [sys.executable, "-u", "-m", "pytest", "-q", str(test_file)]
    return [
        sys.executable,
        "-u",
        "-m",
        "unittest",
        "discover",
        str(TESTS_DIR),
        "-p",
        test_file.name,
        "-v",
    ]


def main() -> int:
    test_files = sorted(TESTS_DIR.glob("test_*.py"))
    if not test_files:
        print("No test_*.py files found.", file=sys.stderr, flush=True)
        return 1

    for test_file in test_files:
        if test_file.name in LIVE_ONLY:
            print(
                f"SKIP {test_file.relative_to(ROOT)}: manual live camera/GUI integration script",
                flush=True,
            )
            continue

        relative_path = test_file.relative_to(ROOT)
        try:
            mode = _mode_for(test_file)
        except (OSError, SyntaxError) as exc:
            print(f"FAILED {relative_path}: cannot classify: {exc}", file=sys.stderr, flush=True)
            return 1

        print(f"\n=== {relative_path} ({mode}) ===", flush=True)
        try:
            completed = subprocess.run(
                _command_for(test_file, mode),
                cwd=ROOT,
                check=False,
                timeout=PER_FILE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            print(
                f"TIMEOUT {relative_path}: exceeded {PER_FILE_TIMEOUT_SECONDS} seconds",
                file=sys.stderr,
                flush=True,
            )
            return 1

        if completed.returncode != 0:
            print(
                f"FAILED {relative_path}: {mode} exited with {completed.returncode}",
                file=sys.stderr,
                flush=True,
            )
            return completed.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
