#!/usr/bin/env python3
"""Tests for the optional terminology checker."""

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

from check_terminology import TerminologyError, check_terminology  # noqa: E402


class CheckTerminologyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name) / "demo"
        (self.project / "svg_output").mkdir(parents=True)
        (self.project / "notes").mkdir()
        (self.project / "main_content.md").write_text(
            "Use Flow and XGU.\n", encoding="utf-8"
        )
        (self.project / "notes" / "total.md").write_text(
            "Flow should also be caught.\n", encoding="utf-8"
        )
        (self.project / "svg_output" / "01.svg").write_text(
            "<svg><text>XGU</text></svg>\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_missing_policy_is_a_successful_noop(self) -> None:
        result = check_terminology(self.project)

        self.assertEqual(result["status"], "not_configured")
        self.assertEqual(result["issue_count"], 0)

    def test_reports_every_occurrence_without_modifying_sources(self) -> None:
        policy = self.project / "terminology.json"
        policy.write_text(
            json.dumps({"forbidden": {"Flow": "工作流", "XGU": "XGUI"}}),
            encoding="utf-8",
        )

        result = check_terminology(self.project)

        self.assertEqual(result["status"], "issues")
        self.assertEqual(result["issue_count"], 4)
        self.assertEqual(
            {(issue["found"], issue["replacement"]) for issue in result["issues"]},
            {("Flow", "工作流"), ("XGU", "XGUI")},
        )
        self.assertEqual(
            (self.project / "main_content.md").read_text(encoding="utf-8"),
            "Use Flow and XGU.\n",
        )

    def test_invalid_policy_is_actionable(self) -> None:
        (self.project / "terminology.json").write_text(
            '{"forbidden":["Flow"]}', encoding="utf-8"
        )

        with self.assertRaisesRegex(TerminologyError, "must map"):
            check_terminology(self.project)

    def test_cli_uses_exit_two_for_policy_violations(self) -> None:
        (self.project / "terminology.json").write_text(
            json.dumps({"forbidden": {"Flow": "工作流"}}),
            encoding="utf-8",
        )

        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "check_terminology.py"),
                str(self.project),
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 2)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "issues")
        self.assertEqual(completed.stderr, "")


if __name__ == "__main__":
    unittest.main()
