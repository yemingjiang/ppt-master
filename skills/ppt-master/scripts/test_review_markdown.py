"""Cross-language Markdown round-trips, compact note diffs and stable identities."""
import copy
import json
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

from build_preview_html import render_preview
from preview_editing import Conflict, EditError, MANIFEST, apply_edits, revision
from review_markdown import patch_notes
from review_packets import acknowledge, apply_packet, inspect_packet, parse_packet
from test_preview_editing import fixture

FORMATTER = Path(__file__).parent / 'preview_editor/clipboard.js'


def node(code, data):
    return subprocess.check_output(['node', '-e', code, str(FORMATTER.resolve())], input=json.dumps(data, ensure_ascii=False), text=True)


def formatted(packet, manifest, zh=True):
    return node("globalThis.crypto=require('crypto').webcrypto; const f=require(process.argv[1]); const d=JSON.parse(require('fs').readFileSync(0,'utf8')); f.format(d.packet,d.manifest,'示例',d.zh).then(s=>process.stdout.write(s));", {'packet': packet, 'manifest': manifest, 'zh': zh})


class MarkdownReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.p = Path(self.temp.name)
        fixture(self.p)
        self.notes = '\n\n'.join(f'第{i}段：保留完整的组织背景与讲述细节。' for i in range(24)) + '\n\n要点：目标\n\n时长：1分'
        path = self.p / 'notes/total.md'
        text = path.read_text()
        path.write_text(text[:text.index('\n\n') + 2] + self.notes + text[text.index('\n---\n'):])
        render_preview(self.p)
        self.m = self.manifest()
        self.s = self.m['slides'][0]
        self.f = self.s['fields'][1]

    def manifest(self):
        return json.loads((self.p / MANIFEST).read_text())

    def packet(self, notes=None):
        return {'schema': 2, 'kind': 'ppt-master-review', 'packet_id': 'r0123456789abcdef',
                'project_id': self.m['project_id'], 'base_revision': self.m['revision'],
                'changes': [{'slide_id': self.s['id'], 'key': '01', 'title': self.s['title'], 'fields': {self.f['id']: '越要说清标准。'},
                             'notes': notes if notes is not None else self.notes.replace('第3段：', '新增判断：').replace('第19段：', '更明确的判断：')}],
                'base_values': {self.s['id']: {'fields': {self.f['id']: {'value': self.f['value'], 'field': self.f['field']}}, 'notes': self.notes}},
                'comments': [{'slide_id': self.s['id'], 'key': '01', 'title': self.s['title'], 'text': '布局再简洁一点。\n\n## 保留我的 Markdown\n```json\n{"示例":"仅为批注"}\n```\n> 引用\n末尾空格  \n'}]}

    def test_compact_notes_and_literal_markdown_roundtrip(self):
        packet = self.packet()
        for zh in (True, False):
            with self.subTest(zh=zh):
                text = formatted(packet, self.m, zh)
                self.assertEqual(parse_packet(text, self.p), packet)
                for full_id in (self.s['id'], self.f['id'], self.m['project_id']):
                    self.assertNotIn(full_id, text)
                self.assertNotIn('第10段', text)
                self.assertLess(len(text), len(json.dumps(packet, ensure_ascii=False, indent=2)) // 2)
                self.assertIn('@@ ', text)
        apply_packet(self.p, parse_packet(text, self.p))
        self.assertIn('新增判断', (self.p / 'notes/total.md').read_text())
        self.assertIn('第10段', (self.p / 'notes/total.md').read_text())

    def test_full_rewrite_empty_notes_and_multiline_text(self):
        for notes in ('全部重写。\n\n时长：2分\n', ''):
            packet = self.packet(notes)
            packet['changes'][0]['fields'][self.f['id']] = '第一行\n\n最后一行  \n'
            text = formatted(packet, self.m)
            self.assertIn('### 备注全文', text)
            self.assertNotIn('第10段', text)
            self.assertEqual(parse_packet(text, self.p), packet)

    def test_post_copy_source_change_retains_baseline_and_detects_conflict(self):
        packet = self.packet()
        text = formatted(packet, self.m)
        other = self.m['slides'][1]
        apply_edits(self.p, {'schema': 1, 'project_id': self.m['project_id'], 'base_revision': self.m['revision'],
                            'changes': [{'slide_id': other['id'], 'fields': {}, 'notes': '另一页变化。'}]})
        render_preview(self.p)
        self.assertEqual(parse_packet(text, self.p), packet)
        self.assertEqual(inspect_packet(self.p, parse_packet(text, self.p))['status'], 'ok')
        competing = copy.deepcopy(packet)
        competing['packet_id'] = 'r1111111111111111'
        competing['changes'][0]['notes'] = '别人已修改此页备注。'
        apply_packet(self.p, competing)
        report = inspect_packet(self.p, parse_packet(text, self.p))
        self.assertEqual(report['status'], 'conflict')
        self.assertEqual(report['conflicts'][0]['field_id'], 'notes')

    def test_new_preview_uses_old_note_baseline_and_preserves_receipts(self):
        packet = self.packet()
        text = formatted(packet, self.m)
        apply_packet(self.p, packet)
        render_preview(self.p)
        newer = self.manifest()
        later = self.packet(self.notes.replace('第4段：', '复制后新增：'))
        later['base_revision'] = newer['revision']
        later['packet_id'] = 'r2222222222222222'
        copied = formatted(later, newer)
        self.assertIn('### 备注修改 [v1]', copied)
        self.assertEqual(parse_packet(copied, self.p), later)
        acknowledge(self.p, parse_packet(text, self.p), comments=True)
        self.assertTrue(inspect_packet(self.p, parse_packet(text, self.p))['already_processed'])
        self.assertEqual(apply_packet(self.p, parse_packet(text, self.p))['files'], [])
        with self.assertRaises(Conflict):
            apply_packet(self.p, parse_packet(text.replace('越要说清标准。', '换一种表达。'), self.p))

    def test_unarchived_browser_baseline_has_readable_lossless_fallback(self):
        packet = self.packet('保留浏览器的新版本。')
        packet['base_values'][self.s['id']]['notes'] = '老浏览器里才有的原稿。\n\n**备注**'
        packet['base_values'][self.s['id']]['fields'][self.f['id']]['field'] = 'bullets.99'
        text = formatted(packet, self.m)
        self.assertIn('### 备注替换', text)
        self.assertNotIn('base_values', text)
        self.assertEqual(parse_packet(text, self.p), packet)
        self.assertEqual(inspect_packet(self.p, packet)['status'], 'conflict')

    def test_reordered_pages_resolve_by_stable_id_and_missing_baselines_fail(self):
        packet = self.packet()
        text = formatted(packet, self.m)
        a, b = self.p / 'svg_output/01_开场.svg', self.p / 'svg_output/02_下一页.svg'
        av, bv = a.read_text(), b.read_text()
        a.write_text(bv)
        b.write_text(av)
        render_preview(self.p)
        self.assertEqual(parse_packet(text, self.p), packet)
        self.assertEqual(self.manifest()['slides'][1]['id'], self.s['id'])
        (self.p / 'preview/review_baselines/v1.json').unlink()
        with self.assertRaises(EditError):
            parse_packet(text, self.p)

    def test_malformed_diff_and_unknown_references_never_write(self):
        packet = self.packet()
        text = formatted(packet, self.m)
        before = revision(self.p)
        for altered in (text.replace('[s1]', '[s999]'), text.replace('[t2]', '[t999]'),
                        text.replace('-第3段：', '-错误段落：'), text.replace('```diff', '```json'),
                        text.replace('版本：v1', '版本：v999')):
            with self.subTest(altered=altered[:40]), self.assertRaises(EditError):
                parse_packet(altered, self.p)
        self.assertEqual(revision(self.p), before)

    def test_comment_only_and_legacy(self):
        packet = self.packet()
        packet['changes'], packet['base_values'] = [], {}
        text = formatted(packet, self.m)
        self.assertNotIn('### 正文', text)
        self.assertNotIn('### 备注', text)
        self.assertEqual(parse_packet(text, self.p), packet)
        packet['comments'] = [{'slide_id': None, 'key': '04', 'title': '待确认页面', 'text': '旧版批注。'}]
        self.assertEqual(parse_packet(formatted(packet, self.m), self.p), packet)

    def test_diff_positions_with_insertions_deletions_and_repeated_lines(self):
        random.seed(42)
        examples = [('', '新增\n'), ('a\n', ''), ('a\nb', 'new\na\nb'), ('a\nb', 'a\nb\nnew')]
        for _ in range(80):
            old = [random.choice(['a', 'b', '', '相同段落', '> quote', '```']) for _ in range(random.randint(1,35))]
            new = old[:]
            for _ in range(6):
                start = random.randint(0,len(new))
                new[start:start+random.randint(0,3)] = [random.choice(['a','新段落','']) for _ in range(random.randint(0,3))]
            examples.append(('\n'.join(old), '\n'.join(new)))
        patches = json.loads(node("const f=require(process.argv[1]),d=JSON.parse(require('fs').readFileSync(0,'utf8')); console.log(JSON.stringify(d.map(([a,b])=>f.diff(a,b))));", examples))
        for (before,after), patch in zip(examples,patches):
            with self.subTest(before=before, after=after):
                self.assertEqual(patch_notes(before, patch) if patch else before, after)


if __name__ == '__main__':
    unittest.main()
