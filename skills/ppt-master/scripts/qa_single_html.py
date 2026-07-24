#!/usr/bin/env python3
"""Run repeatable real-browser QA for a packaged single-file HTML presentation."""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]


class QAError(RuntimeError):
    """Raised when browser QA cannot start or does not pass."""


def _candidate_runtime_pairs(
    explicit_node: Path | None, explicit_modules: Path | None
) -> list[tuple[Path, Path | None]]:
    pairs: list[tuple[Path, Path | None]] = []
    if explicit_node is not None:
        pairs.append((explicit_node, explicit_modules))

    env_node = os.environ.get("PPT_MASTER_NODE")
    env_modules = os.environ.get("PPT_MASTER_NODE_MODULES")
    if env_node:
        pairs.append((Path(env_node), Path(env_modules) if env_modules else explicit_modules))

    codex_dependencies = (
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "node"
    )
    pairs.append(
        (codex_dependencies / "bin" / "node", codex_dependencies / "node_modules")
    )

    system_node = shutil.which("node")
    if system_node:
        pairs.extend(
            [
                (Path(system_node), explicit_modules),
                (Path(system_node), REPO_ROOT / "node_modules"),
                (Path(system_node), None),
            ]
        )
    return pairs


def _has_playwright(node: Path, modules: Path | None) -> bool:
    if not node.exists():
        return False
    environment = os.environ.copy()
    if modules is not None:
        if not modules.exists():
            return False
        environment["NODE_PATH"] = str(modules)
    completed = subprocess.run(
        [str(node), "-e", "require.resolve('playwright')"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    return completed.returncode == 0


def resolve_node_runtime(
    explicit_node: Path | None = None, explicit_modules: Path | None = None
) -> tuple[Path, Path | None]:
    seen: set[tuple[str, str]] = set()
    for node, modules in _candidate_runtime_pairs(explicit_node, explicit_modules):
        key = (str(node), str(modules or ""))
        if key in seen:
            continue
        seen.add(key)
        if _has_playwright(node, modules):
            return node.resolve(), modules.resolve() if modules is not None else None
    raise QAError(
        "Playwright runtime not found. Set PPT_MASTER_NODE and PPT_MASTER_NODE_MODULES, "
        "or pass --node and --node-modules. The modules directory must contain 'playwright'."
    )


def _build_contact_sheets(screenshots_dir: Path, slide_count: int) -> list[str]:
    try:
        from PIL import Image, ImageDraw
    except ImportError as error:
        raise QAError(
            "Pillow is required to create contact sheets; install the repository requirements."
        ) from error

    thumbnails = []
    for index in range(1, slide_count + 1):
        source = screenshots_dir / f"{index:02d}.png"
        if not source.exists():
            raise QAError(f"expected screenshot was not created: {source}")
        with Image.open(source) as opened:
            image = opened.convert("RGB")
        image.thumbnail((480, 270))
        canvas = Image.new("RGB", (500, 305), "white")
        canvas.paste(image, ((500 - image.width) // 2, 20))
        ImageDraw.Draw(canvas).text((10, 5), f"{index:02d}", fill="black")
        thumbnails.append(canvas)

    outputs: list[str] = []
    for sheet_index, start in enumerate(range(0, len(thumbnails), 8), 1):
        group = thumbnails[start : start + 8]
        sheet = Image.new("RGB", (2000, 610), (235, 235, 235))
        for position, image in enumerate(group):
            sheet.paste(image, ((position % 4) * 500, (position // 4) * 305))
        output = screenshots_dir / f"contact-sheet-{sheet_index}.png"
        sheet.save(output)
        outputs.append(str(output.resolve()))
    return outputs


def run_browser_qa(
    project_path: Path,
    *,
    html_path: Path | None = None,
    screenshots_dir: Path | None = None,
    browser: str = "auto",
    node: Path | None = None,
    node_modules: Path | None = None,
) -> dict[str, object]:
    project_path = project_path.resolve()
    html_path = (
        html_path.resolve()
        if html_path is not None
        else (project_path / "exports" / f"{project_path.name}.single.html").resolve()
    )
    if not html_path.exists():
        raise QAError(
            f"packaged HTML not found: {html_path}. "
            "Run build_single_html.py before browser QA."
        )
    if screenshots_dir is not None:
        screenshots_dir = screenshots_dir.resolve()
        screenshots_dir.mkdir(parents=True, exist_ok=True)

    node_path, modules_path = resolve_node_runtime(node, node_modules)
    configuration = {
        "htmlPath": str(html_path),
        "screenshotsDir": str(screenshots_dir) if screenshots_dir is not None else None,
        "browser": browser,
    }
    encoded = base64.b64encode(
        json.dumps(configuration, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    environment = os.environ.copy()
    if modules_path is not None:
        environment["NODE_PATH"] = str(modules_path)
    completed = subprocess.run(
        [str(node_path), str(SCRIPT_DIR / "qa_single_html.cjs"), encoded],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no output"
        raise QAError(f"browser QA returned invalid output: {detail}") from error
    if completed.returncode != 0 or payload.get("status") != "ok":
        raise QAError(str(payload.get("error") or completed.stderr.strip() or "browser QA failed"))

    payload["node"] = str(node_path)
    payload["node_modules"] = str(modules_path) if modules_path is not None else None
    if screenshots_dir is not None:
        payload["contact_sheets"] = _build_contact_sheets(
            screenshots_dir, int(payload["slides"])
        )
    else:
        payload["contact_sheets"] = []
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run real-browser QA for a packaged ppt-master single-file HTML presentation.",
        epilog=(
            "Examples:\n"
            "  python3 qa_single_html.py projects/quarterly-review --json\n"
            "  python3 qa_single_html.py projects/quarterly-review --screenshots /tmp/quarterly-qa --json\n"
            "  python3 qa_single_html.py projects/quarterly-review --browser chrome --node /path/to/node --node-modules /path/to/node_modules"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("project_path", type=Path, help="Presentation project directory.")
    parser.add_argument("--html", type=Path, help="Packaged HTML path; defaults to the standard export.")
    parser.add_argument(
        "--screenshots",
        type=Path,
        help="Write clean per-slide screenshots and contact sheets to this directory.",
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
        result = run_browser_qa(
            args.project_path,
            html_path=args.html,
            screenshots_dir=args.screenshots,
            browser=args.browser,
            node=args.node,
            node_modules=args.node_modules,
        )
    except (OSError, QAError, ValueError) as error:
        if args.json:
            print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False))
        else:
            print(f"Error: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"QA passed: {result['html']}")
        print(f"Browser: {result['browser']}")
        print(f"Slides: {result['slides']}")
        print(f"Checks: {len(result['checks'])}")
        if result["contact_sheets"]:
            print(f"Contact sheets: {len(result['contact_sheets'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
