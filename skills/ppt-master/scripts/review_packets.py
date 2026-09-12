"""Validate pasted offline feedback and track exactly what Codex has processed."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

from preview_editing import MANIFEST, Conflict, EditError, apply_edits, atomic_write, edit_lock, prepare_manifest, revision

RECEIPTS = 'preview/review_receipts.json'


def parse_packet(text: str, project: Path | None = None) -> dict:
    # Quoted Markdown values can end with a meaningful space or empty quoted line.
    text = text.lstrip().rstrip('\r\n')
    if text.startswith(('# PPT 修改清单\n', '# PPT Change List\n')):
        if project is None:
            raise EditError('A project path is required to resolve the change list references')
        from review_markdown import parse_markdown
        return parse_markdown(project.resolve(), text)
    if not text.startswith('{'):
        blocks = re.findall(r'^```json\s*\n(.*?)^```\s*$', text, re.M | re.S)
        if len(blocks) != 1:
            raise EditError('Paste the complete Markdown change list or legacy JSON record from Copy all changes')
        text = blocks[0]
    package = json.loads(text)
    if not isinstance(package, dict):
        raise EditError('Review payload must be a JSON object')
    return package


def digest(package: dict) -> str:
    return hashlib.sha256(json.dumps(package, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def receipts(project: Path) -> dict:
    file = project / RECEIPTS
    return json.loads(file.read_text()) if file.exists() else {'schema': 1, 'packets': {}}


def validate(project: Path, package: dict) -> tuple[dict, dict | None]:
    if package.get('schema') != 2 or package.get('kind') != 'ppt-master-review':
        raise EditError('Expected a schema 2 ppt-master-review clipboard record')
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}', str(package.get('packet_id', ''))):
        raise EditError('Missing or invalid packet ID')
    manifest = json.loads((project / MANIFEST).read_text())
    if package.get('project_id') != manifest['project_id']:
        raise EditError('This feedback belongs to a different project')
    if not isinstance(package.get('changes'), list) or not isinstance(package.get('comments'), list):
        raise EditError('changes and comments must be lists')
    if not isinstance(package.get('base_values'), dict) or not isinstance(package.get('base_revision'), str):
        raise EditError('Missing source baseline')
    if not package['changes'] and not package['comments']:
        raise EditError('There are no edits or comments to process')
    seen = set()
    for change in package['changes']:
        if not isinstance(change, dict) or not isinstance(change.get('slide_id'), str) or not isinstance(change.get('fields', {}), dict):
            raise EditError('Invalid slide edit')
        uid = change['slide_id']
        if uid in seen:
            raise EditError('Duplicate slide edit')
        seen.add(uid)
        base = package['base_values'].get(uid)
        if not isinstance(base, dict) or not isinstance(base.get('fields', {}), dict):
            raise EditError('Every slide edit needs its original values')
        if not change.get('fields') and 'notes' not in change:
            raise EditError('Empty slide edit')
    for comment in package['comments']:
        if not isinstance(comment, dict) or not isinstance(comment.get('text'), str) or not comment['text'].strip():
            raise EditError('Invalid comment')
        if len(comment['text']) > 200000:
            raise EditError('Comment is too long')
    record = receipts(project)['packets'].get(package['packet_id'])
    if record and record['digest'] != digest(package):
        raise Conflict('The same packet ID was reused with different contents; do not modify an existing packet')
    return manifest, record


def inspect_packet(project: Path, package: dict) -> dict:
    project = project.resolve()
    manifest, record = validate(project, package)
    current_revision = revision(project)
    problems, pending = [], []
    if not record or not record['content_applied']:
        if manifest['revision'] != current_revision:
            raise Conflict('Source files changed. Rebuild the offline preview, then inspect this original packet again.')
        seen = set()
        for change in package['changes']:
            if not isinstance(change, dict) or not isinstance(change.get('fields', {}), dict):
                raise EditError('Invalid slide edit')
            uid = change.get('slide_id')
            if uid in seen:
                raise EditError('Duplicate slide edit')
            seen.add(uid)
            slide = next((s for s in manifest['slides'] if s['id'] == uid), None)
            if not slide:
                problems.append({'slide_id': uid, 'reason': 'slide removed or identity changed'})
                continue
            base = package['base_values'].get(uid, {})
            item = {'slide_id': uid, 'fields': {}}
            for node_id, after in change.get('fields', {}).items():
                field = next((f for f in slide['fields'] if f['id'] == node_id), None)
                before = base.get('fields', {}).get(node_id)
                if not isinstance(after, str) or not isinstance(before, dict) or not isinstance(before.get('value'), str):
                    raise EditError('Every text edit needs its original value and field binding')
                if not field or before.get('field') != field['field']:
                    problems.append({'slide_id': uid, 'field_id': node_id, 'reason': 'text removed or remapped', 'edited': after})
                elif field['value'] == after:
                    continue
                elif field['value'] != before['value']:
                    problems.append({'slide_id': uid, 'field_id': node_id, 'before': before['value'], 'current': field['value'], 'edited': after})
                else:
                    item['fields'][node_id] = after
            if 'notes' in change:
                after = change['notes']
                before = base.get('notes')
                if not isinstance(after, str) or not isinstance(before, str):
                    raise EditError('A notes edit needs its original Markdown')
                if not slide['notes_available']:
                    problems.append({'slide_id': uid, 'reason': 'notes section removed', 'edited': after})
                elif slide['notes'] == after:
                    pass
                elif slide['notes'] != before:
                    problems.append({'slide_id': uid, 'field_id': 'notes', 'before': before, 'current': slide['notes'], 'edited': after})
                else:
                    item['notes'] = after
            if item['fields'] or 'notes' in item:
                pending.append(item)
    comments = [] if record and record['comments_processed'] else package['comments']
    return {'status': 'conflict' if problems else 'ok', 'packet_id': package['packet_id'],
            'conflicts': problems, 'pending_changes': pending, 'comments_pending': comments,
            'current_revision': current_revision,
            'already_processed': bool(record and record['content_applied'] and record['comments_processed'])}


def acknowledge(project: Path, package: dict, content: bool = False, comments: bool = False) -> dict:
    """Explicit processing receipt; comments are never acknowledged merely by applying text."""
    project = project.resolve()
    if not content and not comments:
        raise EditError('Select --content-processed and/or --comments-processed after actually handling that feedback')
    with edit_lock(project):
        _, record = validate(project, package)
        all_receipts = receipts(project)
        record = record or {'digest': digest(package), 'content_applied': not package['changes'], 'comments_processed': not package['comments']}
        record['content_applied'] |= content
        record['comments_processed'] |= comments
        all_receipts['packets'][package['packet_id']] = record
        atomic_write(project / RECEIPTS, json.dumps(all_receipts, ensure_ascii=False, indent=2) + '\n')
    return {'status': 'ok', 'packet_id': package['packet_id'], **record}


def apply_packet(project: Path, package: dict, dry_run: bool = False) -> dict:
    project = project.resolve()
    report = inspect_packet(project, package)
    if report['conflicts']:
        raise Conflict(json.dumps(report, ensure_ascii=False))
    if report['pending_changes']:
        native = {'schema': 1, 'project_id': package['project_id'], 'base_revision': report['current_revision'],
                  'changes': copy.deepcopy(report['pending_changes'])}
        applied = apply_edits(project, native, dry_run)
        report['files'] = applied['files']
    else:
        report['files'] = []
    report['dry_run'] = dry_run
    if not dry_run:
        acknowledge(project, package, content=True)
        # Include new receipts in the next generated offline document.
        prepare_manifest(project)
    return report
