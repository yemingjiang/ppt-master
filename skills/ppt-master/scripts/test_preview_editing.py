"""Round-trip and conflict regressions for source-backed review editing."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from build_preview_html import render_preview
from preview_editing import Conflict, EditError, MANIFEST, apply_edits, prepare_manifest, revision


def fixture(project):
    (project / 'svg_output').mkdir(parents=True)
    (project / 'notes').mkdir()
    (project / 'main_content.md').write_text('''# 示例 主内容

## Slides

### Slide 01 - 执行越快，越要明确目标。
- Title: 执行越快，越要明确目标。
- Takeaway: 执行越快，越要明确目标。
- Bullets:
  - 执行越快，
  - 越要明确目标。
  - 重复
  - 重复
- Assets:
  - None
- Review Notes:
  - 保留此处备注

### Slide 02 - 下一页
- Title: 下一页
- Takeaway: 下一页
- Bullets:
  - 下一页
- Assets:
  - None
- Review Notes:
  - None
''')
    (project / 'design_spec.md').write_text('''# 示例 - Design Spec
## I. Project Information
| Item | Value |
| --- | --- |
| Project Name | 示例 |
## IX. Content Outline
### 第一章
#### Slide 01 - 执行越快，越要明确目标。
- **Layout**: 双行
- **Title**: 执行越快，越要明确目标。
- **Content**:
  - 执行越快，
  - 越要明确目标。
  - 重复
  - 重复
### 第二章
#### Slide 02 - 下一页
- **Title**: 下一页
## X. Speaker Notes Requirements
保留这个章节与说明。
''')
    notes = '# 01_开场\n\n第一段。\n\n第二段 **重点**。\n\n要点：目标\n\n时长：1分\n---\n# 02_下一页\n\n下一页备注。\n\n时长：1分\n'
    (project / 'notes/total.md').write_text(notes)
    (project / 'notes/01_开场.md').write_text('第一段。\n\n第二段 **重点**。\n\n要点：目标\n\n时长：1分\n')
    (project / 'notes/02_下一页.md').write_text('下一页备注。\n\n时长：1分\n')
    (project / 'svg_output/01_开场.svg').write_text('''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"><title>执行越快，越要明确目标。</title><rect width="1280" height="720" fill="#FAFAF8"/><g fill="#171717" font-family="Arial, PingFang SC" font-size="56"><text x="96" y="295">执行越快，</text><text x="96" y="401" fill="#2563EB">越要明确目标。</text><text x="96" y="550" font-size="28">重复</text><text x="640" y="550" font-size="28">重复</text></g></svg>''')
    (project / 'svg_output/02_下一页.svg').write_text('''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"><rect width="1280" height="720" fill="#FAFAF8"/><text x="96" y="295" font-size="56">下一页</text></svg>''')


class PreviewEditingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.p = Path(self.temp.name)
        fixture(self.p)
        render_preview(self.p, editable=True)
        self.manifest = json.loads((self.p / MANIFEST).read_text())

    def package(self):
        slide = self.manifest['slides'][0]
        return {'schema': 1, 'project_id': self.manifest['project_id'], 'base_revision': self.manifest['revision'], 'changes': [
            {'slide_id': slide['id'], 'fields': {slide['fields'][1]['id']: '越要说清标准。'}, 'notes': '新的讲述。\n\n保留 **Markdown** 和[链接](https://example.org)。\n\n要点：标准\n\n时长：1分20秒'}]}

    def test_edit_rebuild_roundtrip_preserves_ids_geometry_and_other_slides(self):
        before = (self.p / 'svg_output/02_下一页.svg').read_bytes()
        result = apply_edits(self.p, self.package())
        render_preview(self.p)  # Editing persists without repeating the flag.
        after = json.loads((self.p / MANIFEST).read_text())
        self.assertEqual(after['slides'][0]['id'], self.manifest['slides'][0]['id'])
        self.assertEqual(after['slides'][0]['fields'][1]['id'], self.manifest['slides'][0]['fields'][1]['id'])
        self.assertEqual(after['slides'][0]['title'], '执行越快，越要说清标准。')
        self.assertEqual(after['slides'][0]['fields'][1]['value'], '越要说清标准。')
        self.assertEqual((self.p / 'svg_output/02_下一页.svg').read_bytes(), before)
        self.assertIn('\n\n保留 **Markdown**', after['slides'][0]['notes'])
        self.assertIn('保留此处备注', (self.p / 'main_content.md').read_text())
        self.assertIn('### 第二章', (self.p / 'design_spec.md').read_text())
        self.assertIn('保留这个章节与说明', (self.p / 'design_spec.md').read_text())
        node = list(ET.parse(self.p / 'svg_output/01_开场.svg').getroot().iter('{http://www.w3.org/2000/svg}text'))[1]
        self.assertEqual((node.get('x'), node.get('y'), node.get('fill')), ('96', '401', '#2563EB'))
        self.assertTrue(Path(result['history']).exists())
        self.assertIn('新的讲述', (self.p / 'preview/index.html').read_text())

    def test_dry_run_and_stale_revision_never_write(self):
        before = revision(self.p)
        result = apply_edits(self.p, self.package(), dry_run=True)
        self.assertTrue(result['files'])
        self.assertEqual(revision(self.p), before)
        path = self.p / 'notes/02_下一页.md'
        path.write_text('另一位编辑修改了备注。')
        changed = revision(self.p)
        with self.assertRaises(Conflict):
            apply_edits(self.p, self.package())
        self.assertEqual(revision(self.p), changed)

    def test_ambiguous_text_is_readonly_and_unknown_nodes_rejected(self):
        slide = self.manifest['slides'][0]
        self.assertEqual(len(slide['fields']), 2)
        self.assertEqual(slide['readonly'], ['重复', '重复'])
        package = self.package()
        package['changes'][0]['fields'] = {'not-mapped': '不能修改'}
        with self.assertRaises(EditError):
            apply_edits(self.p, package)

    def test_multiline_and_markup_are_plain_text(self):
        package = self.package()
        id = self.manifest['slides'][0]['fields'][1]['id']
        package['changes'][0]['fields'][id] = '明确\n<标准>&目标'
        result = apply_edits(self.p, package)
        f = result['manifest']['slides'][0]['fields'][1]
        self.assertEqual(f['value'], '明确\n<标准>&目标')
        self.assertIn('明确<标准>&目标', (self.p / 'main_content.md').read_text())
        self.assertIn('&lt;标准&gt;&amp;目标', (self.p / 'svg_output/01_开场.svg').read_text())

    def test_notes_only_leaves_visual_and_main_source_unchanged(self):
        before = {f: (self.p / f).read_bytes() for f in ['main_content.md','design_spec.md','svg_output/01_开场.svg']}
        package = self.package()
        package['changes'][0]['fields'] = {}
        apply_edits(self.p, package)
        for f, value in before.items():
            self.assertEqual((self.p / f).read_bytes(), value)

    def test_notes_cannot_inject_another_slide(self):
        package = self.package()
        package['changes'][0]['notes'] = '正文\r\n---\r\n# 02_替换其他页\r\n内容'
        before = revision(self.p)
        with self.assertRaises(EditError):
            apply_edits(self.p, package)
        self.assertEqual(revision(self.p), before)

    def test_failed_multi_file_save_rolls_back(self):
        from preview_editing import atomic_write
        before = revision(self.p)
        attempts = []
        def fail_once(path, value):
            attempts.append(path)
            if len(attempts) == 3:
                raise OSError('simulated write failure')
            atomic_write(path, value)
        with patch('preview_editing.atomic_write', side_effect=fail_once):
            with self.assertRaises(OSError):
                apply_edits(self.p, self.package())
        self.assertEqual(revision(self.p), before)


if __name__ == '__main__':
    unittest.main()
