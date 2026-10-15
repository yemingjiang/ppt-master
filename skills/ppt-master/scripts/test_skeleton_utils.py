#!/usr/bin/env python3
"""Regression tests for slide keys and design-spec/style-sheet handoff."""

from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from skeleton_utils import build_style_sheet_markdown, parse_design_spec, slide_key, slide_sort_key  # noqa: E402


class SlideKeyTests(unittest.TestCase):
    def test_bare_numeric_prefix(self) -> None:
        self.assertEqual(slide_key("01_intro"), "01")
        self.assertEqual(slide_key("1_intro"), "01")
        self.assertEqual(slide_key("12_summary"), "12")

    def test_slide_underscore_convention(self) -> None:
        # Blessed by validate_project_structure: slide_\d+_\w+
        self.assertEqual(slide_key("slide_01_intro"), "01")
        self.assertEqual(slide_key("slide_7_overview"), "07")

    def test_p_prefix_convention(self) -> None:
        # Blessed by validate_project_structure: P?\d+_.+
        self.assertEqual(slide_key("P1_intro"), "01")
        self.assertEqual(slide_key("P10_appendix"), "10")

    def test_no_number_falls_back_to_stem(self) -> None:
        self.assertEqual(slide_key("封面"), "封面")
        self.assertEqual(slide_key("cover"), "cover")

    def test_notes_heading_forms(self) -> None:
        # Notes headings may use a space or no separator before CJK title text
        self.assertEqual(slide_key("01 封面"), "01")
        self.assertEqual(slide_key("01封面"), "01")

    def test_no_false_positive_on_leading_p_word(self) -> None:
        # "Plan1" / "Performance" must not be parsed as a P-prefixed slide
        self.assertEqual(slide_key("Performance_2024"), "Performance_2024")
        self.assertEqual(slide_key("Plan1_overview"), "Plan1_overview")


class SlideSortKeyTests(unittest.TestCase):
    def test_all_conventions_sort_numerically(self) -> None:
        files = [
            Path("P10_appendix.svg"),
            Path("P2_body.svg"),
            Path("P1_intro.svg"),
        ]
        ordered = sorted(files, key=slide_sort_key)
        self.assertEqual(
            [p.name for p in ordered],
            ["P1_intro.svg", "P2_body.svg", "P10_appendix.svg"],
        )

    def test_slide_underscore_sorts_numerically(self) -> None:
        files = [
            Path("slide_10_end.svg"),
            Path("slide_2_mid.svg"),
            Path("slide_1_start.svg"),
        ]
        ordered = sorted(files, key=slide_sort_key)
        self.assertEqual(
            [p.name for p in ordered],
            ["slide_1_start.svg", "slide_2_mid.svg", "slide_10_end.svg"],
        )


class StyleSheetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.project_path = Path(self.workspace.name)
        self.template = (SCRIPT_DIR.parent / "templates" / "design_spec_reference.md").read_text(encoding="utf-8")

    def build_spec(self, baseline: int, *, language: str = "en", override: str = "") -> dict:
        text = self.template.replace("{project_name}", "样式检查" if language == "zh" else "Style check")
        text = text.replace("Body font size = [fill in]px", f"Body font size = {baseline}px")
        minimum = {18: 14, 24: 18, 32: 20}[baseline]
        text = text.replace("**Minimum font size**: [fill in]px", f"**Minimum font size**: {minimum}px")
        text = text.replace("[Fill in CSS font-family string]", "Arial, sans-serif")
        text = text.replace(
            "[Live projection / remote screen share / self-paced reading; include relevant viewing constraints]",
            "Remote screen share",
        )
        text = text.replace("[Cross-page data/category/status mappings; roles may share colors]", "Revenue = blue; costs = orange")
        text = text.replace("[Specify role-based line-height or baseline spacing, especially titles and quotes]", "Title line-height 1.1; body 1.35")
        text = text.replace(
            "[Use cards, shadows, gradients, or glow only for a stated purpose; flat layouts are valid]",
            "Flat layout; highlight only the key comparison",
        )
        text = text.replace(
            "[Policy: none / page number / required branding or compliance; reserve space only when used. Live slides can omit persistent chrome; report reviews may benefit from numbering. Visible citations only when requested/required.]",
            "None; keep page numbers in review navigation only",
        )
        if override:
            row = next(line for line in text.splitlines() if line.startswith("| Content title |"))
            text = text.replace(row, row.replace("[Optional override]", override))
        (self.project_path / "design_spec.md").write_text(text, encoding="utf-8")
        return parse_design_spec(self.project_path)

    def test_selected_baseline_reaches_style_sheet_in_both_languages(self) -> None:
        for language in ("en", "zh"):
            for baseline, expected_title in ((18, "27-36px"), (24, "36-48px"), (32, "48-64px")):
                with self.subTest(language=language, baseline=baseline):
                    spec = self.build_spec(baseline, language=language)
                    self.assertEqual(spec["body_baseline_px"], baseline)
                    output = build_style_sheet_markdown(spec)
                    title = next(line for line in output.splitlines() if "`Content title`" in line)
                    body = next(line for line in output.splitlines() if "`Body content`" in line)
                    self.assertIn(f"`{expected_title}`", title)
                    self.assertIn(f"`{baseline}px`", body)

    def test_authored_size_override_takes_precedence(self) -> None:
        for baseline in (24, 32):
            with self.subTest(baseline=baseline):
                output = build_style_sheet_markdown(self.build_spec(baseline, override="44px"))
                title = next(line for line in output.splitlines() if "`Content title`" in line)
                self.assertIn("`44px`", title)

    def test_style_choices_survive_handoff_in_both_languages(self) -> None:
        for language in ("en", "zh"):
            with self.subTest(language=language):
                spec = self.build_spec(32, language=language)
                self.assertEqual(spec["minimum_font_px"], 20)
                output = build_style_sheet_markdown(spec)
                for value in (
                    "Remote screen share",
                    "Revenue = blue; costs = orange",
                    "Title line-height 1.1; body 1.35",
                    "Arial, sans-serif",
                    "Flat layout; highlight only the key comparison",
                    "None; keep page numbers in review navigation only",
                ):
                    self.assertIn(value, output)
                minimum_line = next(line for line in output.splitlines() if "Minimum font size" in line or "最小字体" in line)
                self.assertIn("`20`", minimum_line)

    def test_legacy_spec_without_new_fields_still_builds(self) -> None:
        text = """# Legacy design
## I. Project Information
| Item | Value |
| ---- | ----- |
| Project Name | Legacy |
## IV. Typography System
### Font Plan
| Role | Chinese | English | Fallback |
| ---- | ------- | ------- | -------- |
| Body | | Arial | sans-serif |
### Font Size Hierarchy
Baseline: Body font size = 24px
| Purpose | Ratio | 24px baseline (relaxed) | 18px baseline (dense) | Weight |
| ------- | ----- | ---------------------- | -------------------- | ------ |
| Content title | 1.5-2x | 36-48px | 27-36px | Bold |
| Body content | 1x | 24px | 18px | Regular |
"""
        (self.project_path / "design_spec.md").write_text(text, encoding="utf-8")
        spec = parse_design_spec(self.project_path)
        output = build_style_sheet_markdown(spec)
        self.assertIn("`36-48px`", output)
        self.assertIn("`Body content`: `24px`", output)
        self.assertIsNone(spec["minimum_font_px"])


if __name__ == "__main__":
    unittest.main()
