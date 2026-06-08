#!/usr/bin/env python3
"""Regression tests for ConvertContext transform composition."""

from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from svg_to_pptx.drawingml_context import ConvertContext  # noqa: E402
from svg_to_pptx.drawingml_utils import ctx_x, ctx_y  # noqa: E402


class TransformCompositionTests(unittest.TestCase):
    def test_scale_then_translate_composes_as_matrix(self) -> None:
        """A translate inside a scaled group must be expressed in the
        already-scaled parent space: scale(2) > translate(10) > x=5 -> 30."""
        root = ConvertContext()
        scaled = root.child(sx=2, sy=2)
        translated = scaled.child(dx=10, dy=10)
        self.assertEqual(ctx_x(5, translated), 30.0)
        self.assertEqual(ctx_y(5, translated), 30.0)

    def test_translate_then_scale(self) -> None:
        """translate(100) > scale(2) > x=5 -> 100 + 2*5 = 110."""
        root = ConvertContext()
        translated = root.child(dx=100, dy=100)
        scaled = translated.child(sx=2, sy=2)
        self.assertEqual(ctx_x(5, scaled), 110.0)
        self.assertEqual(ctx_y(5, scaled), 110.0)

    def test_nested_scales_multiply(self) -> None:
        root = ConvertContext()
        a = root.child(sx=2, sy=3)
        b = a.child(sx=2, sy=2)
        self.assertEqual(b.scale_x, 4.0)
        self.assertEqual(b.scale_y, 6.0)

    def test_pure_translate_chain_adds(self) -> None:
        root = ConvertContext()
        a = root.child(dx=10, dy=20)
        b = a.child(dx=5, dy=5)
        self.assertEqual(ctx_x(0, b), 15.0)
        self.assertEqual(ctx_y(0, b), 25.0)

    def test_three_level_scale_translate_scale(self) -> None:
        """scale(2) > translate(10) > scale(3) > x=4
        = 2*(10 + 3*4) = 2*22 = 44."""
        root = ConvertContext()
        s1 = root.child(sx=2, sy=2)
        t = s1.child(dx=10, dy=10)
        s2 = t.child(sx=3, sy=3)
        self.assertEqual(ctx_x(4, s2), 44.0)


if __name__ == "__main__":
    unittest.main()
