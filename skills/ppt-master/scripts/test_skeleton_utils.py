#!/usr/bin/env python3
"""Regression tests for skeleton_utils slide-key helpers."""

from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from skeleton_utils import slide_key, slide_sort_key  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
