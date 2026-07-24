#!/usr/bin/env python3
"""Tests for GIF analysis and optional MP4 optimization for single-file HTML slides."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from optimize_single_html_media import (  # noqa: E402
    _build_output_name,
    MediaOptimizationError,
    analyze_project,
)


GIF_1X1 = (
    b"GIF89a"
    b"\x01\x00\x01\x00"
    b"\x80\x00\x00"
    b"\x00\x00\x00"
    b"\xff\xff\xff"
    b"!\xf9\x04\x01\x00\x00\x00\x00"
    b",\x00\x00\x00\x00\x01\x00\x01\x00\x00"
    b"\x02\x02D\x01\x00;"
)


class OptimizeSingleHtmlMediaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project = Path(self.temp_dir.name)
        (self.project / "html_output" / "slides").mkdir(parents=True)
        (self.project / "images").mkdir()
        self.gif_path = self.project / "images" / "demo.gif"
        self.gif_path.write_bytes(GIF_1X1)
        self.source_sha1 = hashlib.sha1(GIF_1X1).hexdigest()

        slide = self.project / "html_output" / "slides" / "01_demo.html"
        slide.write_text(
            (
                '<section class="pm-slide" data-slide-id="01">'
                '<svg xmlns="http://www.w3.org/2000/svg" class="pm-artwork" viewBox="0 0 1280 720">'
                '<image xlink:href="../../images/demo.gif" x="100" y="120" width="256" height="144" '
                'preserveAspectRatio="xMidYMid meet" />'
                "</svg></section>"
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_default_target_is_1080p_and_recommends_640p_style_output(self) -> None:
        with patch("optimize_single_html_media.read_gif_metadata") as metadata:
            metadata.return_value.width = 1920
            metadata.return_value.height = 1080
            metadata.return_value.frames = 60
            metadata.return_value.duration_ms = 4000
            metadata.return_value.file_size = 16_000_000

            result = analyze_project(self.project)

        self.assertEqual(result["target"], "1080p")
        asset = result["assets"][0]
        self.assertEqual(asset["max_visible_pixels"], {"width": 384, "height": 216})
        self.assertEqual(asset["recommendation"]["pixels"], {"width": 640, "height": 360})
        self.assertEqual(asset["recommendation"]["format"], "video/mp4")

    def test_explicit_4k_target_recommends_960p_style_output(self) -> None:
        with patch("optimize_single_html_media.read_gif_metadata") as metadata:
            metadata.return_value.width = 1920
            metadata.return_value.height = 1080
            metadata.return_value.frames = 60
            metadata.return_value.duration_ms = 4000
            metadata.return_value.file_size = 16_000_000

            result = analyze_project(self.project, target="4k")

        asset = result["assets"][0]
        self.assertEqual(asset["max_visible_pixels"], {"width": 768, "height": 432})
        self.assertEqual(asset["recommendation"]["pixels"], {"width": 960, "height": 540})

    def test_analysis_only_does_not_write_media_output(self) -> None:
        with patch("optimize_single_html_media.read_gif_metadata") as metadata:
            metadata.return_value.width = 1920
            metadata.return_value.height = 1080
            metadata.return_value.frames = 60
            metadata.return_value.duration_ms = 4000
            metadata.return_value.file_size = 16_000_000

            result = analyze_project(self.project, apply=False)

        self.assertEqual(result["summary"]["optimized_count"], 0)
        self.assertFalse((self.project / "html_output" / "media_optimized").exists())
        self.assertIsNone(result["assets"][0]["replacement"])

    def test_apply_uses_existing_output_without_overwriting(self) -> None:
        optimized_relpath = (
            Path("html_output")
            / "media_optimized"
            / _build_output_name(
                "images/demo.gif", "1080p", 640, 360, self.source_sha1
            )
        )
        output_path = self.project / optimized_relpath
        output_path.parent.mkdir(parents=True)
        output_path.write_bytes(b"existing mp4")

        with patch("optimize_single_html_media.read_gif_metadata") as metadata:
            metadata.return_value.width = 1920
            metadata.return_value.height = 1080
            metadata.return_value.frames = 60
            metadata.return_value.duration_ms = 4000
            metadata.return_value.file_size = 16_000_000
            with patch("optimize_single_html_media.subprocess.run") as run_mock:
                result = analyze_project(self.project, apply=True)

        run_mock.assert_not_called()
        asset = result["assets"][0]
        self.assertEqual(asset["action"], "existing")
        self.assertEqual(asset["replacement"]["optimized_relpath"], optimized_relpath.as_posix())
        self.assertEqual(asset["rewritten_placements"], 1)
        self.assertEqual(output_path.read_bytes(), b"existing mp4")
        rewritten_slide = (
            self.project / "html_output" / "slides" / "01_demo.html"
        ).read_text(encoding="utf-8")
        self.assertNotIn("<image", rewritten_slide)
        self.assertNotIn("<foreignObject", rewritten_slide)
        self.assertIn("<video", rewritten_slide)
        self.assertIn('class="pm-optimized-video pm-media-overlay"', rewritten_slide)
        self.assertIn("left:7.8125%;top:16.66666667%", rewritten_slide)
        self.assertIn('data-pm-target="1080p"', rewritten_slide)
        self.assertIn("../media_optimized/", rewritten_slide)
        self.assertEqual(self.gif_path.read_bytes(), GIF_1X1)

    def test_apply_transcodes_with_mocked_ffmpeg(self) -> None:
        with patch("optimize_single_html_media.read_gif_metadata") as metadata:
            metadata.return_value.width = 1920
            metadata.return_value.height = 1080
            metadata.return_value.frames = 60
            metadata.return_value.duration_ms = 4000
            metadata.return_value.file_size = 16_000_000
            with patch("optimize_single_html_media.shutil.which", return_value="/usr/bin/ffmpeg"):
                with patch("optimize_single_html_media.subprocess.run") as run_mock:
                    def fake_run(command, check, capture_output, text):
                        Path(command[-1]).write_bytes(b"created mp4")
                        return subprocess.CompletedProcess(command, 0, "", "")

                    run_mock.side_effect = fake_run
                    result = analyze_project(self.project, apply=True)

        asset = result["assets"][0]
        self.assertEqual(asset["action"], "created")
        self.assertEqual(asset["optimized_bytes"], len(b"created mp4"))
        self.assertEqual(asset["saved_bytes"], 16_000_000 - len(b"created mp4"))
        self.assertEqual(
            result["summary"]["saved_bytes"], 16_000_000 - len(b"created mp4")
        )
        self.assertEqual(result["summary"]["rewritten_placement_count"], 1)
        command = run_mock.call_args.args[0]
        self.assertEqual(command[command.index("-crf") + 1], "23")
        self.assertTrue((self.project / asset["planned_output_relpath"]).exists())

    def test_apply_migrates_existing_foreignobject_video_to_html_overlay(self) -> None:
        optimized_relpath = (
            Path("html_output")
            / "media_optimized"
            / _build_output_name(
                "images/demo.gif", "1080p", 640, 360, self.source_sha1
            )
        )
        output_path = self.project / optimized_relpath
        output_path.parent.mkdir(parents=True)
        output_path.write_bytes(b"existing mp4")
        slide_path = self.project / "html_output" / "slides" / "01_demo.html"
        slide_path.write_text(
            (
                '<section class="pm-slide" data-slide-id="01">'
                '<svg xmlns="http://www.w3.org/2000/svg" class="pm-artwork" '
                'viewBox="0 0 1280 720">'
                '<foreignObject x="100" y="120" width="256" height="144">'
                '<video xmlns="http://www.w3.org/1999/xhtml" '
                'data-pm-source-gif="../../images/demo.gif" '
                'data-pm-placement-id="legacy-placement" '
                'data-pm-preserve-aspect-ratio="xMidYMid meet" '
                'data-pm-target="1080p" src="../media_optimized/old.mp4"></video>'
                "</foreignObject></svg></section>"
            ),
            encoding="utf-8",
        )

        with patch("optimize_single_html_media.read_gif_metadata") as metadata:
            metadata.return_value.width = 1920
            metadata.return_value.height = 1080
            metadata.return_value.frames = 60
            metadata.return_value.duration_ms = 4000
            metadata.return_value.file_size = 16_000_000
            result = analyze_project(self.project, apply=True)

        self.assertEqual(result["assets"][0]["rewritten_placements"], 1)
        rewritten = slide_path.read_text(encoding="utf-8")
        self.assertNotIn("<foreignObject", rewritten)
        self.assertIn('class="pm-optimized-video pm-media-overlay"', rewritten)
        self.assertIn('data-pm-placement-id="legacy-placement"', rewritten)
        self.assertIn(output_path.name, rewritten)

    def test_reanalysis_can_upgrade_an_existing_video_to_4k(self) -> None:
        optimized_relpath = (
            Path("html_output")
            / "media_optimized"
            / _build_output_name(
                "images/demo.gif", "1080p", 640, 360, self.source_sha1
            )
        )
        output_path = self.project / optimized_relpath
        output_path.parent.mkdir(parents=True)
        output_path.write_bytes(b"existing 1080p mp4")

        with patch("optimize_single_html_media.read_gif_metadata") as metadata:
            metadata.return_value.width = 1920
            metadata.return_value.height = 1080
            metadata.return_value.frames = 60
            metadata.return_value.duration_ms = 4000
            metadata.return_value.file_size = 16_000_000
            analyze_project(self.project, apply=True)

            target_4k_relpath = (
                Path("html_output")
                / "media_optimized"
                / _build_output_name(
                    "images/demo.gif", "4k", 960, 540, self.source_sha1
                )
            )
            target_4k_path = self.project / target_4k_relpath
            target_4k_path.write_bytes(b"existing 4k mp4")
            result = analyze_project(self.project, target="4k", apply=True)

        asset = result["assets"][0]
        self.assertEqual(asset["recommendation"]["pixels"], {"width": 960, "height": 540})
        self.assertEqual(asset["rewritten_placements"], 1)
        rewritten_slide = (
            self.project / "html_output" / "slides" / "01_demo.html"
        ).read_text(encoding="utf-8")
        self.assertIn('data-pm-target="4k"', rewritten_slide)
        self.assertIn(target_4k_path.name, rewritten_slide)
        self.assertNotIn(output_path.name, rewritten_slide)

    def test_does_not_rewrite_when_mp4_is_not_smaller(self) -> None:
        with patch("optimize_single_html_media.read_gif_metadata") as metadata:
            metadata.return_value.width = 1920
            metadata.return_value.height = 1080
            metadata.return_value.frames = 60
            metadata.return_value.duration_ms = 4000
            metadata.return_value.file_size = 10
            with patch("optimize_single_html_media.shutil.which", return_value="/usr/bin/ffmpeg"):
                with patch("optimize_single_html_media.subprocess.run") as run_mock:
                    def fake_run(command, check, capture_output, text):
                        Path(command[-1]).write_bytes(b"larger than gif")
                        return subprocess.CompletedProcess(command, 0, "", "")

                    run_mock.side_effect = fake_run
                    result = analyze_project(self.project, apply=True, min_bytes=0)

        self.assertEqual(result["assets"][0]["action"], "not_smaller")
        slide = (self.project / "html_output" / "slides" / "01_demo.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("<image", slide)
        self.assertNotIn("<video", slide)

    def test_changed_gif_content_invalidates_existing_derivative(self) -> None:
        with patch("optimize_single_html_media.read_gif_metadata") as metadata:
            metadata.return_value.width = 1920
            metadata.return_value.height = 1080
            metadata.return_value.frames = 60
            metadata.return_value.duration_ms = 4000
            metadata.return_value.file_size = 16_000_000
            with patch("optimize_single_html_media.shutil.which", return_value="/usr/bin/ffmpeg"):
                with patch("optimize_single_html_media.subprocess.run") as run_mock:
                    def fake_run(command, check, capture_output, text):
                        Path(command[-1]).write_bytes(b"created mp4")
                        return subprocess.CompletedProcess(command, 0, "", "")

                    run_mock.side_effect = fake_run
                    first = analyze_project(self.project, apply=True)
                    self.gif_path.write_bytes(GIF_1X1 + b"changed")
                    second = analyze_project(self.project, apply=True)

        self.assertEqual(run_mock.call_count, 2)
        self.assertNotEqual(
            first["assets"][0]["planned_output_relpath"],
            second["assets"][0]["planned_output_relpath"],
        )
        slide = (self.project / "html_output" / "slides" / "01_demo.html").read_text(
            encoding="utf-8"
        )
        self.assertIn(Path(second["assets"][0]["planned_output_relpath"]).name, slide)
        self.assertNotIn(Path(first["assets"][0]["planned_output_relpath"]).name, slide)

    def test_retarget_updates_every_duplicate_placement(self) -> None:
        slide_path = self.project / "html_output" / "slides" / "01_demo.html"
        slide_path.write_text(
            (
                '<section class="pm-slide" data-slide-id="01">'
                '<svg xmlns="http://www.w3.org/2000/svg" class="pm-artwork" viewBox="0 0 1280 720">'
                '<image href="../../images/demo.gif" x="100" y="120" width="256" height="144" '
                'preserveAspectRatio="xMidYMid meet" />'
                '<image href="../../images/demo.gif" x="500" y="120" width="256" height="144" '
                'preserveAspectRatio="xMidYMid meet" />'
                "</svg></section>"
            ),
            encoding="utf-8",
        )
        with patch("optimize_single_html_media.read_gif_metadata") as metadata:
            metadata.return_value.width = 1920
            metadata.return_value.height = 1080
            metadata.return_value.frames = 60
            metadata.return_value.duration_ms = 4000
            metadata.return_value.file_size = 16_000_000
            with patch("optimize_single_html_media.shutil.which", return_value="/usr/bin/ffmpeg"):
                with patch("optimize_single_html_media.subprocess.run") as run_mock:
                    def fake_run(command, check, capture_output, text):
                        Path(command[-1]).write_bytes(b"created mp4")
                        return subprocess.CompletedProcess(command, 0, "", "")

                    run_mock.side_effect = fake_run
                    first = analyze_project(self.project, apply=True)
                    second = analyze_project(self.project, target="4k", apply=True)

        self.assertEqual(first["summary"]["rewritten_placement_count"], 2)
        self.assertEqual(second["summary"]["rewritten_placement_count"], 2)
        rewritten = slide_path.read_text(encoding="utf-8")
        self.assertEqual(rewritten.count('data-pm-target="4k"'), 2)
        self.assertEqual(rewritten.count('data-pm-target="1080p"'), 0)
        self.assertEqual(rewritten.count("data-pm-placement-id="), 2)

    def test_apply_requires_ffmpeg_with_actionable_error(self) -> None:
        with patch("optimize_single_html_media.read_gif_metadata") as metadata:
            metadata.return_value.width = 1920
            metadata.return_value.height = 1080
            metadata.return_value.frames = 60
            metadata.return_value.duration_ms = 4000
            metadata.return_value.file_size = 16_000_000
            with patch("optimize_single_html_media.shutil.which", return_value=None):
                with self.assertRaisesRegex(MediaOptimizationError, "ffmpeg is required for --apply"):
                    analyze_project(self.project, apply=True)

    def test_cli_json_error_is_one_object(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "missing"
            project.mkdir()
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "optimize_single_html_media.py"),
                    str(project),
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertIn("slides directory not found", payload["error"])
        self.assertEqual(completed.stderr, "")

    def test_cli_help_has_copyable_examples(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "optimize_single_html_media.py"), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("optimize_single_html_media.py projects/ai-lab-demo --json", completed.stdout)
        self.assertIn("--target 4k --min-bytes 8000000", completed.stdout)


if __name__ == "__main__":
    unittest.main()
