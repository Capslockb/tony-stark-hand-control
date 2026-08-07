import ast
import re
import unittest
from pathlib import Path


APP_PATH = Path(__file__).parents[1] / "tony_stark_hud_control.py"
APP_SOURCE = APP_PATH.read_text(encoding="utf-8")
APP_TREE = ast.parse(APP_SOURCE)


def _function_source(class_name: str, function_name: str) -> str:
    for node in APP_TREE.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == function_name:
                    return ast.get_source_segment(APP_SOURCE, child) or ""
    raise AssertionError(f"{class_name}.{function_name} not found")


class OllamaSecurityContractTests(unittest.TestCase):
    def test_api_key_field_has_no_embedded_default(self):
        match = re.search(
            r"self\.ollama_key_var\s*=\s*tk\.StringVar\(\s*value=(?P<quote>['\"])(?P<value>.*?)(?P=quote)\s*\)",
            APP_SOURCE,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match, "Ollama API-key field definition not found")
        self.assertFalse(
            bool(match.group("value")),
            "The public application must not ship with a credential-like API-key default.",
        )

    def test_empty_key_is_allowed_for_local_endpoints(self):
        save_source = _function_source("HandControlApp", "_save_ollama_settings")
        self.assertNotIn(
            "Endpoint, model, and API key are all required.",
            save_source,
            "Local Ollama-compatible endpoints that do not require authentication must be usable with an empty key.",
        )
        self.assertIsNone(
            re.search(r"not\s*\(\s*endpoint\s+and\s+model\s+and\s+key\s*\)", save_source),
            "Saving Ollama settings must not reject an otherwise valid endpoint/model solely because the key is empty.",
        )

    def test_authorization_header_is_conditional(self):
        worker_source = _function_source("OllamaGestureRecognizer", "_worker")
        self.assertNotIn(
            'headers={"Authorization": f"Bearer {self.api_key}"}',
            worker_source,
            "Do not send an empty Bearer header to local endpoints; add Authorization only when a key is present.",
        )
        self.assertRegex(
            worker_source,
            r"if\s+(?:self\.)?api_key|if\s+self\.api_key",
            "The request path should explicitly condition Authorization on a non-empty API key.",
        )


if __name__ == "__main__":
    unittest.main()
