"""Tests for validated inputs to the offline single-file HTML builder."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_single_html import PackagingError, load_manifest, validate_slide_fragment


MANIFEST = {
    "schema_version": 1,
    "title": "Offline Demo",
    "lang": "zh-CN",
    "aspect_ratio": "16 / 9",
    "theme": {
        "name": "executive-red",
        "tokens": {
            "background": "#FFFFFF",
            "surface": "#F2F2F2",
            "primary": "#B50F0A",
            "on_primary": "#FFFFFF",
            "text": "#222222",
            "muted": "#666666",
            "line": "#D7D7D7",
        },
    },
    "slides": [
        {"id": "01", "title": "封面", "file": "slides/01_cover.html", "notes_key": "01"},
        {"id": "02", "title": "概览", "file": "slides/02_overview.html", "notes_key": "02"},
    ],
}


class ProjectFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project = Path(self.temp_dir.name)
        (self.project / "notes").mkdir()
        (self.project / "html_output" / "slides").mkdir(parents=True)
        (self.project / "design_spec.md").write_text("# Design", encoding="utf-8")
        (self.project / "notes" / "total.md").write_text("# Notes", encoding="utf-8")
        (self.project / "html_output" / "presentation.css").write_text("", encoding="utf-8")
        for slide in MANIFEST["slides"]:
            path = self.project / "html_output" / slide["file"]
            path.write_text(
                f'<section class="pm-slide" data-slide-id="{slide["id"]}"></section>',
                encoding="utf-8",
            )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_manifest(self, manifest: dict[str, object]) -> None:
        path = self.project / "html_output" / "presentation.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


class LoadManifestTests(ProjectFixture):
    def test_accepts_valid_manifest(self) -> None:
        self.write_manifest(MANIFEST)

        manifest = load_manifest(self.project)

        self.assertEqual(manifest["title"], "Offline Demo")

    def test_rejects_unsupported_schema_version(self) -> None:
        manifest = dict(MANIFEST, schema_version=2)
        self.write_manifest(manifest)

        with self.assertRaisesRegex(PackagingError, "schema_version"):
            load_manifest(self.project)

    def test_rejects_duplicate_slide_ids(self) -> None:
        manifest = dict(MANIFEST, slides=[*MANIFEST["slides"], dict(MANIFEST["slides"][0])])
        self.write_manifest(manifest)

        with self.assertRaisesRegex(PackagingError, "slides.*id"):
            load_manifest(self.project)

    def test_rejects_slide_path_outside_project(self) -> None:
        manifest = dict(MANIFEST)
        manifest["slides"] = [dict(MANIFEST["slides"][0], file="../../outside.html")]
        self.write_manifest(manifest)

        with self.assertRaisesRegex(PackagingError, "slides.*file"):
            load_manifest(self.project)


class ValidateSlideFragmentTests(unittest.TestCase):
    def test_accepts_one_matching_slide_root(self) -> None:
        source = Path("slides/01_cover.html")

        fragment = validate_slide_fragment(
            '<section class="pm-slide" data-slide-id="01"><h1>Title</h1></section>',
            "01",
            source,
        )

        self.assertEqual(
            fragment,
            '<section class="pm-slide" data-slide-id="01"><h1>Title</h1></section>',
        )

    def test_rejects_missing_or_nonmatching_slide_root(self) -> None:
        with self.assertRaisesRegex(PackagingError, "slide root"):
            validate_slide_fragment('<div class="pm-slide" data-slide-id="01"></div>', "01", Path("x"))

        with self.assertRaisesRegex(PackagingError, "data-slide-id"):
            validate_slide_fragment('<section class="pm-slide" data-slide-id="02"></section>', "01", Path("x"))

    def test_rejects_multiple_slide_roots(self) -> None:
        with self.assertRaisesRegex(PackagingError, "exactly one"):
            validate_slide_fragment(
                '<section class="pm-slide" data-slide-id="01"></section>'
                '<section class="pm-slide" data-slide-id="01"></section>',
                "01",
                Path("x"),
            )

    def test_rejects_a_slide_section_inside_a_wrapper(self) -> None:
        with self.assertRaisesRegex(PackagingError, "slide root"):
            validate_slide_fragment(
                '<div><section class="pm-slide" data-slide-id="01"></section></div>',
                "01",
                Path("x"),
            )

    def test_rejects_scripts(self) -> None:
        with self.assertRaisesRegex(PackagingError, "script"):
            validate_slide_fragment(
                '<section class="pm-slide" data-slide-id="01"><script>bad()</script></section>',
                "01",
                Path("x"),
            )


if __name__ == "__main__":
    unittest.main()
