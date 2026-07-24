#!/usr/bin/env python3
"""Regression tests for prepare_single_html."""

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

from prepare_single_html import PreparationError, prepare_single_html  # noqa: E402


class PrepareSingleHtmlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name) / "demo"
        (self.project / "svg_output").mkdir(parents=True)
        (self.project / "images").mkdir()
        (self.project / "images" / "hero.png").write_bytes(b"\x89PNG\r\n\x1a\nhero")
        (self.project / "main_content.md").write_text(
            """# Demo Deck 主内容

## Slides

### Slide 01 - Cover
- Title: 封面标题
- Takeaway: 开场
- Bullets:
  - None
- Assets:
  - None
- Review Notes:
  - None

### Slide 02 - Result
- Title: 结果页
- Takeaway: 结果
- Bullets:
  - None
- Assets:
  - None
- Review Notes:
  - None
""",
            encoding="utf-8",
        )
        (self.project / "svg_output" / "01_cover.svg").write_text(
            """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <defs><linearGradient id="hero"><stop offset="0%" stop-color="#fff"/></linearGradient></defs>
  <rect id="card" width="1280" height="720" fill="url(#hero)"/>
  <image href="../images/hero.png" width="10" height="10"/>
</svg>
""",
            encoding="utf-8",
        )
        (self.project / "svg_output" / "02_result.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720"><text id="title">Result</text></svg>',
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_prepares_manifest_and_prefixed_fragments(self) -> None:
        result = prepare_single_html(self.project)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["slides"], 2)
        manifest = json.loads(
            (self.project / "html_output" / "presentation.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["lang"], "zh-CN")
        self.assertEqual(manifest["aspect_ratio"], "16 / 9")
        self.assertEqual([slide["id"] for slide in manifest["slides"]], ["01", "02"])
        self.assertNotIn("notes_key", manifest["slides"][0])
        first = (
            self.project / "html_output" / "slides" / "01_cover.html"
        ).read_text(encoding="utf-8")
        self.assertIn('data-slide-id="01"', first)
        self.assertIn('aria-label="封面标题"', first)
        self.assertIn('class="pm-artwork"', first)
        self.assertIn('id="s01-hero"', first)
        self.assertIn('fill="url(#s01-hero)"', first)
        self.assertIn('href="../../images/hero.png"', first)

    def test_retry_is_idempotent_without_force(self) -> None:
        prepare_single_html(self.project)
        result = prepare_single_html(self.project)

        self.assertEqual(result["created"], [])
        self.assertEqual(result["updated"], [])
        self.assertGreaterEqual(len(result["unchanged"]), 4)

    def test_refuses_to_overwrite_different_existing_source(self) -> None:
        prepare_single_html(self.project)
        target = self.project / "html_output" / "slides" / "01_cover.html"
        target.write_text("manual edit", encoding="utf-8")

        with self.assertRaisesRegex(PreparationError, "--force"):
            prepare_single_html(self.project)

        self.assertEqual(target.read_text(encoding="utf-8"), "manual edit")

    def test_dry_run_reports_conflicts_without_writing(self) -> None:
        (self.project / "html_output").mkdir()
        target = self.project / "html_output" / "presentation.json"
        target.write_text('{"manual": true}\n', encoding="utf-8")

        result = prepare_single_html(self.project, dry_run=True)

        self.assertEqual(result["status"], "planned")
        self.assertIn("html_output/presentation.json", result["would_overwrite"])
        self.assertEqual(target.read_text(encoding="utf-8"), '{"manual": true}\n')
        self.assertFalse((self.project / "html_output" / "slides").exists())

    def test_force_replaces_only_planned_targets(self) -> None:
        prepare_single_html(self.project)
        target = self.project / "html_output" / "slides" / "01_cover.html"
        extra = self.project / "html_output" / "slides" / "custom.html"
        target.write_text("manual edit", encoding="utf-8")
        extra.write_text("keep", encoding="utf-8")

        result = prepare_single_html(self.project, force=True)

        self.assertIn("html_output/slides/01_cover.html", result["updated"])
        self.assertEqual(extra.read_text(encoding="utf-8"), "keep")

    def test_preserves_existing_slide_filenames_and_deck_settings(self) -> None:
        prepare_single_html(self.project)
        manifest_path = self.project / "html_output" / "presentation.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["title"] = "Custom title"
        manifest["slides"][0]["file"] = "slides/01_custom.html"
        original = self.project / "html_output" / "slides" / "01_cover.html"
        custom = self.project / "html_output" / "slides" / "01_custom.html"
        original.replace(custom)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        result = prepare_single_html(self.project)

        refreshed = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(refreshed["title"], "Custom title")
        self.assertEqual(refreshed["slides"][0]["file"], "slides/01_custom.html")
        self.assertIn("html_output/slides/01_custom.html", result["unchanged"])

    def test_rejects_remote_svg_resources(self) -> None:
        (self.project / "svg_output" / "01_cover.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.test/x.png"/></svg>',
            encoding="utf-8",
        )

        with self.assertRaisesRegex(PreparationError, "project-local"):
            prepare_single_html(self.project)

    def test_cli_json_dry_run_is_machine_readable(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "prepare_single_html.py"),
                str(self.project),
                "--dry-run",
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "planned")
        self.assertEqual(payload["slides"], 2)


if __name__ == "__main__":
    unittest.main()
