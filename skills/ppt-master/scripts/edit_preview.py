#!/usr/bin/env python3
"""Inspect/apply clipboard feedback and acknowledge processed items. Offline only."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from build_preview_html import render_preview
from preview_editing import Conflict, EditError, apply_edits
from review_packets import acknowledge, apply_packet, inspect_packet, parse_packet


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Examples (paste the complete copied text on stdin):\n  edit_preview.py inspect projects/demo --stdin --json\n  edit_preview.py apply projects/demo --stdin --dry-run --json\n  edit_preview.py apply projects/demo --stdin --json\n  edit_preview.py ack projects/demo --stdin --comments-processed --json')
    subs = parser.add_subparsers(dest='command', required=True)
    for command, description in [('inspect', 'Read changes, comments and source conflicts without writing.'),
                                 ('apply', 'Apply direct text/notes edits; leave comments pending for Codex.'),
                                 ('ack', 'Confirm feedback already handled by Codex; rebuild the offline preview.')]:
        sub = subs.add_parser(command, help=description, description=description)
        sub.add_argument('project_path', type=Path)
        source = sub.add_mutually_exclusive_group(required=True)
        source.add_argument('--stdin', action='store_true', help='Read the copied Markdown change list (or legacy JSON) from standard input.')
        source.add_argument('--file', help='Read an agent-side saved copy of the feedback; - also means stdin.')
        sub.add_argument('--json', action='store_true', help='Print structured output.')
        if command == 'apply':
            sub.add_argument('--dry-run', action='store_true', help='Validate and report changes without writing.')
        if command == 'ack':
            sub.add_argument('--content-processed', action='store_true', help='Direct edits were manually resolved/applied by Codex.')
            sub.add_argument('--comments-processed', action='store_true', help='All comments in this exact packet were handled by Codex.')
    args = parser.parse_args()
    try:
        raw = sys.stdin.read() if args.stdin or args.file == '-' else Path(args.file).read_text()
        package = parse_packet(raw, args.project_path)
        if args.command == 'inspect':
            result = inspect_packet(args.project_path, package)
        elif args.command == 'ack':
            result = acknowledge(args.project_path, package, args.content_processed, args.comments_processed)
        elif package.get('schema') == 1:
            result = apply_edits(args.project_path, package, args.dry_run)
            result.pop('manifest', None)
        else:
            result = apply_packet(args.project_path, package, args.dry_run)
        if args.command == 'ack' or (args.command == 'apply' and not args.dry_run):
            try:
                render_preview(args.project_path, editable=True)
            except Exception as exc:
                result['preview_warning'] = str(exc)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 3 if result.get('status') == 'conflict' else 0
    except (EditError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'status': 'conflict' if isinstance(exc, Conflict) else 'error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 3 if isinstance(exc, Conflict) else 2


if __name__ == '__main__':
    raise SystemExit(main())
