#!/usr/bin/env python3
"""Tests for the safe single-file HTML finalization orchestrator."""

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

from finalize_single_html import FinalizationError, finalize_single_html  # noqa: E402


class FinalizeSingleHtmlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name) / "demo"
        (self.project / "svg_output").mkdir(parents=True)
        (self.project / "notes").mkdir()
        (self.project / "svg_output" / "01_cover.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            "<text>Demo</text></svg>",
            encoding="utf-8",
        )
        (self.project / "main_content.md").write_text(
            """# Demo

## Slides

### Slide 01 - Cover
- Title: Cover
- Takeaway: Opening
- Bullets:
  - None
- Assets:
  - None
- Review Notes:
  - None
""",
            encoding="utf-8",
        )
        (self.project / "notes" / "total.md").write_text(
            "# 01 Cover\nOpening notes\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_dry_run_does_not_create_html_sources(self) -> None:
        result = finalize_single_html(self.project, dry_run=True)

        self.assertEqual(result["status"], "planned")
        self.assertFalse((self.project / "html_output").exists())
        self.assertFalse((self.project / "exports").exists())
        self.assertTrue(result["would_run_browser_qa"])

    def test_pipeline_forwards_explicit_media_approval_and_runs_qa(self) -> None:
        fake_qa = {
            "status": "ok",
            "slides": 1,
            "contact_sheets": [],
            "checks": {"offline": True},
        }
        with (
            patch("finalize_single_html.analyze_project") as analyze,
            patch("finalize_single_html.run_browser_qa", return_value=fake_qa) as qa,
        ):
            analyze.return_value = {
                "status": "ok",
                "summary": {"gif_count": 0},
            }
            result = finalize_single_html(self.project, apply_media=True)

        self.assertEqual(result["status"], "ok")
        self.assertTrue(analyze.call_args.kwargs["apply"])
        self.assertTrue(Path(result["build"]["output_html"]).exists())
        qa.assert_called_once()

    def test_terminology_issues_block_all_writes(self) -> None:
        (self.project / "terminology.json").write_text(
            json.dumps({"forbidden": {"Demo": "演示"}}), encoding="utf-8"
        )

        with self.assertRaisesRegex(FinalizationError, "terminology policy"):
            finalize_single_html(self.project)

        self.assertFalse((self.project / "html_output").exists())

    def test_cli_help_documents_safe_and_approved_paths(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "finalize_single_html.py"), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--dry-run --json", completed.stdout)
        self.assertIn("--apply-media --browser chrome --json", completed.stdout)
        self.assertIn("--force-scaffold --apply-media --json", completed.stdout)


if __name__ == "__main__":
    unittest.main()
