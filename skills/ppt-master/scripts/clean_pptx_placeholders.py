#!/usr/bin/env python3
"""Remove unwanted placeholder text boxes from a PPTX archive.

Examples:
    python3 scripts/clean_pptx_placeholders.py deck.pptx --in-place
    python3 scripts/clean_pptx_placeholders.py deck.pptx -o cleaned.pptx
    python3 scripts/clean_pptx_placeholders.py deck.pptx --in-place --dry-run
    python3 scripts/clean_pptx_placeholders.py deck.pptx --in-place --format text
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Iterable
import zipfile


DEFAULT_PLACEHOLDER_TYPES = ("sldNum",)


def build_placeholder_regex(placeholder_types: Iterable[str]) -> re.Pattern[str]:
    escaped = "|".join(re.escape(value) for value in placeholder_types)
    return re.compile(
        rf"<p:sp\b[\s\S]*?<p:ph\b[^>]*\btype=\"(?:{escaped})\"[^>]*/>[\s\S]*?</p:sp>",
        re.MULTILINE,
    )


def clean_slide_xml(xml: str, placeholder_types: Iterable[str]) -> tuple[str, int]:
    pattern = build_placeholder_regex(placeholder_types)
    cleaned, removed = pattern.subn("", xml)
    return cleaned, removed


def rezip_tree(source_dir: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir))


def clean_pptx(
    input_path: Path,
    *,
    output_path: Path | None,
    in_place: bool,
    placeholder_types: list[str],
    dry_run: bool,
) -> dict[str, object]:
    if not input_path.is_file():
        raise FileNotFoundError(f"PPTX not found: {input_path}")

    with tempfile.TemporaryDirectory(prefix="ppt-clean-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        with zipfile.ZipFile(input_path) as archive:
            archive.extractall(temp_dir)

        slides_dir = temp_dir / "ppt" / "slides"
        slide_files = sorted(slides_dir.glob("*.xml")) if slides_dir.exists() else []
        slides_changed = 0
        placeholders_removed = 0

        for slide_path in slide_files:
            xml = slide_path.read_text(encoding="utf-8")
            cleaned_xml, removed = clean_slide_xml(xml, placeholder_types)
            if removed:
                slides_changed += 1
                placeholders_removed += removed
                if not dry_run:
                    slide_path.write_text(cleaned_xml, encoding="utf-8")

        target_path = input_path if in_place else output_path
        if not dry_run and target_path is not None:
            rezip_tree(temp_dir, target_path)

    return {
        "status": "dry-run" if dry_run else "ok",
        "input": str(input_path),
        "output": None if dry_run else (str(target_path) if target_path is not None else None),
        "placeholder_types": placeholder_types,
        "slides_scanned": len(slide_files),
        "slides_changed": slides_changed,
        "placeholders_removed": placeholders_removed,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Remove unwanted placeholder text boxes from a PPTX archive. "
            "Defaults to removing slide-number placeholders (type=sldNum)."
        ),
        epilog=(
            "Examples:\n"
            "  python3 scripts/clean_pptx_placeholders.py deck.pptx --in-place\n"
            "  python3 scripts/clean_pptx_placeholders.py deck.pptx -o cleaned.pptx\n"
            "  python3 scripts/clean_pptx_placeholders.py deck.pptx --in-place --dry-run\n"
            "  python3 scripts/clean_pptx_placeholders.py deck.pptx --in-place --format text"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("pptx_path", help="Input PPTX file to clean.")
    parser.add_argument(
        "-o",
        "--output",
        help="Write the cleaned PPTX to this path instead of modifying the input file.",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Rewrite the input PPTX in place.",
    )
    parser.add_argument(
        "--placeholder-type",
        action="append",
        dest="placeholder_types",
        help=(
            "Placeholder type to remove. Repeat to remove multiple types. "
            "Default: sldNum."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing a cleaned PPTX.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Success/error output format. Default: json.",
    )
    return parser


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.in_place and args.output:
        parser.error("Use either --in-place or --output, not both.")
    if not args.in_place and not args.output:
        parser.error("Choose one write mode: --in-place or --output <path>.")


def render_text(payload: dict[str, object]) -> str:
    return (
        f"status={payload['status']} "
        f"slides_scanned={payload['slides_scanned']} "
        f"slides_changed={payload['slides_changed']} "
        f"placeholders_removed={payload['placeholders_removed']} "
        f"output={payload['output'] or '-'}"
    )


def emit(payload: dict[str, object], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(render_text(payload))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(args, parser)

    placeholder_types = args.placeholder_types or list(DEFAULT_PLACEHOLDER_TYPES)
    input_path = Path(args.pptx_path).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve() if args.output else None

    try:
        payload = clean_pptx(
            input_path,
            output_path=output_path,
            in_place=bool(args.in_place),
            placeholder_types=placeholder_types,
            dry_run=bool(args.dry_run),
        )
    except Exception as exc:  # pragma: no cover - exercised through CLI behavior
        error_payload = {
            "status": "error",
            "error": str(exc),
            "input": str(input_path),
        }
        emit(error_payload, args.format)
        return 1

    emit(payload, args.format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
