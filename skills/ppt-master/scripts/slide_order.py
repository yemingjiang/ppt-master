"""Plan a source-backed slide permutation without guessing page identity."""
from __future__ import annotations

import re
from pathlib import Path
import xml.etree.ElementTree as ET

from preview_editing import Conflict, EditError, NS


def validate_order(order: dict, current: list[str]) -> list[str] | None:
    if not isinstance(order, dict) or set(order) != {'before', 'after'}:
        raise EditError('Page order needs complete before/after slide IDs')
    before, after = order['before'], order['after']
    if any(not isinstance(v, list) or any(not isinstance(uid, str) for uid in v)
           or len(v) != len(set(v)) for v in (before, after)):
        raise EditError('Page order must contain unique slide IDs')
    if set(before) != set(after):
        raise EditError('Reordering cannot add or remove pages')
    if set(after) != set(current):
        raise Conflict('Pages were added, removed or replaced; reconcile the complete page order in Codex')
    if after == current:
        return None
    if before != current:
        raise Conflict('The page order changed since this draft; compare original/current/requested order in Codex')
    return after


def reorder_blocks(text: str, pattern: str, keys: list[str], numbers: dict[str, str], *, required=False) -> str:
    """Permute page blocks within existing section slots, preserving surrounding chapters."""
    matches = list(re.finditer(pattern, text, re.M | re.S))
    if not matches:
        if required:
            raise EditError('Missing numbered slide sections; repair the source before reordering')
        return text
    blocks = {m[1].zfill(2): m[0] for m in matches}
    if len(blocks) != len(matches) or set(blocks) != set(keys):
        raise EditError('Numbered sections do not match the complete deck; repair them before reordering')
    output, cursor = [], 0
    for slot, key in zip(matches, keys):
        block = blocks[key]
        # The first capture is the page number in the section heading.
        source = next(m for m in matches if m[1].zfill(2) == key)
        start, end = source.start(1)-source.start(), source.end(1)-source.start()
        block = block[:start] + numbers[key] + block[end:]
        output.extend((text[cursor:slot.start()], block.rstrip('\n') + '\n\n'))
        cursor = slot.end()
    return ''.join(output) + text[cursor:]


def plan_order(project: Path, manifest: dict, after: list[str], read) -> dict[str, str | None]:
    """Return all writes/deletions for the existing edit transaction and rollback."""
    by_id = {s['id']: s for s in manifest['slides']}
    slides = [by_id[uid] for uid in after]
    keys = [s['key'] for s in slides]
    numbers = {key: str(i+1).zfill(2) for i, key in enumerate(keys)}
    writes = {}
    moves = {}
    for slide in slides:
        old = slide['svg']
        stem = Path(old).stem
        new_stem = re.sub(r'^\d+', numbers[slide['key']], stem)
        new = 'svg_output/' + new_stem + '.svg'
        moves[old] = new
        markup = read(old)
        tree = ET.fromstring(markup)
        numbered = list(tree.iter(f'{{{NS}}}text'))
        numbered = [n for n in numbered if n.get('data-pm-page-number') == 'true']
        if numbered:
            for node in numbered:
                if list(node):
                    raise EditError('Page-number binding must be a plain text node')
                node.text = numbers[slide['key']]
            markup = ET.tostring(tree, encoding='unicode')
        writes[new] = markup
        note_old, note_new = 'notes/' + stem + '.md', 'notes/' + new_stem + '.md'
        if (project / note_old).exists() or read(note_old):
            moves[note_old] = note_new
            writes[note_new] = read(note_old)
    if len(set(moves.values())) != len(moves):
        raise EditError('Renumbering would create duplicate filenames')
    for old, new in moves.items():
        if new != old and (project / new).exists() and new not in moves:
            raise Conflict('Renumbering would overwrite an unrelated file: ' + new)
        if old not in writes:
            writes[old] = None
    writes['main_content.md'] = reorder_blocks(read('main_content.md'),
        r'^### Slide (\d+)[^\n]*\n.*?(?=^#{1,3} |\Z)', keys, numbers, required=True)
    writes['design_spec.md'] = reorder_blocks(read('design_spec.md'),
        r'^#### Slide (\d+)[^\n]*\n.*?(?=^#{1,4} |\Z)', keys, numbers)
    if (project / 'notes/total.md').exists():
        writes['notes/total.md'] = reorder_blocks(read('notes/total.md'),
            r'^# (\d+)[^\n]*\n.*?(?=\n---\n# \d+|\Z)', keys, numbers, required=True)
    if (project / 'asset_manifest.md').exists():
        # Keep the global asset index intact; remap its explicit Used In page tokens.
        text = reorder_blocks(read('asset_manifest.md'),
            r'^### Slide (\d+)[^\n]*\n.*?(?=^#{1,3} |\Z)', keys, numbers)
        lines = text.splitlines(keepends=True)
        for i, line in enumerate(lines):
            if line.startswith('|'):
                cells = line.split('|')
                if len(cells) == 8:  # Generated global asset index's Used In column.
                    cells[-2] = re.sub(r'(^\s*|,\s*)(\d+)(?= )',
                        lambda m: m[1] + numbers.get(m[2].zfill(2), m[2]), cells[-2])
                    lines[i] = '|'.join(cells)
        text = ''.join(lines)
        writes['asset_manifest.md'] = text
    return writes
