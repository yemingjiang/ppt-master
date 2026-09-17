"""Recover authorized offline HTML edits before regenerating derived artifacts.

Only inert review JSON is read; scripts and browser-supplied paths are never executed.
The existing review transaction provides field-level conflict checking and backups.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from preview_editing import MANIFEST, Conflict, EditError, prepare_manifest, revision
from review_packets import apply_packet

MARKER = re.compile(r'<script id="ppt-master-saved-state" type="application/json">(.*?)</script>', re.S)


def read_saved_html(path: Path) -> dict | None:
    if not path.exists():
        return None
    text = path.read_text(encoding='utf-8')
    matches = MARKER.findall(text)
    if not matches:
        return None  # Existing drafts predate browser saving.
    if len(matches) != 1:
        raise EditError('Duplicate saved HTML state; original preview was not overwritten')
    try:
        data = json.loads(matches[0])
    except ValueError as exc:
        raise EditError('Saved HTML state is damaged; recover it before rebuilding') from exc
    if not isinstance(data, dict) or data.get('schema') != 1 or data.get('kind') != 'ppt-master-saved-html':
        raise EditError('Unknown saved HTML format; original preview was not overwritten')
    return data


def sync_saved_html(project: Path, path: Path | None = None, *, dry_run: bool = False) -> dict:
    project = project.resolve()
    saved = read_saved_html(path or project / 'preview/index.html')
    result = {'saved': saved, 'pending_changes': [], 'files': []}
    if not saved:
        return result
    manifest_path = project / MANIFEST
    if not manifest_path.exists():
        raise EditError('Saved HTML requires the original project manifest; do not guess field mappings')
    manifest = json.loads(manifest_path.read_text())
    if saved.get('project_id') != manifest['project_id']:
        raise EditError('Saved HTML belongs to another project')
    packet = saved.get('packet')
    if not packet:
        return result
    if not isinstance(packet, dict) or packet.get('comments') != []:
        raise EditError('Saved HTML must contain content-only edits; comments require explicit review')
    if manifest['revision'] != revision(project):
        if dry_run:
            raise Conflict('Sources changed since preview generation. Rebuild the draft to reconcile saved edits first.')
        prepare_manifest(project)
    result.update(apply_packet(project, packet, dry_run=dry_run))
    return result
