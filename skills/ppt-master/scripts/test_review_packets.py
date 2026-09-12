"""Offline clipboard feedback: baselines, receipts, retries and source changes."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from build_preview_html import render_preview
from preview_editing import Conflict, EditError, MANIFEST, apply_edits, revision
from review_packets import RECEIPTS, acknowledge, apply_packet, inspect_packet, parse_packet
from test_preview_editing import fixture


class ReviewPacketTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.p = Path(self.temp.name)
        fixture(self.p)
        render_preview(self.p)  # Raw-source drafts are editable without an opt-in flag.
        self.m = json.loads((self.p / MANIFEST).read_text())
        self.s = self.m['slides'][0]
        self.f = self.s['fields'][1]

    def packet(self):
        return {'schema': 2, 'kind': 'ppt-master-review', 'packet_id': 'packet-test-001',
                'project_id': self.m['project_id'], 'base_revision': self.m['revision'],
                'changes': [{'slide_id': self.s['id'], 'fields': {self.f['id']: '越要说清标准。'},
                             'notes': '新的讲述。\n\n要点：标准\n\n时长：1分20秒'}],
                'base_values': {self.s['id']: {'fields': {self.f['id']: {'value': self.f['value'], 'field': self.f['field']}}, 'notes': self.s['notes']}},
                'comments': [{'slide_id': self.s['id'], 'key': '01', 'text': '标题请再简练一点。'}]}

    def test_full_copied_record_and_cli_inspect_are_readonly(self):
        packet = self.packet()
        text = '# PPT 修改记录\n\n正文修改 1 处 · 备注修改 1 页 · 批注 1 条\n\n```json\n' + json.dumps(packet, ensure_ascii=False) + '\n```'
        self.assertEqual(parse_packet(text), packet)
        before = revision(self.p)
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('edit_preview.py')), 'inspect', str(self.p), '--stdin', '--json'], input=text, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)['comments_pending']), 1)
        self.assertEqual(revision(self.p), before)
        self.assertFalse((self.p / RECEIPTS).exists())
        with self.assertRaises(EditError):
            parse_packet(text + '\n```json\n{}\n```')

    def test_apply_preserves_comments_until_explicit_ack_and_retries_are_safe(self):
        packet = self.packet()
        apply_packet(self.p, packet)
        self.assertIn('越要说清标准。', (self.p / 'main_content.md').read_text())
        result = inspect_packet(self.p, packet)
        self.assertFalse(result['pending_changes'])
        self.assertEqual(result['comments_pending'], packet['comments'])
        self.assertFalse(result['already_processed'])
        before = revision(self.p)
        self.assertEqual(apply_packet(self.p, packet)['files'], [])
        self.assertEqual(revision(self.p), before)
        acknowledge(self.p, packet, comments=True)
        render_preview(self.p)
        self.assertTrue(inspect_packet(self.p, packet)['already_processed'])
        self.assertEqual(json.loads((self.p / MANIFEST).read_text())['receipts'], [
            {'packet_id': packet['packet_id'], 'content_applied': True, 'comments_processed': True}])
        tampered = copy.deepcopy(packet)
        tampered['comments'][0]['text'] = '篡改了原来的修改记录'
        with self.assertRaises(Conflict):
            apply_packet(self.p, tampered)

    def test_comment_only_and_legacy_comments(self):
        packet = self.packet()
        packet['changes'] = []
        packet['base_values'] = {}
        packet['comments'].append({'slide_id': None, 'key': '04', 'source_round': 'old-round', 'text': '旧批注需确认页面'})
        before = revision(self.p)
        self.assertEqual(apply_packet(self.p, packet)['files'], [])
        self.assertEqual(revision(self.p), before)
        self.assertEqual(len(inspect_packet(self.p, packet)['comments_pending']), 2)
        acknowledge(self.p, packet, comments=True)
        self.assertTrue(inspect_packet(self.p, packet)['already_processed'])

    def test_dry_run_writes_neither_source_nor_receipt(self):
        before = {str(p.relative_to(self.p)): p.read_bytes() for p in self.p.rglob('*') if p.is_file()}
        result = apply_packet(self.p, self.packet(), dry_run=True)
        after = {str(p.relative_to(self.p)): p.read_bytes() for p in self.p.rglob('*') if p.is_file()}
        self.assertTrue(result['files'])
        self.assertEqual(before, after)

    def test_unrelated_revision_can_rebase_but_same_field_cannot(self):
        packet = self.packet()
        other = self.m['slides'][1]
        apply_edits(self.p, {'schema': 1, 'project_id': self.m['project_id'], 'base_revision': self.m['revision'],
                           'changes': [{'slide_id': other['id'], 'fields': {}, 'notes': '另一页更新了。'}]})
        render_preview(self.p)
        self.assertEqual(inspect_packet(self.p, packet)['status'], 'ok')
        changed = copy.deepcopy(packet)
        changed['packet_id'] = 'packet-test-002'
        changed['changes'][0]['fields'][self.f['id']] = '别人已经修改了。'
        apply_packet(self.p, changed)
        report = inspect_packet(self.p, packet)
        self.assertEqual(report['status'], 'conflict')
        self.assertEqual(report['conflicts'][0]['before'], self.f['value'])
        self.assertEqual(report['conflicts'][0]['current'], '别人已经修改了。')
        with self.assertRaises(Conflict):
            apply_packet(self.p, packet)
        # After Codex manually resolves the conflict, acknowledge without reapplying old copy.
        acknowledge(self.p, packet, content=True, comments=True)
        self.assertTrue(inspect_packet(self.p, packet)['already_processed'])
        self.assertEqual(apply_packet(self.p, packet)['files'], [])
        self.assertIn('别人已经修改了。', (self.p / 'main_content.md').read_text())

    def test_stale_manifest_and_invalid_baselines_fail_without_changes(self):
        packet = self.packet()
        malformed = copy.deepcopy(packet)
        malformed['base_values'][self.s['id']] = []
        with self.assertRaises(EditError):
            inspect_packet(self.p, malformed)
        with self.assertRaises(EditError):
            acknowledge(self.p, packet)
        (self.p / 'notes/02_下一页.md').write_text('外部编辑。')
        with self.assertRaises(Conflict):
            inspect_packet(self.p, packet)
        render_preview(self.p)
        self.assertEqual(inspect_packet(self.p, packet)['status'], 'ok')


if __name__ == '__main__':
    unittest.main()
