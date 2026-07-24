#!/usr/bin/env python3
"""Integration tests for single-file HTML scaffold and export freshness."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_single_html import PackagingError, build_single_html, check_single_html  # noqa: E402
from prepare_single_html import prepare_single_html  # noqa: E402


class SingleHtmlFreshnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name) / "demo"
        (self.project / "svg_output").mkdir(parents=True)
        (self.project / "notes").mkdir()
        (self.project / "svg_output" / "01_cover.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            "<text>Original</text></svg>",
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
        (self.project / "design_spec.md").write_text(
            "# Design\n- Deliverable Mode: Single-file HTML Presentation\n",
            encoding="utf-8",
        )
        (self.project / "notes" / "total.md").write_text(
            "# 01 Cover\nOpening notes\n",
            encoding="utf-8",
        )
        prepare_single_html(self.project)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_check_reports_current_after_build(self) -> None:
        first = check_single_html(self.project)
        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["source_state"], "current")
        self.assertEqual(first["export_state"], "missing")
        self.assertTrue(first["needs_build"])

        build_single_html(self.project)
        current = check_single_html(self.project)

        self.assertEqual(current["status"], "ok")
        self.assertEqual(current["source_state"], "current")
        self.assertEqual(current["export_state"], "current")
        self.assertFalse(current["needs_build"])

    def test_svg_change_marks_source_and_export_stale_and_blocks_build(self) -> None:
        build_single_html(self.project)
        source = self.project / "svg_output" / "01_cover.svg"
        source.write_text(
            source.read_text(encoding="utf-8").replace("Original", "Changed"),
            encoding="utf-8",
        )

        stale = check_single_html(self.project)

        self.assertEqual(stale["status"], "stale")
        self.assertEqual(stale["source_state"], "stale")
        self.assertEqual(stale["stale_slides"], ["01"])
        with self.assertRaisesRegex(PackagingError, "--refresh-changed"):
            build_single_html(self.project)

        prepare_single_html(self.project, refresh_changed=True)
        refreshed = check_single_html(self.project)
        self.assertEqual(refreshed["source_state"], "current")
        self.assertEqual(refreshed["export_state"], "stale")
        build_single_html(self.project)
        self.assertEqual(check_single_html(self.project)["export_state"], "current")

    def test_custom_fragment_plus_svg_change_is_reported_as_conflict(self) -> None:
        fragment = self.project / "html_output" / "slides" / "01_cover.html"
        fragment.write_text(
            fragment.read_text(encoding="utf-8").replace(
                "</section>", "<p>Custom</p></section>"
            ),
            encoding="utf-8",
        )
        source = self.project / "svg_output" / "01_cover.svg"
        source.write_text(
            source.read_text(encoding="utf-8").replace("Original", "Changed"),
            encoding="utf-8",
        )

        freshness = check_single_html(self.project)

        self.assertEqual(freshness["source_state"], "conflict")
        self.assertEqual(freshness["conflicted_slides"], ["01"])

    def test_notes_change_marks_only_export_stale(self) -> None:
        build_single_html(self.project)
        notes = self.project / "notes" / "total.md"
        notes.write_text("# 01 Cover\nUpdated notes\n", encoding="utf-8")

        freshness = check_single_html(self.project)

        self.assertEqual(freshness["status"], "stale")
        self.assertEqual(freshness["source_state"], "current")
        self.assertEqual(freshness["export_state"], "stale")
        rebuilt = build_single_html(self.project)
        self.assertEqual(rebuilt["export_state"], "current")

    def test_design_spec_change_marks_scaffold_stale(self) -> None:
        build_single_html(self.project)
        design = self.project / "design_spec.md"
        design.write_text(design.read_text(encoding="utf-8") + "\nNew rule\n", encoding="utf-8")

        freshness = check_single_html(self.project)

        self.assertEqual(freshness["source_state"], "stale")
        self.assertEqual(freshness["stale_inputs"], ["design_spec.md"])


if __name__ == "__main__":
    unittest.main()
