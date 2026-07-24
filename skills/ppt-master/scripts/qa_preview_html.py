#!/usr/bin/env python3
"""Run repeatable browser QA for a ppt-master skeleton preview."""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
from pathlib import Path

from qa_single_html import QAError, resolve_node_runtime


SCRIPT_DIR = Path(__file__).resolve().parent


def _parse_slide_keys(value: str | None) -> list[str]:
    if not value:
        return []
    keys: list[str] = []
    for raw in value.split(","):
        item = raw.strip()
        if not item:
            continue
        if not item.isdigit():
            raise QAError(f"invalid slide key {item!r}; use comma-separated numbers such as 06,15,19")
        key = item.zfill(2)
        if key not in keys:
            keys.append(key)
    return keys


def _build_contact_sheet(screenshots: list[str], output_dir: Path) -> str | None:
    if not screenshots:
        return None
    try:
        from PIL import Image, ImageDraw
    except ImportError as error:
        raise QAError("Pillow is required to create the preview contact sheet.") from error

    thumbnails = []
    for screenshot in screenshots:
        source = Path(screenshot)
        with Image.open(source) as opened:
            image = opened.convert("RGB")
        image.thumbnail((480, 270))
        canvas = Image.new("RGB", (500, 305), "white")
        canvas.paste(image, ((500 - image.width) // 2, 20))
        ImageDraw.Draw(canvas).text((10, 5), source.stem, fill="black")
        thumbnails.append(canvas)

    columns = min(4, len(thumbnails))
    rows = (len(thumbnails) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * 500, rows * 305), (235, 235, 235))
    for index, image in enumerate(thumbnails):
        sheet.paste(image, ((index % columns) * 500, (index // columns) * 305))
    output = output_dir / "contact-sheet.png"
    sheet.save(output)
    return str(output.resolve())


def run_preview_qa(
    project_path: Path,
    *,
    preview_path: Path | None = None,
    slide_keys: list[str] | None = None,
    screenshots_dir: Path | None = None,
    browser: str = "auto",
    node: Path | None = None,
    node_modules: Path | None = None,
) -> dict[str, object]:
    project_path = project_path.resolve()
    preview_path = (
        preview_path.resolve()
        if preview_path is not None
        else (project_path / "preview" / "index.html").resolve()
    )
    if not preview_path.exists():
        raise QAError(
            f"skeleton preview not found: {preview_path}. "
            "Run build_preview_html.py before preview QA."
        )
    if screenshots_dir is not None:
        screenshots_dir = screenshots_dir.resolve()
        screenshots_dir.mkdir(parents=True, exist_ok=True)

    node_path, modules_path = resolve_node_runtime(node, node_modules)
    configuration = {
        "previewPath": str(preview_path),
        "slideKeys": slide_keys or [],
        "screenshotsDir": str(screenshots_dir) if screenshots_dir is not None else None,
        "browser": browser,
    }
    encoded = base64.b64encode(
        json.dumps(configuration, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    environment = os.environ.copy()
    if modules_path is not None:
        environment["NODE_PATH"] = str(modules_path)
    try:
        completed = subprocess.run(
            [str(node_path), str(SCRIPT_DIR / "qa_preview_html.cjs"), encoded],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            timeout=90,
        )
    except subprocess.TimeoutExpired as error:
        raise QAError(
            "preview browser QA exceeded 90 seconds; rerun with --browser chrome "
            "and inspect the preview for a slide or iframe that never finishes loading."
        ) from error
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no output"
        raise QAError(f"preview browser QA returned invalid output: {detail}") from error
    if completed.returncode != 0 or payload.get("status") != "ok":
        raise QAError(str(payload.get("error") or completed.stderr.strip() or "preview QA failed"))

    payload["node"] = str(node_path)
    payload["node_modules"] = str(modules_path) if modules_path is not None else None
    payload["contact_sheet"] = (
        _build_contact_sheet(payload.get("screenshots", []), screenshots_dir)
        if screenshots_dir is not None
        else None
    )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run real-browser QA for a ppt-master skeleton preview.",
        epilog=(
            "Examples:\n"
            "  python3 qa_preview_html.py projects/quarterly-review --json\n"
            "  python3 qa_preview_html.py projects/quarterly-review --slides 06,15,19 "
            "--screenshots /tmp/preview-qa --json\n"
            "  python3 qa_preview_html.py projects/quarterly-review --browser chrome --json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("project_path", type=Path, help="Presentation project directory.")
    parser.add_argument(
        "--preview",
        type=Path,
        help="Preview HTML path; defaults to <project_path>/preview/index.html.",
    )
    parser.add_argument(
        "--slides",
        help="Comma-separated slide numbers to screenshot, for example 06,15,19.",
    )
    parser.add_argument(
        "--screenshots",
        type=Path,
        help="Write selected slide screenshots and a contact sheet to this directory.",
    )
    parser.add_argument(
        "--browser",
        choices=("auto", "chrome", "msedge", "chromium"),
        default="auto",
        help="Browser channel. auto tries Chrome, Edge, then Playwright Chromium.",
    )
    parser.add_argument("--node", type=Path, help="Explicit Node.js executable.")
    parser.add_argument(
        "--node-modules",
        type=Path,
        help="Explicit Node modules directory containing Playwright.",
    )
    parser.add_argument("--json", action="store_true", help="Print one JSON object to stdout.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run_preview_qa(
            args.project_path,
            preview_path=args.preview,
            slide_keys=_parse_slide_keys(args.slides),
            screenshots_dir=args.screenshots,
            browser=args.browser,
            node=args.node,
            node_modules=args.node_modules,
        )
    except (OSError, QAError, ValueError) as error:
        if args.json:
            print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False))
        else:
            print(f"Error: {error}", file=os.sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"Preview QA passed: {result['preview']}")
        print(f"Slides: {result['slides']}")
        print(f"Tested slides: {', '.join(result['tested_slides'])}")
        if result["contact_sheet"]:
            print(f"Contact sheet: {result['contact_sheet']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
