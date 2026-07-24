#!/usr/bin/env python3
"""Unit tests for the single-file HTML browser-QA wrapper."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from qa_single_html import QAError, resolve_node_runtime, run_browser_qa  # noqa: E402


class QASingleHtmlTests(unittest.TestCase):
    def test_explicit_runtime_is_preferred(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            node = root / "node"
            modules = root / "node_modules"
            node.write_text("#!/bin/sh\n", encoding="utf-8")
            modules.mkdir()
            with patch("qa_single_html._has_playwright", return_value=True):
                resolved_node, resolved_modules = resolve_node_runtime(node, modules)

        self.assertEqual(resolved_node, node.resolve())
        self.assertEqual(resolved_modules, modules.resolve())

    def test_missing_html_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "missing"
            project.mkdir()
            with self.assertRaisesRegex(QAError, "Run build_single_html.py"):
                run_browser_qa(project)

    def test_cli_json_error_is_one_object(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "missing"
            project.mkdir()
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "qa_single_html.py"),
                    str(project),
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertIn("Run build_single_html.py", payload["error"])
        self.assertEqual(completed.stderr, "")

    def test_cli_help_has_copyable_examples(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "qa_single_html.py"), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("qa_single_html.py projects/quarterly-review --json", completed.stdout)
        self.assertIn("--screenshots /tmp/quarterly-qa --json", completed.stdout)


if __name__ == "__main__":
    unittest.main()
