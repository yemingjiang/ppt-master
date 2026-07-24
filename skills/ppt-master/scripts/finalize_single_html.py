#!/usr/bin/env python3
"""Run the complete safe finalization pipeline for a single-file HTML deck."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from build_single_html import PackagingError, build_single_html, check_single_html
from check_terminology import TerminologyError, check_terminology
from optimize_single_html_media import (
    DEFAULT_MIN_BYTES,
    MediaOptimizationError,
    analyze_project,
)
from prepare_single_html import PreparationError, prepare_single_html
from qa_single_html import QAError, run_browser_qa
from single_html_state import StateError


class FinalizationError(ValueError):
    """Raised when the finalization pipeline cannot safely continue."""


def finalize_single_html(
    project_path: Path,
    *,
    source: str = "output",
    output_path: Path | None = None,
    force_scaffold: bool = False,
    apply_media: bool = False,
    media_target: str = "1080p",
    min_bytes: int = DEFAULT_MIN_BYTES,
    qa_dir: Path | None = None,
    browser: str = "auto",
    dry_run: bool = False,
) -> dict[str, object]:
    project_path = project_path.resolve()
    terminology = check_terminology(project_path)
    if terminology["status"] == "issues":
        first = terminology["issues"][0]
        raise FinalizationError(
            f"terminology policy found {terminology['issue_count']} issue(s); "
            f"first: {first['file']}:{first['line']} {first['found']} -> "
            f"{first['replacement']}. Run check_terminology.py --json for the full list."
        )

    preparation = prepare_single_html(
        project_path,
        source=source,
        force=force_scaffold,
        refresh_changed=not force_scaffold,
        dry_run=dry_run,
    )
    if dry_run:
        html_output = project_path / "html_output"
        media = (
            analyze_project(
                project_path,
                target=media_target,
                apply=False,
                min_bytes=min_bytes,
            )
            if (html_output / "slides").exists()
            else {
                "status": "not_ready",
                "reason": "HTML slide fragments do not exist yet.",
            }
        )
        packaging = (
            check_single_html(project_path)
            if (html_output / "presentation.json").exists()
            else {
                "status": "not_ready",
                "reason": "HTML manifest does not exist yet.",
            }
        )
        return {
            "status": "planned",
            "mode": "dry-run",
            "project_path": str(project_path),
            "terminology": terminology,
            "preparation": preparation,
            "media": media,
            "packaging": packaging,
            "would_apply_media": apply_media,
            "would_run_browser_qa": True,
        }

    media = analyze_project(
        project_path,
        target=media_target,
        apply=apply_media,
        min_bytes=min_bytes,
    )
    packaging = check_single_html(project_path)
    if packaging["source_state"] in {"stale", "conflict"}:
        raise FinalizationError(
            "HTML scaffold remains stale after preparation; resolve the reported slide "
            "conflicts before final packaging."
        )
    build = build_single_html(project_path, output_path)
    qa_dir = (
        qa_dir.resolve()
        if qa_dir is not None
        else (project_path / "qa" / "final-html").resolve()
    )
    qa = run_browser_qa(
        project_path,
        html_path=Path(build["output_html"]),
        screenshots_dir=qa_dir,
        browser=browser,
    )
    return {
        "status": "ok",
        "mode": "finalize",
        "project_path": str(project_path),
        "terminology": terminology,
        "preparation": preparation,
        "media": media,
        "packaging": packaging,
        "build": build,
        "qa": qa,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely refresh, optimize, build, and browser-QA a single-file HTML deck.",
        epilog=(
            "Examples:\n"
            "  python3 finalize_single_html.py projects/quarterly-review --dry-run --json\n"
            "  python3 finalize_single_html.py projects/quarterly-review --json\n"
            "  python3 finalize_single_html.py projects/quarterly-review "
            "--apply-media --browser chrome --json\n"
            "  python3 finalize_single_html.py projects/legacy-review "
            "--force-scaffold --apply-media --json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("project_path", type=Path, help="Presentation project directory.")
    parser.add_argument(
        "--source",
        choices=("output", "final"),
        default="output",
        help="SVG source directory: output=svg_output (default), final=svg_final.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Final HTML path; defaults to <project>/exports/<project>.single.html.",
    )
    parser.add_argument(
        "--force-scaffold",
        action="store_true",
        help=(
            "Replace all differing managed HTML scaffold targets. Use only for an intentional "
            "legacy migration or full refresh; inspect first with --dry-run."
        ),
    )
    parser.add_argument(
        "--apply-media",
        action="store_true",
        help=(
            "Apply GIF-to-MP4 optimization. Pass only after the user has requested or approved it; "
            "otherwise the pipeline analyzes media without rewriting it."
        ),
    )
    parser.add_argument(
        "--media-target",
        choices=("1080p", "4k"),
        default="1080p",
        help="Presentation media target. Use 4k only for an explicit 4K requirement.",
    )
    parser.add_argument(
        "--min-bytes",
        type=int,
        default=DEFAULT_MIN_BYTES,
        help=f"Minimum GIF size to analyze. Default: {DEFAULT_MIN_BYTES}.",
    )
    parser.add_argument(
        "--qa-dir",
        type=Path,
        help="QA screenshot directory; defaults to <project>/qa/final-html.",
    )
    parser.add_argument(
        "--browser",
        choices=("auto", "chrome", "msedge", "chromium"),
        default="auto",
        help="Browser channel for final QA.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report planned refreshes and current checks without writing project files.",
    )
    parser.add_argument("--json", action="store_true", help="Print one JSON object to stdout.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.output is not None and not args.output.is_absolute():
            output_path = (Path.cwd() / args.output).resolve()
        else:
            output_path = args.output
        result = finalize_single_html(
            args.project_path,
            source=args.source,
            output_path=output_path,
            force_scaffold=args.force_scaffold,
            apply_media=args.apply_media,
            media_target=args.media_target,
            min_bytes=args.min_bytes,
            qa_dir=args.qa_dir,
            browser=args.browser,
            dry_run=args.dry_run,
        )
    except (
        OSError,
        FinalizationError,
        MediaOptimizationError,
        PackagingError,
        PreparationError,
        QAError,
        StateError,
        TerminologyError,
        ValueError,
    ) as error:
        if args.json:
            print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False))
        else:
            print(f"Error: {error}", file=os.sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"Status: {result['status']}")
        if result["status"] == "planned":
            print("Dry run only; no project files were written.")
        else:
            print(f"Output: {result['build']['output_html']}")
            print(f"Slides: {result['build']['slides']}")
            print(f"QA contact sheets: {len(result['qa']['contact_sheets'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
