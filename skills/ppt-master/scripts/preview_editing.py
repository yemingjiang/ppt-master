"""Source-backed text editing for review previews (no model calls)."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
import xml.etree.ElementTree as ET

from main_content_pipeline import parse_main_content

NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
MANIFEST = 'preview/editable_manifest.json'
MAIN_BLOCK = re.compile(r'^###\s+Slide\s+(\d+)\s+-\s+[^\n]*\n.*?(?=^###\s+Slide\s+\d+\s+-|\Z)', re.M | re.S)
NOTE_BLOCK = re.compile(r'^# (\d+)[^\n]*\n.*?(?=\n---\n# \d+|\Z)', re.M | re.S)


class EditError(ValueError):
    pass


class Conflict(EditError):
    pass


def atomic_write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(value)
        if path.exists():
            os.chmod(temp, path.stat().st_mode & 0o777)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def inside(project: Path, relative: str) -> Path:
    path = (project / relative).resolve()
    if not path.is_relative_to(project.resolve()):
        raise EditError('Path leaves the project directory')
    return path


def revision(project: Path) -> str:
    project = project.resolve()
    paths = [project / 'main_content.md', project / 'design_spec.md']
    paths += sorted((project / 'svg_output').glob('*.svg'))
    paths += sorted((project / 'notes').glob('*.md'))
    digest = hashlib.sha256()
    for path in paths:
        path = inside(project, str(path.relative_to(project)))
        digest.update(str(path.relative_to(project)).encode())
        digest.update(b'\0')
        digest.update(path.read_bytes() if path.exists() else b'<missing>')
        digest.update(b'\0')
    return digest.hexdigest()


def raw_notes(project: Path) -> dict:
    path = project / 'notes/total.md'
    if not path.exists():
        return {}
    return {m[1].zfill(2): m[0].split('\n', 1)[1].strip('\n') for m in NOTE_BLOCK.finditer(path.read_text())}


def display_text(node: ET.Element) -> str:
    if node.get('data-pm-multiline') == 'true':
        return '\n'.join([node.text or ''] + [c.text or '' for c in node])
    return ''.join(node.itertext())


def plain(value: str) -> str:
    # Manual line breaks are layout; spaces explicitly entered by the user remain.
    return value.replace('\r\n', '\n').replace('\n', '')


def simple_text(node: ET.Element) -> bool:
    return not list(node) or (node.get('data-pm-multiline') == 'true' and all(c.tag == f'{{{NS}}}tspan' and not list(c) for c in node))


def field_value(slide: dict, field: str) -> str:
    if field in ('title', 'takeaway'):
        return slide[field]
    if re.fullmatch(r'bullets\.\d+', field):
        return slide['bullets'][int(field.split('.')[1])]
    raise EditError('Unsupported content field: ' + field)


def prepare_manifest(project: Path) -> dict:
    """Assign stable IDs, and bind only unambiguous, exactly matching text nodes."""
    project = project.resolve()
    if not (project / 'main_content.md').exists():
        raise EditError('Create main_content.md before enabling editing')
    model = {s['key']: s for s in parse_main_content(project)['slides']}
    old_path = project / MANIFEST
    old = json.loads(old_path.read_text()) if old_path.exists() else {}
    from review_markdown import archive_manifest
    if old.get('revision') and old.get('slides'):
        archive_manifest(project, old)
    result = {'schema': 1, 'project_id': old.get('project_id', str(uuid.uuid4())), 'slides': []}
    ids = set()
    notes = raw_notes(project)
    for file in sorted((project / 'svg_output').glob('*.svg')):
        file = inside(project, str(file.relative_to(project)))
        match = re.match(r'(\d+)', file.stem)
        if not match or match[1].zfill(2) not in model:
            raise EditError('SVG has no matching main_content slide: ' + file.name)
        key = match[1].zfill(2)
        slide = model[key]
        original = file.read_text()
        tree = ET.fromstring(original)
        uid = tree.get('data-pm-slide') or str(uuid.uuid4())
        if uid in ids:
            raise EditError('Duplicate data-pm-slide; assign a new ID to copied slide: ' + file.name)
        ids.add(uid)
        tree.set('data-pm-slide', uid)
        nodes = list(tree.iter(f'{{{NS}}}text'))
        counts = Counter(plain(display_text(n)) for n in nodes)
        fields, readonly = [], []
        element_ids = Counter(n.get('id') for n in tree.iter() if n.get('id'))
        for node in nodes:
            value = display_text(node)
            field = node.get('data-pm-field')
            if not simple_text(node):
                readonly.append(value)
                continue
            if not field:
                candidates = [f'bullets.{i}' for i, b in enumerate(slide['bullets']) if b == plain(value)]
                if len(candidates) == 1 and counts[plain(value)] == 1:
                    field = candidates[0]
                elif not candidates and counts[plain(value)] == 1:
                    field = next((k for k in ('title', 'takeaway') if slide[k] == plain(value)), None)
            try:
                valid = field and field_value(slide, field) == plain(value)
            except (KeyError, IndexError, EditError):
                valid = False
            if not valid:
                readonly.append(value)
                continue
            node_id = node.get('id')
            if node_id and element_ids[node_id] > 1:
                raise EditError('Duplicate SVG element ID: ' + node_id)
            if not node_id:
                node_id = 'pm-text-' + uuid.uuid4().hex
                node.set('id', node_id)
            node.set('data-pm-field', field)
            fields.append({'id': node_id, 'field': field, 'value': value})
        updated = ET.tostring(tree, encoding='unicode')
        # Avoid serializing already registered pages on every preview rebuild.
        if updated != ET.tostring(ET.fromstring(original), encoding='unicode'):
            atomic_write(file, updated)
        result['slides'].append({'id': uid, 'key': key, 'svg': str(file.relative_to(project)),
                                 'title': slide['title'], 'takeaway': slide['takeaway'], 'fields': fields, 'readonly': readonly,
                                 'svg_markup': file.read_text(),
                                 'notes': notes.get(key, ''), 'notes_available': key in notes})
    result['revision'] = revision(project)
    result['review'] = archive_manifest(project, result)
    receipt_file = project / 'preview/review_receipts.json'
    records = json.loads(receipt_file.read_text()).get('packets', {}) if receipt_file.exists() else {}
    result['receipts'] = [{'packet_id': key, 'content_applied': value['content_applied'],
                           'comments_processed': value['comments_processed']} for key, value in records.items()]
    atomic_write(old_path, json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


def replace_section(document: str, pattern: re.Pattern, key: str, transform) -> str:
    matches = [m for m in pattern.finditer(document) if m[1].zfill(2) == key]
    if len(matches) != 1:
        raise EditError(f'Expected exactly one section for slide {key}')
    m = matches[0]
    return document[:m.start()] + transform(m[0]) + document[m.end():]


def replace_main_fields(block: str, old: dict, new: dict) -> str:
    for name, label in [('title', 'Title'), ('takeaway', 'Takeaway')]:
        if old[name] != new[name]:
            block, count = re.subn(rf'^- {label}:[^\n]*$', lambda m: '- ' + label + ': ' + new[name], block, flags=re.M)
            if count != 1:
                raise EditError('Missing or duplicate main_content field: ' + label)
    if old['title'] != new['title']:
        lines = block.splitlines(keepends=True)
        if lines[0].rstrip().endswith(' - ' + old['title']):
            lines[0] = lines[0].replace(' - ' + old['title'], ' - ' + new['title'])
        block = ''.join(lines)
    lines = block.splitlines(keepends=True)
    active, index = False, 0
    for i, line in enumerate(lines):
        if re.match(r'^- Bullets:\s*$', line):
            active = True
        elif re.match(r'^- [A-Za-z ]+:', line):
            active = False
        elif active and re.match(r'^\s+-\s+', line):
            if index < len(new['bullets']) and old['bullets'][index] != new['bullets'][index]:
                prefix = re.match(r'^\s+-\s+', line)[0]
                lines[i] = prefix + new['bullets'][index] + ('\n' if line.endswith('\n') else '')
            index += 1
    return ''.join(lines)


def sync_aliases(old: dict, new: dict, primary: set) -> None:
    """Maintain title/takeaway only when they exactly mirror a leading bullet sequence."""
    for alias in ('title', 'takeaway'):
        if alias in primary:
            continue
        for count in range(1, len(old['bullets']) + 1):
            if old[alias] == ''.join(old['bullets'][:count]):
                new[alias] = ''.join(new['bullets'][:count])
                break
    for i, value in enumerate(old['bullets']):
        if f'bullets.{i}' not in primary and old['bullets'].count(value) == 1:
            for alias in ('title', 'takeaway'):
                if alias in primary and value == old[alias]:
                    new['bullets'][i] = new[alias]
    if 'title' in primary and 'takeaway' not in primary and old['title'] == old['takeaway']:
        new['takeaway'] = new['title']


def write_node(node: ET.Element, value: str) -> None:
    lines = value.replace('\r\n', '\n').split('\n')
    for child in list(node):
        node.remove(child)
    node.text = lines[0]
    if len(lines) > 1:
        node.set('data-pm-multiline', 'true')
        for line in lines[1:]:
            ET.SubElement(node, f'{{{NS}}}tspan', {'x': node.get('x', '0'), 'dy': '1.4em'}).text = line
    else:
        node.attrib.pop('data-pm-multiline', None)


@contextmanager
def edit_lock(project: Path):
    lock = project / 'preview/.edit.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise Conflict('Another save is active. Retry; if it persists, check preview/.edit.lock.')
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def apply_edits(project: Path, package: dict, dry_run: bool = False) -> dict:
    project = project.resolve()
    if not isinstance(package, dict):
        raise EditError('Edit package must be a JSON object')
    with edit_lock(project):
        manifest = json.loads((project / MANIFEST).read_text())
        current_revision = revision(project)
        if package.get('schema') != 1 or package.get('project_id') != manifest['project_id']:
            raise EditError('This edit package belongs to a different project or schema')
        if package.get('base_revision') != current_revision or manifest['revision'] != current_revision:
            raise Conflict('Project changed since editing began. Inspect the original copied feedback against the current sources before applying it.')
        model = {s['key']: s for s in parse_main_content(project)['slides']}
        originals, writes, changed = {}, {}, []
        def read(relative):
            if relative not in originals:
                path = inside(project, relative)
                originals[relative] = path.read_text() if path.exists() else None
            return writes.get(relative, originals[relative]) or ''
        seen = set()
        changes = package.get('changes')
        if not isinstance(changes, list) or not changes:
            raise EditError('No changes supplied')
        for change in changes:
            if not isinstance(change, dict):
                raise EditError('Each slide change must be an object')
            uid = change.get('slide_id')
            if uid in seen:
                raise EditError('Duplicate slide edit')
            seen.add(uid)
            slide = next((s for s in manifest['slides'] if s['id'] == uid), None)
            if not slide:
                raise EditError('Unknown slide ID')
            key = slide['key']
            old, new = model[key], copy.deepcopy(model[key])
            fields = change.get('fields', {})
            if not isinstance(fields, dict):
                raise EditError('fields must be an object')
            tree = ET.fromstring(read(slide['svg']))
            primary, new_values = set(), {}
            for node_id, value in fields.items():
                binding = next((f for f in slide['fields'] if f['id'] == node_id), None)
                if not binding or not isinstance(value, str) or not plain(value).strip() or len(value) > 10000:
                    raise EditError('Invalid, empty, or unmapped text edit')
                value = value.replace('\r\n', '\n').replace('\r', '\n')
                if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', value):
                    raise EditError('Text contains unsupported control characters')
                fields[node_id] = value
                field = binding['field']
                if field in new_values and plain(new_values[field]) != plain(value):
                    raise EditError('Two text blocks disagree about the same source field')
                new_values[field] = value
                primary.add(field)
                if field.startswith('bullets.'):
                    new['bullets'][int(field.split('.')[1])] = plain(value)
                else:
                    new[field] = plain(value)
            sync_aliases(old, new, primary)
            if fields:
                for binding in slide['fields']:
                    value = fields.get(binding['id'])
                    if value is None and field_value(old, binding['field']) != field_value(new, binding['field']):
                        value = new_values.get(binding['field'], field_value(new, binding['field']))
                    if value is not None:
                        node = next((n for n in tree.iter(f'{{{NS}}}text') if n.get('id') == binding['id']), None)
                        if node is None:
                            raise Conflict('Mapped text node disappeared')
                        write_node(node, value)
                if old['title'] != new['title']:
                    title = tree.find(f'{{{NS}}}title')
                    if title is not None:
                        title.text = new['title']
                writes[slide['svg']] = ET.tostring(tree, encoding='unicode')
                main = read('main_content.md')
                writes['main_content.md'] = replace_section(main, MAIN_BLOCK, key, lambda b: replace_main_fields(b, old, new))
                # Preserve chapter headings and all unrelated design-spec material.
                spec = read('design_spec.md')
                pattern = re.compile(r'^#### Slide (\d+)[^\n]*\n.*?(?=^#{1,4} |\Z)', re.M | re.S)
                if any(m[1].zfill(2) == key for m in pattern.finditer(spec)):
                    def spec_update(block):
                        replacements = {old[k]: new[k] for k in ('title', 'takeaway') if old[k] != new[k]}
                        replacements.update({a: b for a, b in zip(old['bullets'], new['bullets']) if a != b and old['bullets'].count(a) == 1})
                        output = []
                        for line in block.splitlines(keepends=True):
                            for before, after in replacements.items():
                                if line.rstrip().endswith(before):
                                    prefix = line.rstrip()[:-len(before)]
                                    if prefix.startswith(('#### Slide ', '- **Title**:', '- **Takeaway**:', '  - ')):
                                        line = prefix + after + ('\n' if line.endswith('\n') else '')
                                        break
                            output.append(line)
                        return ''.join(output)
                    writes['design_spec.md'] = replace_section(spec, pattern, key, spec_update)
            if 'notes' in change:
                value = change['notes']
                if not isinstance(value, str) or len(value) > 200000:
                    raise EditError('Invalid notes')
                value = value.replace('\r\n', '\n').replace('\r', '\n')
                if not slide['notes_available']:
                    raise EditError('Create this slide section in notes/total.md before editing notes')
                if re.search(r'^# \d+', value, re.M) or '\n---\n' in value:
                    raise EditError('Notes cannot contain slide headings or the reserved slide separator; use *** for a Markdown rule')
                total = read('notes/total.md')
                writes['notes/total.md'] = replace_section(total, NOTE_BLOCK, key, lambda b: b.split('\n', 1)[0] + '\n\n' + value.strip('\n') + '\n')
                relative = 'notes/' + Path(slide['svg']).stem + '.md'
                read(relative)
                writes[relative] = value.strip('\n') + '\n'
            changed.append(uid)
        writes = {k: v for k, v in writes.items() if v != originals[k]}
        result = {'status': 'ok', 'dry_run': dry_run, 'changed_slides': changed, 'files': sorted(writes)}
        if dry_run:
            return result
        if revision(project) != current_revision:
            raise Conflict('Project changed during save; no changes applied')
        history = project / 'preview/edit_history' / (str(time.time_ns()) + '-' + uuid.uuid4().hex[:8])
        for relative in writes:
            if originals[relative] is not None:
                target = history / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(originals[relative])
        if writes:
            atomic_write(history / 'changes.json', json.dumps(package, ensure_ascii=False, indent=2))
        committed = []
        try:
            for relative, value in writes.items():
                atomic_write(inside(project, relative), value)
                committed.append(relative)
            updated = prepare_manifest(project)
        except Exception:
            for relative in reversed(committed):
                if originals[relative] is None:
                    inside(project, relative).unlink(missing_ok=True)
                else:
                    atomic_write(inside(project, relative), originals[relative])
            atomic_write(project / MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
            raise
        # Existing final exports are never silently regenerated.
        if writes and ((project / 'exports').exists() or (project / 'html_output').exists() or (project / 'svg_final').exists()):
            atomic_write(project / 'preview/final_stale.json', json.dumps({'revision': updated['revision'], 'reason': 'review content edited'}, indent=2))
        result.update({'manifest': updated, 'history': str(history) if writes else None})
        return result


def inject_editor(document: str, manifest: dict) -> str:
    assets = Path(__file__).parent / 'preview_editor'
    css = (assets / 'editor.css').read_text()
    js = (assets / 'clipboard.js').read_text() + '\n' + (assets / 'editor.js').read_text()
    payload = json.dumps(manifest, ensure_ascii=False).replace('</', '<\\/')
    addition = '<style>' + css + '</style><script>const editableManifest = ' + payload + ';</script><script>' + js + '</script>'
    return document.replace('</body>', addition + '</body>')
