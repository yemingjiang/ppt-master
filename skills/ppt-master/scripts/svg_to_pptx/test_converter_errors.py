#!/usr/bin/env python3
"""Regression tests for converter error surfacing."""

from pathlib import Path
import sys
import unittest
from xml.etree import ElementTree as ET


SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from svg_to_pptx import drawingml_converter as dc  # noqa: E402
from svg_to_pptx.drawingml_context import ConvertContext  # noqa: E402

SVG_NS = "http://www.w3.org/2000/svg"


class ConverterErrorSurfacingTests(unittest.TestCase):
    def test_errors_list_propagates_through_child_by_reference(self) -> None:
        root = ConvertContext()
        child = root.child(dx=1)
        child.errors.append("boom")
        self.assertIn("boom", root.errors)

    def test_converter_exception_recorded_on_ctx_errors(self) -> None:
        """A converter that raises must be recorded in ctx.errors, not just
        printed — so callers can detect dropped content."""
        ctx = ConvertContext()

        def _boom(elem, ctx):
            raise ValueError("simulated converter failure")

        original = dc._CONVERTERS.get("rect")
        dc._CONVERTERS["rect"] = _boom
        try:
            elem = ET.Element(f"{{{SVG_NS}}}rect")
            result = dc.convert_element(elem, ctx)
        finally:
            if original is not None:
                dc._CONVERTERS["rect"] = original
        self.assertIsNone(result)
        self.assertTrue(ctx.errors, "ctx.errors should record the failure")
        self.assertIn("rect", ctx.errors[0])

    def test_nested_group_failure_bubbles_to_slide(self) -> None:
        """A failure inside a <g> must reach the slide-level error list."""
        svg = (
            f'<svg xmlns="{SVG_NS}" viewBox="0 0 1280 720">'
            '<g transform="translate(10,10)"><rect x="0" y="0" width="5" height="5"/></g>'
            "</svg>"
        )
        import tempfile

        def _boom(elem, ctx):
            raise ValueError("nested boom")

        original = dc._CONVERTERS.get("rect")
        dc._CONVERTERS["rect"] = _boom
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as fh:
                fh.write(svg)
                path = Path(fh.name)
            _xml, _media, _rels, errors = dc.convert_svg_to_slide_shapes(
                path, slide_num=1
            )
        finally:
            if original is not None:
                dc._CONVERTERS["rect"] = original
            path.unlink(missing_ok=True)
        self.assertTrue(errors, "nested-group failure should surface in errors")


if __name__ == "__main__":
    unittest.main()
