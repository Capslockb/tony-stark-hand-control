import re
import unittest
from pathlib import Path


REQUIREMENTS_PATH = Path(__file__).resolve().parents[1] / "requirements.txt"
REQUIREMENT_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)(?P<specifier>[^;]*?)(?:;\s*(?P<marker>.+))?$"
)


def _requirements_named(name: str) -> list[tuple[str, str | None]]:
    matches: list[tuple[str, str | None]] = []
    for raw_line in REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines():
        requirement = raw_line.split("#", 1)[0].strip()
        if not requirement:
            continue

        match = REQUIREMENT_RE.fullmatch(requirement)
        if match and match.group("name").casefold() == name.casefold():
            matches.append((match.group("specifier").replace(" ", ""), match.group("marker")))
    return matches


class RuntimeDependencyContractTests(unittest.TestCase):
    def test_requests_is_declared_once(self) -> None:
        self.assertEqual(_requirements_named("requests"), [(">=2.32,<3.0", None)])

    def test_winshell_uses_one_valid_windows_only_range(self) -> None:
        winshell_requirements = _requirements_named("winshell")
        self.assertEqual(len(winshell_requirements), 1)

        specifier, marker = winshell_requirements[0]
        self.assertEqual(specifier, ">=0.6,<0.7")
        self.assertIsNotNone(marker)
        normalized_marker = marker.replace(" ", "").replace("'", '"').casefold()
        self.assertEqual(normalized_marker, 'sys_platform=="win32"')
