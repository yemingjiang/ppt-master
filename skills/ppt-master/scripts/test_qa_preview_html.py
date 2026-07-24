#!/usr/bin/env python3
"""Unit tests for the skeleton-preview browser-QA wrapper."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from qa_preview_html import QAError, _parse_slide_keys, run_preview_qa  # noqa: E402


class QAPreviewHtmlTests(unittest.TestCase):
    def test_slide_keys_are_normalized_and_deduplicated(self) -> None:
        self.assertEqual(_parse_slide_keys("6, 15,06,19"), ["06", "15", "19"])

    def test_invalid_slide_key_is_actionable(self) -> None:
        with self.assertRaisesRegex(QAError, "comma-separated numbers"):
            _parse_slide_keys("06,title")

    def test_missing_preview_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "missing"
            project.mkdir()
            with self.assertRaisesRegex(QAError, "Run build_preview_html.py"):
                run_preview_qa(project)

    def test_cli_json_error_is_one_object(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "missing"
            project.mkdir()
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "qa_preview_html.py"),
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
        self.assertIn("Run build_preview_html.py", payload["error"])
        self.assertEqual(completed.stderr, "")

    def test_cli_help_has_copyable_examples(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "qa_preview_html.py"), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--slides 06,15,19", completed.stdout)
        self.assertIn("--screenshots /tmp/preview-qa --json", completed.stdout)


if __name__ == "__main__":
    unittest.main()
