"""Saved offline HTML must round-trip through source and final preparation safely."""
import json
import tempfile
import unittest
from pathlib import Path

from build_preview_html import render_preview
from prepare_single_html import PreparationError, prepare_single_html
from preview_editing import Conflict, EditError, MANIFEST, apply_edits
from saved_html import MARKER, read_saved_html, sync_saved_html
from test_preview_editing import fixture


class SavedHtmlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.p = Path(self.temp.name)
        fixture(self.p)
        render_preview(self.p)
        self.html = self.p / 'preview/index.html'
        self.manifest = json.loads((self.p / MANIFEST).read_text())
        self.slide = self.manifest['slides'][0]
        self.field = self.slide['fields'][1]

    def save(self):
        s, f = self.slide, self.field
        saved = read_saved_html(self.html)
        saved['packet'] = {'schema': 2, 'kind': 'ppt-master-review', 'packet_id': 'saved-test-record',
            'project_id': self.manifest['project_id'], 'base_revision': self.manifest['revision'],
            'changes': [{'slide_id': s['id'], 'fields': {f['id']: '保存后的观点'}, 'notes': '保存后的备注 **原样**。'}],
            'base_values': {s['id']: {'fields': {f['id']: {'field': f['field'], 'value': f['value']}}, 'notes': s['notes']}},
            'comments': []}
        self.html.write_text(MARKER.sub(lambda _: '<script id="ppt-master-saved-state" type="application/json">'+json.dumps(saved, ensure_ascii=False)+'</script>', self.html.read_text()))

    def test_rebuild_imports_once_without_touching_finals(self):
        (self.p / 'exports').mkdir()
        final = self.p / 'exports/old.html'; final.write_text('keep final')
        self.save()
        before = self.html.read_bytes()
        report = sync_saved_html(self.p, dry_run=True)
        self.assertTrue(report['pending_changes'])
        self.assertEqual(self.html.read_bytes(), before)
        self.assertNotIn('保存后的观点', (self.p / 'main_content.md').read_text())
        render_preview(self.p)
        self.assertIn('保存后的观点', (self.p / 'main_content.md').read_text())
        self.assertIn('保存后的备注', (self.p / 'notes/01_开场.md').read_text())
        self.assertEqual(final.read_text(), 'keep final')
        self.assertIsNone(read_saved_html(self.html)['packet'])
        source = (self.p / 'main_content.md').read_bytes()
        render_preview(self.p)
        self.assertEqual(source, (self.p / 'main_content.md').read_bytes())

    def test_final_preparation_imports_saved_content(self):
        self.save()
        with self.assertRaises(PreparationError):
            prepare_single_html(self.p, dry_run=True)
        prepare_single_html(self.p)
        html = '\n'.join(f.read_text() for f in (self.p / 'html_output/slides').glob('*.html'))
        self.assertIn('保存后的观点', html)
        self.assertIn('保存后的备注', (self.p / 'notes/total.md').read_text())

    def test_source_conflict_does_not_overwrite_saved_html(self):
        self.save()
        apply_edits(self.p, {'schema': 1, 'project_id': self.manifest['project_id'],
            'base_revision': self.manifest['revision'],
            'changes': [{'slide_id': self.slide['id'], 'fields': {self.field['id']: '另一份修改'}}]})
        before = self.html.read_bytes()
        with self.assertRaises(Conflict):
            render_preview(self.p)
        self.assertEqual(self.html.read_bytes(), before)
        self.assertIn('另一份修改', (self.p / 'main_content.md').read_text())

    def test_corrupted_saved_data_blocks_overwrite(self):
        self.html.write_text(MARKER.sub('<script id="ppt-master-saved-state" type="application/json">bad json</script>', self.html.read_text()))
        before = self.html.read_bytes()
        with self.assertRaises(EditError):
            render_preview(self.p)
        self.assertEqual(before, self.html.read_bytes())


if __name__ == '__main__':
    unittest.main()
