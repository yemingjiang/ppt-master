#!/usr/bin/env python3
"""Generate standard main_content.md, style_sheet.md, and asset_manifest.md."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from main_content_pipeline import (
    CONTENT_FILE,
    build_asset_manifest_from_model,
    build_main_content_markdown,
    parse_main_content,
    sync_design_spec_from_main_content,
)
from skeleton_utils import build_style_sheet_markdown, parse_design_spec


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate standard main_content.md, style_sheet.md, and asset_manifest.md "
            "files for a ppt-master project."
        ),
        epilog=(
            "Examples:\n"
            "  python3 scripts/generate_skeleton_docs.py projects/demo\n"
            "  python3 scripts/generate_skeleton_docs.py projects/demo --overwrite\n"
            "  python3 scripts/generate_skeleton_docs.py projects/demo --main-content-only --json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("project_path", help="Path to the ppt-master project directory.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing generated files.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--style-sheet-only",
        action="store_true",
        help="Generate only style_sheet.md.",
    )
    group.add_argument(
        "--asset-manifest-only",
        action="store_true",
        help="Generate only asset_manifest.md.",
    )
    group.add_argument(
        "--main-content-only",
        action="store_true",
        help="Generate only main_content.md.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON summary instead of human-readable text.",
    )
    return parser.parse_args()


def write_if_allowed(path: Path, content: str, overwrite: bool) -> str:
    if path.exists() and not overwrite:
        return "skipped_existing"
    path.write_text(content, encoding="utf-8")
    return "written"


def main() -> int:
    args = parse_args()
    project_path = Path(args.project_path).expanduser().resolve()
    if not project_path.exists():
        raise SystemExit(f"Error: project path does not exist: {project_path}")

    spec = parse_design_spec(project_path)
    content_path = project_path / CONTENT_FILE
    content_exists = content_path.exists()
    model = parse_main_content(project_path, spec)
    design_spec_status = "unchanged"
    if content_exists:
        sync_design_spec_from_main_content(project_path, spec, model)
        spec = parse_design_spec(project_path)
        design_spec_status = "synced_from_main_content"

    outputs: dict[str, dict[str, str]] = {}
    default_mode = not (args.style_sheet_only or args.asset_manifest_only or args.main_content_only)

    if default_mode or args.main_content_only:
        main_content_status = write_if_allowed(
            content_path,
            build_main_content_markdown(spec, model),
            args.overwrite,
        )
        outputs["main_content"] = {"path": str(content_path), "status": main_content_status}

    if default_mode or args.style_sheet_only:
        style_path = project_path / "style_sheet.md"
        style_status = write_if_allowed(style_path, build_style_sheet_markdown(spec), args.overwrite)
        outputs["style_sheet"] = {"path": str(style_path), "status": style_status}

    if default_mode or args.asset_manifest_only:
        asset_path = project_path / "asset_manifest.md"
        asset_status = write_if_allowed(asset_path, build_asset_manifest_from_model(spec, model), args.overwrite)
        outputs["asset_manifest"] = {"path": str(asset_path), "status": asset_status}

    payload = {
        "status": "ok",
        "project_path": str(project_path),
        "project_name": spec["project_name"],
        "design_spec_status": design_spec_status,
        "outputs": outputs,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Project: {project_path}")
        for name, info in outputs.items():
            print(f"{name}: {info['status']} -> {info['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
