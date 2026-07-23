#!/usr/bin/env python3
"""Regression tests for build_preview_html."""

from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_preview_html import build_html  # noqa: E402


class BuildPreviewHtmlTests(unittest.TestCase):
    def test_static_file_preview_supports_copy_review(self) -> None:
        html = build_html(
            title="Demo",
            entries=[
                {
                    "key": "01",
                    "number": "01",
                    "href": "svg_output/01_封面.svg",
                    "label": "封面",
                    "title": "封面",
                    "takeaway": "",
                    "layout": "",
                    "visualization": "",
                    "notes_script": "",
                    "notes_key_points": [],
                    "notes_duration": "",
                    "assets": [],
                }
            ],
            strings={
                "eyebrow": "骨架审稿",
                "meta": "",
                "slides": "页数",
                "keyboard": "支持左右键",
                "prev": "上一页",
                "next": "下一页",
                "scope": "推荐审稿范围：结构、结论、素材、备注。",
                "takeaway": "本页 takeaway",
                "notes": "Notes 面板",
                "key_points": "Key Points",
                "duration": "时长",
                "assets": "资产清单",
                "comments": "批注入口",
                "comment_hint": "",
                "comment_placeholder": "",
                "copy_all": "复制全部批注",
                "copied_all": "已复制全部批注",
                "copy_failed": "复制失败",
                "no_comments": "",
                "saved": "",
                "no_takeaway": "",
                "no_notes": "",
                "no_assets": "",
                "asset_status": "状态",
                "asset_type": "类型",
                "asset_path": "路径",
                "review_title": "PPT 骨架审稿记录",
            },
            project_key="demo",
            review_build_id="build-123",
        )
        self.assertIn("copyAllCommentsBtn", html)
        self.assertIn("execCommand('copy')", html)
        self.assertIn("blocks.join('\\n')", html)
        self.assertIn("const reviewBuildId = \"build-123\";", html)
        self.assertIn("const storagePrefix = `ppt-master-preview-comments::${projectKey}::`;", html)
        self.assertIn("cleanupStaleCommentKeys()", html)
        self.assertIn("localStorage.removeItem(key);", html)
        self.assertIn("- project_key: ${projectKey}", html)
        self.assertNotIn("setExportDirBtn", html)
        self.assertNotIn("applyCommentsBtn", html)
        self.assertNotIn("saveCommentBtn", html)
        self.assertNotIn("copyCommentBtn", html)
        self.assertNotIn("exportAllCommentsBtn", html)
        self.assertNotIn("showDirectoryPicker", html)
        self.assertNotIn("showSaveFilePicker", html)
        self.assertNotIn("indexedDB.open", html)
        self.assertNotIn("URL.createObjectURL", html)
        self.assertNotIn("link.click()", html)
        self.assertNotIn("review_server.py", html)
        self.assertIn("overflow-y: auto;", html)
        self.assertIn("overscroll-behavior: contain;", html)
        self.assertIn("const outline = document.querySelector('.nav');", html)
        self.assertIn("function syncOutlineToCurrentSlide()", html)
        self.assertIn("outline.scrollTop = targetScrollTop;", html)
        self.assertIn("syncOutlineToCurrentSlide();", html)
        summary_index = html.index('<section class="summary-card">')
        viewer_index = html.index('<div class="viewer-shell">')
        navigation_index = html.index('<nav class="slide-navigation"')
        prev_index = html.index('id="prevBtn"')
        next_index = html.index('id="nextBtn"')

        self.assertLess(summary_index, viewer_index)
        self.assertLess(viewer_index, navigation_index)
        self.assertLess(navigation_index, prev_index)
        self.assertLess(prev_index, next_index)
        self.assertNotIn('class="toolbar"', html)
        self.assertNotIn('id="slideToolbarTitle"', html)
        self.assertNotIn("toolbarTitle", html)
        scope_sentence = "推荐审稿范围：结构、结论、素材、备注。"
        markup, script = html.split("<script>", 1)
        self.assertNotIn(scope_sentence, markup)
        self.assertIn(f'"scope": "{scope_sentence}"', script)
        self.assertIn("justify-content: flex-end;", html)
        self.assertIn("document.getElementById('prevBtn').addEventListener('click', () => selectSlide(current - 1));", html)
        self.assertIn("document.getElementById('nextBtn').addEventListener('click', () => selectSlide(current + 1));", html)
        script = script.split("</script>", 1)[0]
        result = subprocess.run(
            ["node", "-e", "const vm=require('vm'); new vm.Script(process.argv[1]);", script],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)


if __name__ == "__main__":
    unittest.main()
