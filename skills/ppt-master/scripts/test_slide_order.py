"""Reordering preserves page identity and uses the review transaction end to end."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from build_preview_html import render_preview
from preview_editing import Conflict, EditError, MANIFEST, atomic_write, revision
from review_packets import apply_packet, inspect_packet, parse_packet
from saved_html import MARKER, read_saved_html
from prepare_single_html import PreparationError, prepare_single_html
from test_preview_editing import fixture


class SlideOrderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.p = Path(self.temp.name)
        fixture(self.p)
        for file, old, new in [('main_content.md', '### Slide 02', '### Slide 03'),
                               ('design_spec.md', '#### Slide 02', '#### Slide 03')]:
            path = self.p / file
            text = path.read_text()
            start = text.index(old)
            end = text.find('\n## ', start)
            block = text[start:end if end >= 0 else len(text)].replace(old, new).replace('下一页', '第三页')
            path.write_text(text[:end] + '\n' + block + text[end:] if end >= 0 else text + '\n' + block)
        (self.p / 'svg_output/03_第三页.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"><text x="96" y="295">第三页</text><text data-pm-page-number="true" x="1200" y="680">03</text></svg>')
        notes = self.p / 'notes/total.md'
        notes.write_text(notes.read_text() + '\n---\n# 03_第三页\n\n第三页备注。\n')
        (self.p / 'notes/03_第三页.md').write_text('第三页备注。\n')
        render_preview(self.p)
        self.m = json.loads((self.p / MANIFEST).read_text())
        self.ids = [s['id'] for s in self.m['slides']]

    def packet(self, after=None):
        return {'schema': 2, 'kind': 'ppt-master-review', 'packet_id': 'order-test-record',
                'project_id': self.m['project_id'], 'base_revision': self.m['revision'],
                'changes': [], 'base_values': {}, 'comments': [],
                'order': {'before': self.ids, 'after': after or self.ids[::-1]}}

    def test_combined_roundtrip_renumbers_without_detaching_content(self):
        (self.p / 'exports').mkdir()
        (self.p / 'exports/approved.pptx').write_bytes(b'keep existing final')
        packet = self.packet()
        s, f = self.m['slides'][0], self.m['slides'][0]['fields'][1]
        packet['changes'] = [{'slide_id': s['id'], 'fields': {f['id']: '明确标准。'}, 'notes': '重排后的备注。'}]
        packet['base_values'] = {s['id']: {'fields': {f['id']: {'value': f['value'], 'field': f['field']}}, 'notes': s['notes']}}
        files = {str(f.relative_to(self.p)): f.read_bytes() for f in self.p.rglob('*') if f.is_file()}
        self.assertTrue(apply_packet(self.p, packet, dry_run=True)['pending_order'])
        self.assertEqual(files, {str(f.relative_to(self.p)): f.read_bytes() for f in self.p.rglob('*') if f.is_file()})
        apply_packet(self.p, packet)
        render_preview(self.p)
        m = json.loads((self.p / MANIFEST).read_text())
        self.assertEqual([s['id'] for s in m['slides']], self.ids[::-1])
        self.assertEqual([s['key'] for s in m['slides']], ['01', '02', '03'])
        self.assertIn('>01<', (self.p / 'svg_output/01_第三页.svg').read_text())
        self.assertIn('明确标准。', (self.p / 'svg_output/03_开场.svg').read_text())
        self.assertIn('重排后的备注。', (self.p / 'notes/03_开场.md').read_text())
        self.assertTrue(m['slides'][2]['notes'].startswith('重排后的备注。'))
        self.assertIn('### 第一章', (self.p / 'design_spec.md').read_text())
        self.assertIn('保留这个章节与说明', (self.p / 'design_spec.md').read_text())
        self.assertFalse((self.p / 'svg_output/03_第三页.svg').exists())
        self.assertEqual((self.p / 'exports/approved.pptx').read_bytes(), b'keep existing final')
        self.assertTrue((self.p / 'preview/final_stale.json').exists())
        before = revision(self.p)
        self.assertEqual(apply_packet(self.p, packet)['files'], [])
        self.assertEqual(revision(self.p), before)

    def test_conflicts_invalid_permutations_and_late_text_identity(self):
        bad = self.packet(self.ids[:2])
        with self.assertRaises(EditError):
            inspect_packet(self.p, bad)
        first = self.packet([self.ids[1], self.ids[0], self.ids[2]])
        second = self.packet()
        second['packet_id'] = 'order-second-record'
        apply_packet(self.p, first)
        self.assertEqual(inspect_packet(self.p, second)['status'], 'conflict')
        # A text-only record from the original baseline still resolves the same UUID.
        s, f = self.m['slides'][0], self.m['slides'][0]['fields'][1]
        packet = self.packet();del packet['order']
        packet['packet_id'] = 'old-text-record'
        packet['changes'] = [{'slide_id': s['id'], 'fields': {f['id']: '旧草稿的文字修改。'}}]
        packet['base_values'] = {s['id']: {'fields': {f['id']: {'field': f['field'], 'value': f['value']}}}}
        apply_packet(self.p, packet)
        self.assertIn('旧草稿的文字修改。', (self.p / 'svg_output/02_开场.svg').read_text())

    def test_failed_rename_transaction_rolls_back(self):
        before = revision(self.p)
        calls = []
        def fail_once(path, value):
            calls.append(path)
            if len(calls) == 4:
                raise OSError('write failed')
            atomic_write(path, value)
        with patch('preview_editing.atomic_write', side_effect=fail_once):
            with self.assertRaises(OSError):
                apply_packet(self.p, self.packet())
        self.assertEqual(revision(self.p), before)

    def test_assets_keep_their_original_page_and_collisions_stop(self):
        (self.p / 'asset_manifest.md').write_text('''# Assets
| Asset | Status | Type | Purpose | Source Path | Used In |
| image.png | ready | image | metric 01 | images/image.png | 01 first, 03 third |
## Slide Mapping
### Slide 01 - first
first asset
### Slide 02 - second
second asset
### Slide 03 - third
third asset
''')
        render_preview(self.p)
        apply_packet(self.p, self.packet())
        text = (self.p / 'asset_manifest.md').read_text()
        self.assertIn('03 first, 01 third', text)
        self.assertIn('metric 01', text)
        self.assertLess(text.index('third asset'), text.index('first asset'))
        # An unrelated note destination must never be overwritten during renumbering.
        (self.p / 'notes/02_第三页.md').write_text('unrelated')
        m = json.loads((self.p / MANIFEST).read_text())
        current = [s['id'] for s in m['slides']]
        packet = self.packet([current[1], current[0], current[2]])
        packet['order']['before'] = current
        packet['packet_id'] = 'collision-record'
        render_preview(self.p)
        with self.assertRaises(Conflict):
            apply_packet(self.p, packet)
        self.assertEqual((self.p / 'notes/02_第三页.md').read_text(), 'unrelated')

    def test_saved_order_import_and_final_dry_run_gate(self):
        path = self.p / 'preview/index.html'
        saved = read_saved_html(path);saved['packet'] = self.packet()
        path.write_text(MARKER.sub(lambda _: '<script id="ppt-master-saved-state" type="application/json">' + json.dumps(saved) + '</script>', path.read_text()))
        with self.assertRaises(PreparationError):
            prepare_single_html(self.p, dry_run=True)
        render_preview(self.p)
        self.assertEqual([s['id'] for s in json.loads((self.p / MANIFEST).read_text())['slides']], self.ids[::-1])
        self.assertIsNone(read_saved_html(path)['packet'])

    def test_global_markdown_order_only_parses_stable_refs(self):
        refs = self.m['review']
        before = ' → '.join(refs['slides'][uid]['ref'] for uid in self.ids)
        after = ' → '.join(reversed(before.split(' → ')))
        text = f"# PPT 修改清单\n\n项目：示例 [{refs['project_ref']}]\n版本：{refs['version_ref']}｜修改记录：global-order-test\n\n## 全局修改：页面顺序\n按新顺序排列全部页面，并从 01 连续编号；正文、备注和批注跟随原页面。\n原顺序：{before}\n新顺序：{after}"
        packet = parse_packet(text, self.p)
        self.assertEqual(packet['order']['after'], self.ids[::-1])
        apply_packet(self.p, packet)


if __name__ == '__main__':
    unittest.main()
