#!/usr/bin/env python3
"""Regression tests for clean_pptx_placeholders."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPT_PATH = SCRIPT_DIR / "clean_pptx_placeholders.py"

SLIDE_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr/>
      <p:grpSpPr/>
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="2" name="Slide Number Placeholder 1"/>
          <p:cNvSpPr/>
          <p:nvPr>
            <p:ph type="sldNum" idx="12"/>
          </p:nvPr>
        </p:nvSpPr>
        <p:spPr/>
        <p:txBody>
          <a:bodyPr/>
          <a:lstStyle/>
          <a:p>
            <a:r><a:t>9</a:t></a:r>
          </a:p>
        </p:txBody>
      </p:sp>
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="3" name="Regular Text"/>
          <p:cNvSpPr/>
          <p:nvPr/>
        </p:nvSpPr>
        <p:spPr/>
        <p:txBody>
          <a:bodyPr/>
          <a:lstStyle/>
          <a:p>
            <a:r><a:t>Keep me</a:t></a:r>
          </a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>
"""


def read_slide_xml(pptx_path: Path) -> str:
    with zipfile.ZipFile(pptx_path) as archive:
        with archive.open("ppt/slides/slide1.xml") as handle:
            return handle.read().decode("utf-8")


class CleanPptxPlaceholdersTests(unittest.TestCase):
    def create_fixture(self, root: Path) -> Path:
        pptx_path = root / "fixture.pptx"
        with zipfile.ZipFile(pptx_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("ppt/presentation.xml", "<presentation/>")
            archive.writestr("ppt/slides/slide1.xml", SLIDE_XML)
        return pptx_path

    def test_in_place_cleanup_removes_slide_number_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            pptx_path = self.create_fixture(Path(tmp_dir))
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(pptx_path), "--in-place", "--format", "json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["placeholder_types"], ["sldNum"])
            self.assertEqual(payload["placeholders_removed"], 1)
            self.assertEqual(payload["slides_changed"], 1)

            cleaned_xml = read_slide_xml(pptx_path)
            self.assertNotIn('type="sldNum"', cleaned_xml)
            self.assertIn("Keep me", cleaned_xml)

    def test_dry_run_reports_changes_without_modifying_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            pptx_path = self.create_fixture(Path(tmp_dir))
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    str(pptx_path),
                    "--in-place",
                    "--dry-run",
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "dry-run")
            self.assertEqual(payload["placeholders_removed"], 1)
            self.assertEqual(payload["slides_changed"], 1)
            self.assertIn('type="sldNum"', read_slide_xml(pptx_path))


if __name__ == "__main__":
    unittest.main()
