#!/usr/bin/env python3
"""Regression tests for sync_design_spec_from_main_content."""

from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import main_content_pipeline as mcp  # noqa: E402


def _minimal_spec(text: str) -> dict:
    return {
        "language": "en",
        "use_case": "Demo",
        "design_spec_text": text,
        "slides": [],
    }


def _minimal_model() -> dict:
    return {"slides": []}


class SyncDesignSpecTests(unittest.TestCase):
    def _run_sync(self, spec_text: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "design_spec.md").write_text(spec_text, encoding="utf-8")
            mcp.sync_design_spec_from_main_content(
                project, _minimal_spec(spec_text), _minimal_model()
            )
            return (project / "design_spec.md").read_text(encoding="utf-8")

    def test_sync_replaces_outline_with_trailing_section(self) -> None:
        spec = (
            "## IX. Content Outline\nOLD OUTLINE\n\n"
            "## X. Speaker Notes Requirements\nnotes\n"
        )
        result = self._run_sync(spec)
        self.assertNotIn("OLD OUTLINE", result)
        self.assertIn("## X. Speaker Notes Requirements", result)

    def test_sync_replaces_outline_when_it_is_last_section(self) -> None:
        """Outline as the final section (no '## X.' anchor) must still sync."""
        spec = "## IX. Content Outline\nOLD OUTLINE\n"
        result = self._run_sync(spec)
        self.assertNotIn("OLD OUTLINE", result)

    def test_missing_outline_heading_raises(self) -> None:
        """A spec with no Content Outline heading must fail loudly, not
        silently write unchanged text and report success."""
        spec = "## II. Canvas Specification\nstuff\n"
        with self.assertRaises(ValueError):
            self._run_sync(spec)


if __name__ == "__main__":
    unittest.main()
