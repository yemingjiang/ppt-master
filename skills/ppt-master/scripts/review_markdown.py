"""Compact Markdown feedback backed by immutable project-local text snapshots."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote

from preview_editing import Conflict, EditError, atomic_write

INDEX = 'preview/review_index.json'
BASELINES = 'preview/review_baselines'


def archive_manifest(project: Path, manifest: dict) -> dict:
    """Keep short identities stable and retain text baselines without copying SVG markup."""
    path = project / INDEX
    index = json.loads(path.read_text()) if path.exists() else {
        'project_id': manifest['project_id'],
        'project_ref': 'p' + hashlib.sha256(manifest['project_id'].encode()).hexdigest()[:12],
        'versions': {}, 'slides': {}, 'note_versions': {}, 'field_versions': {},
    }
    if index['project_id'] != manifest['project_id']:
        raise EditError('Review index belongs to another project; preserve the matching manifest and index together')
    rev = manifest['revision']
    version = index['versions'].setdefault(rev, 'v' + str(len(index['versions']) + 1))
    snapshots = []
    for slide in manifest['slides']:
        uid = slide['id']
        identity = index['slides'].setdefault(uid, {'ref': 's' + str(len(index['slides']) + 1), 'fields': {}})
        fields = []
        for field in slide['fields']:
            node = field['id']
            ref = identity['fields'].setdefault(node, 't' + str(len(identity['fields']) + 1))
            fields.append({**field, 'ref': ref})
            index['field_versions'].setdefault(uid, {}).setdefault(node, {})[field['field']] = version
        if slide['notes_available']:
            note_hash = hashlib.sha256(slide['notes'].encode()).hexdigest()
            index['note_versions'].setdefault(uid, {})[note_hash] = version
        snapshots.append({k: slide[k] for k in ('id', 'key', 'title', 'notes', 'notes_available')} | {'ref': identity['ref'], 'fields': fields})
    snapshot = {'project_id': manifest['project_id'], 'revision': rev, 'version': version, 'slides': snapshots}
    target = project / BASELINES / (version + '.json')
    if target.exists():
        if json.loads(target.read_text()) != snapshot:
            raise Conflict('A review baseline changed without a source revision change; keep archived baselines immutable')
    else:
        atomic_write(target, json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n')
    serialized = json.dumps(index, ensure_ascii=False, indent=2) + '\n'
    if not path.exists() or path.read_text() != serialized:
        atomic_write(path, serialized)
    return {**index, 'version_ref': version}


def patch_notes(before: str, diff: str) -> str:
    """Apply exact positional hunks only to the archived baseline, never fuzzily to current notes."""
    original = before.split('\n') if before else []
    lines = diff.split('\n')
    output, cursor, pos, hunks = [], 0, 0, 0
    while pos < len(lines):
        match = re.fullmatch(r'@@ -(\d+),(\d+) \+(\d+),(\d+) @@', lines[pos])
        if not match:
            raise EditError('Invalid notes diff header; paste the complete copied record')
        old_start, old_count, new_start, new_count = map(int, match.groups())
        start = old_start - 1 if old_count else old_start
        if start < cursor or start > len(original):
            raise EditError('Notes diff has overlapping or invalid line positions')
        output.extend(original[cursor:start])
        expected_new = len(output) + (1 if new_count else 0)
        if new_start != expected_new:
            raise EditError('Notes diff has inconsistent new line positions')
        pos += 1
        removed, added = [], []
        while pos < len(lines) and not lines[pos].startswith('@@ '):
            line = lines[pos]
            if not line or line[0] not in ' +-':
                raise EditError('Invalid notes diff line')
            if line[0] in ' -':
                removed.append(line[1:])
            if line[0] in ' +':
                added.append(line[1:])
            pos += 1
        if len(removed) != old_count or len(added) != new_count or original[start:start + old_count] != removed:
            raise Conflict('Notes diff does not match its archived baseline; retain the copied text and compare it in Codex')
        output.extend(added)
        cursor = start + old_count
        hunks += 1
    if not hunks:
        raise EditError('Empty notes diff')
    return '\n'.join(output + original[cursor:])


def parse_markdown(project: Path, text: str) -> dict:
    index_file = project / INDEX
    if not index_file.exists():
        raise EditError('Missing review index. Use the originating project with its preview/review_index.json and review_baselines directory')
    index = json.loads(index_file.read_text())
    lines = text.replace('\r\n', '\n').strip('\n').split('\n')
    if lines[0] not in ('# PPT 修改清单', '# PPT Change List'):
        raise EditError('Expected a complete PPT change list')
    pos = 1

    def skip_blank():
        nonlocal pos
        while pos < len(lines) and not lines[pos].strip():
            pos += 1

    def expect(pattern, message):
        nonlocal pos
        skip_blank()
        match = re.fullmatch(pattern, lines[pos]) if pos < len(lines) else None
        if not match:
            raise EditError(message)
        pos += 1
        return match

    project_ref = expect(r'(?:项目：|Project: ).* \[(p[0-9a-f]+)\]', 'Missing project reference')[1]
    if project_ref != index['project_ref']:
        raise EditError('This change list belongs to a different project')
    header = expect(r'(?:版本：|Version: )(v\d+)[｜|](?:修改记录：|Record: )([A-Za-z0-9_-]{8,100})', 'Missing version or record ID')
    version, packet_id = header.groups()
    cache = {}

    def baseline(ref):
        if not re.fullmatch(r'v\d+', ref):
            raise EditError('Invalid version reference')
        if ref not in cache:
            path = project / BASELINES / (ref + '.json')
            if not path.exists():
                raise EditError(f'Missing archived baseline {ref}; restore the originating project snapshot before processing this record')
            cache[ref] = json.loads(path.read_text())
            if cache[ref]['project_id'] != index['project_id']:
                raise EditError('Archived baseline belongs to another project')
        return cache[ref]

    def slide_baseline(uid, ref):
        slide = next((s for s in baseline(ref)['slides'] if s['id'] == uid), None)
        if not slide:
            raise EditError(f'Slide missing from baseline {ref}')
        return slide

    def quoted():
        nonlocal pos
        values = []
        while pos < len(lines) and lines[pos].startswith('> '):
            values.append(lines[pos][2:])
            pos += 1
        if not values:
            raise EditError('Expected quoted content; paste the complete copied record')
        return '\n'.join(values)

    def value(label):
        nonlocal pos
        labels = ('原：', 'Before: ') if label == 'before' else ('改：', 'After: ')
        skip_blank()
        prefix = next((p for p in labels if pos < len(lines) and lines[pos].startswith(p)), None)
        if prefix is None:
            raise EditError('Missing original or edited text')
        tail = lines[pos][len(prefix):]
        pos += 1
        return tail if tail else quoted()

    result = {'schema': 2, 'kind': 'ppt-master-review', 'project_id': index['project_id'],
              'packet_id': packet_id, 'base_revision': baseline(version)['revision'],
              'changes': [], 'base_values': {}, 'comments': []}
    seen = set()
    while True:
        skip_blank()
        if pos == len(lines):
            break
        page = expect(r'## (\S+) (.+) \[(s\d+|S:[^\]\s]+|legacy)\]', 'Invalid slide heading')
        key, title, ref = page.groups()
        identity = None
        if ref == 'legacy':
            uid = None
        elif ref.startswith('S:'):
            uid = unquote(ref[2:])
        else:
            uid, identity = next(((uid, s) for uid, s in index['slides'].items() if s['ref'] == ref), (None, None))
            if uid is None:
                raise EditError('Unknown stable slide reference: ' + ref)
        if uid is not None and uid in seen:
            raise EditError('Duplicate slide in change list')
        seen.add(uid)
        change, old = {'slide_id': uid, 'key': key, 'title': title, 'fields': {}}, {'fields': {}}
        sections = set()
        while True:
            skip_blank()
            if pos == len(lines) or lines[pos].startswith('## '):
                break
            section = expect(r'### (正文|Text|备注修改|Notes changes|备注全文|Full notes|备注替换|Notes replacement|批注|Comment)(?: \[([^\]]+)\])?', 'Invalid change section')
            kind, token = section.groups()
            if kind in ('正文', 'Text'):
                if uid is None or token is None:
                    raise EditError('Text edits require a stable text reference')
                if token.startswith('T:'):
                    match = re.fullmatch(r'T:([^;]+);F:(.+)', token)
                    if not match:
                        raise EditError('Invalid fallback text identity')
                    node_id, binding = map(unquote, match.groups())
                else:
                    match = re.fullmatch(r'(t\d+)(?:@(v\d+))?', token)
                    if not match or identity is None:
                        raise EditError('Invalid text reference')
                    node_id = next((n for n, t in identity['fields'].items() if t == match[1]), None)
                    archived = slide_baseline(uid, match[2] or version)
                    field = next((f for f in archived['fields'] if f['id'] == node_id), None)
                    if field is None:
                        raise EditError('Text reference missing from its baseline')
                    binding = field['field']
                if node_id in change['fields']:
                    raise EditError('Duplicate text edit')
                before, after = value('before'), value('after')
                old['fields'][node_id] = {'value': before, 'field': binding}
                change['fields'][node_id] = after
            elif kind in ('批注', 'Comment'):
                if 'comment' in sections or token:
                    raise EditError('Duplicate or invalid comment section')
                sections.add('comment')
                result['comments'].append({'slide_id': uid, 'key': key, 'title': title, 'text': quoted()})
            else:
                if uid is None or 'notes' in sections:
                    raise EditError('Duplicate notes or notes without a stable slide identity')
                sections.add('notes')
                if kind in ('备注替换', 'Notes replacement'):
                    if token:
                        raise EditError('Unexpected version for explicit notes replacement')
                    before, after = value('before'), value('after')
                else:
                    archived = slide_baseline(uid, token or version)
                    if not archived['notes_available']:
                        raise EditError('Notes missing from archived baseline')
                    before = archived['notes']
                    if kind in ('备注全文', 'Full notes'):
                        after = quoted()
                    else:
                        expect(r'```diff', 'Missing notes diff block')
                        start = pos
                        while pos < len(lines) and lines[pos] != '```':
                            pos += 1
                        if pos == len(lines):
                            raise EditError('Unclosed notes diff block')
                        after = patch_notes(before, '\n'.join(lines[start:pos]))
                        pos += 1
                old['notes'], change['notes'] = before, after
        if change['fields'] or 'notes' in change:
            result['changes'].append(change)
            result['base_values'][uid] = old
        elif not sections:
            raise EditError('Empty slide section')
    return result
