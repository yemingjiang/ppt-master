#!/usr/bin/env python3
"""Prepare deterministic single-file HTML sources from approved SVG slides."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from main_content_pipeline import parse_main_content
from skeleton_utils import clean_md_inline, parse_design_spec, slide_key, slide_sort_key


DEFAULT_THEME = {
    "name": "executive-red",
    "tokens": {
        "background": "#FFFFFF",
        "surface": "#F2F2F2",
        "primary": "#B50F0A",
        "on_primary": "#FFFFFF",
        "text": "#222222",
        "muted": "#666666",
        "line": "#D7D7D7",
        "runtime_background": "#14171A",
    },
}

DEFAULT_PRESENTATION_CSS = """:root {
  --pm-font-family: "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
}

.pm-stage {
  background: #ffffff;
}

.pm-slide {
  cursor: pointer;
  user-select: none;
  -webkit-user-select: none;
}

.pm-slide .pm-artwork {
  display: block;
  width: 100%;
  height: 100%;
  pointer-events: none;
  shape-rendering: geometricPrecision;
  text-rendering: optimizeLegibility;
}

.pm-slide .pm-artwork * {
  pointer-events: none;
}

.pm-slide text {
  font-synthesis: none;
}

@media print {
  body {
    overflow: visible;
    background: #ffffff;
  }

  .pm-app {
    display: block;
    padding: 0;
    background: #ffffff;
  }

  .pm-stage {
    width: 100%;
    box-shadow: none;
  }

  .pm-controls,
  .pm-progress-track,
  .pm-notes-panel,
  .pm-help-panel {
    display: none !important;
  }
}
"""

_ATTRIBUTE_REFERENCE_PATTERN = re.compile(
    r"(?P<prefix>\b(?:href|xlink:href|src)\s*=\s*)(?P<quote>[\"'])(?P<reference>.*?)(?P=quote)",
    re.I,
)
_CSS_URL_PATTERN = re.compile(
    r"url\(\s*(?P<quote>[\"']?)(?P<reference>.*?)(?P=quote)\s*\)",
    re.I,
)
_SVG_ROOT_PATTERN = re.compile(r"<svg\b.*?</svg>\s*$", re.I | re.S)
_SVG_OPEN_PATTERN = re.compile(r"<svg\b(?P<attributes>[^>]*)>", re.I | re.S)
_ID_PATTERN = re.compile(r"\bid=(?P<quote>[\"'])(?P<id>[^\"']+)(?P=quote)")


class PreparationError(RuntimeError):
    """Raised when deterministic HTML preparation cannot proceed safely."""


def _read_text(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise PreparationError(f"{label} not found: {path}") from error
    except OSError as error:
        raise PreparationError(f"unable to read {label}: {path}") from error


def _extract_svg(text: str, source_path: Path) -> str:
    normalized = text.lstrip("\ufeff").strip()
    normalized = re.sub(r"^<\?xml[^>]*\?>\s*", "", normalized, flags=re.I)
    normalized = re.sub(r"^<!DOCTYPE[^>]*>\s*", "", normalized, flags=re.I | re.S)
    match = _SVG_ROOT_PATTERN.fullmatch(normalized)
    if match is None:
        raise PreparationError(f"{source_path}: expected exactly one SVG root")
    return match.group(0).strip()


def _require_project_local(project_path: Path, path: Path, label: str) -> None:
    try:
        path.resolve().relative_to(project_path.resolve())
    except ValueError as error:
        raise PreparationError(f"{label} must stay inside the project: {path}") from error


def _rebase_reference(reference: str, source_path: Path, destination_dir: Path, project_path: Path) -> str:
    reference = reference.strip()
    if not reference or reference.startswith(("#", "data:")):
        return reference
    parts = urlsplit(reference)
    if parts.scheme or parts.netloc or reference.startswith("//"):
        raise PreparationError(f"{source_path}: final HTML sources may only use project-local resources: {reference}")
    resource_path = (source_path.parent / parts.path).resolve()
    _require_project_local(project_path, resource_path, "resource")
    relative = Path(os.path.relpath(resource_path, destination_dir.resolve())).as_posix()
    if parts.query:
        relative += f"?{parts.query}"
    if parts.fragment:
        relative += f"#{parts.fragment}"
    return relative


def _rebase_svg_resources(svg: str, source_path: Path, destination_dir: Path, project_path: Path) -> str:
    def replace_attribute(match: re.Match[str]) -> str:
        reference = _rebase_reference(
            match.group("reference"), source_path, destination_dir, project_path
        )
        return f"{match.group('prefix')}{match.group('quote')}{reference}{match.group('quote')}"

    def replace_css_url(match: re.Match[str]) -> str:
        reference = match.group("reference").strip()
        if reference.startswith("#"):
            return match.group(0)
        rewritten = _rebase_reference(reference, source_path, destination_dir, project_path)
        quote = match.group("quote")
        return f"url({quote}{rewritten}{quote})"

    return _CSS_URL_PATTERN.sub(replace_css_url, _ATTRIBUTE_REFERENCE_PATTERN.sub(replace_attribute, svg))


def _prefix_svg_ids(svg: str, slide_id: str) -> str:
    prefix = f"s{slide_id}-"
    identifiers = list(dict.fromkeys(match.group("id") for match in _ID_PATTERN.finditer(svg)))
    mapping = {
        identifier: identifier if identifier.startswith(prefix) else f"{prefix}{identifier}"
        for identifier in identifiers
    }

    def replace_id(match: re.Match[str]) -> str:
        return f"id={match.group('quote')}{mapping[match.group('id')]}{match.group('quote')}"

    rewritten = _ID_PATTERN.sub(replace_id, svg)
    for old in sorted(mapping, key=len, reverse=True):
        new = mapping[old]
        if new == old:
            continue
        rewritten = re.sub(rf"(?<=#){re.escape(old)}(?=[)\s\"';])", new, rewritten)
        rewritten = re.sub(
            rf"(?P<prefix>\b(?:begin|end)=[\"'][^\"']*?)\b{re.escape(old)}(?=\.)",
            lambda match: f"{match.group('prefix')}{new}",
            rewritten,
        )
    return rewritten


def _ensure_svg_runtime_attributes(svg: str) -> str:
    match = _SVG_OPEN_PATTERN.search(svg)
    if match is None:
        raise PreparationError("expected SVG opening tag")
    attributes = match.group("attributes")
    class_match = re.search(r"\bclass=(?P<quote>[\"'])(?P<value>.*?)(?P=quote)", attributes, re.S)
    if class_match:
        classes = class_match.group("value").split()
        if "pm-artwork" not in classes:
            classes.append("pm-artwork")
        replacement = f'class="{" ".join(classes)}"'
        attributes = (
            attributes[: class_match.start()] + replacement + attributes[class_match.end() :]
        )
    else:
        attributes += ' class="pm-artwork"'
    if not re.search(r"\baria-hidden=", attributes):
        attributes += ' aria-hidden="true"'
    if not re.search(r"\bfocusable=", attributes):
        attributes += ' focusable="false"'
    return svg[: match.start()] + f"<svg{attributes}>" + svg[match.end() :]


def _svg_dimensions(svg: str) -> tuple[float, float]:
    open_match = _SVG_OPEN_PATTERN.search(svg)
    if open_match is None:
        return (16.0, 9.0)
    attributes = open_match.group("attributes")
    view_box = re.search(
        r"\bviewBox=[\"']\s*[-+0-9.eE]+\s+[-+0-9.eE]+\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s*[\"']",
        attributes,
    )
    if view_box:
        return (float(view_box.group(1)), float(view_box.group(2)))
    width_match = re.search(r"\bwidth=[\"']([0-9.]+)", attributes)
    height_match = re.search(r"\bheight=[\"']([0-9.]+)", attributes)
    if width_match and height_match:
        return (float(width_match.group(1)), float(height_match.group(1)))
    return (16.0, 9.0)


def _aspect_ratio(width: float, height: float) -> str:
    if height <= 0:
        raise PreparationError("SVG height must be positive")
    ratio = width / height
    if abs(ratio - (16 / 9)) < 0.01:
        return "16 / 9"
    if abs(ratio - (4 / 3)) < 0.01:
        return "4 / 3"
    return f"{width:g} / {height:g}"


def _theme_from_design_spec(project_path: Path) -> dict:
    if not (project_path / "design_spec.md").exists():
        return json.loads(json.dumps(DEFAULT_THEME))
    spec = parse_design_spec(project_path)
    tokens = dict(DEFAULT_THEME["tokens"])
    role_map = {
        "background": "background",
        "secondary bg": "surface",
        "primary": "primary",
        "on primary": "on_primary",
        "body text": "text",
        "secondary text": "muted",
        "border/divider": "line",
    }
    for row in spec.get("colors", []):
        role = clean_md_inline(row.get("Role", "")).lower()
        value = clean_md_inline(row.get("HEX", "")).strip("`")
        token = role_map.get(role)
        if token and re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
            tokens[token] = value.upper()
    return {"name": DEFAULT_THEME["name"], "tokens": tokens}


def _atomic_write(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _load_existing_manifest(project_path: Path) -> dict | None:
    path = project_path / "html_output" / "presentation.json"
    if not path.exists():
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise PreparationError(
            f"existing manifest contains invalid JSON at line {error.lineno}: {path}"
        ) from error
    if not isinstance(manifest, dict):
        raise PreparationError(f"existing manifest must be a JSON object: {path}")
    return manifest


def prepare_single_html(
    project_path: Path,
    *,
    source: str = "output",
    force: bool = False,
    dry_run: bool = False,
    title: str | None = None,
    lang: str | None = None,
) -> dict[str, object]:
    project_path = project_path.resolve()
    source_dir_name = {"output": "svg_output", "final": "svg_final"}.get(source)
    if source_dir_name is None:
        raise PreparationError("source must be 'output' or 'final'")
    source_dir = project_path / source_dir_name
    svg_paths = sorted(source_dir.glob("*.svg"), key=slide_sort_key)
    if not svg_paths:
        raise PreparationError(f"no SVG slides found in {source_dir}")

    content_model = parse_main_content(project_path)
    content_by_key = {slide["key"]: slide for slide in content_model.get("slides", [])}
    html_output = project_path / "html_output"
    slides_dir = html_output / "slides"
    existing_manifest = _load_existing_manifest(project_path)
    existing_slides = existing_manifest.get("slides", []) if existing_manifest else []
    existing_files_by_id = {
        str(item.get("id")): str(item.get("file"))
        for item in existing_slides
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and isinstance(item.get("file"), str)
        and str(item.get("file")).startswith("slides/")
    }
    manifest_slides: list[dict[str, str]] = []
    planned: dict[Path, str] = {}
    seen_ids: set[str] = set()
    first_dimensions: tuple[float, float] | None = None

    for svg_path in svg_paths:
        slide_id = slide_key(svg_path.stem)
        if not re.fullmatch(r"\d{2,}", slide_id):
            raise PreparationError(f"{svg_path}: filename must start with a slide number")
        if slide_id in seen_ids:
            raise PreparationError(f"duplicate slide id {slide_id!r} in {source_dir}")
        seen_ids.add(slide_id)
        slide_model = content_by_key.get(slide_id, {})
        slide_title = slide_model.get("title") or re.sub(
            r"^(?:slide_|P)?\d+[_\- ]*", "", svg_path.stem
        )
        svg = _extract_svg(_read_text(svg_path, "SVG slide"), svg_path)
        if first_dimensions is None:
            first_dimensions = _svg_dimensions(svg)
        svg = _rebase_svg_resources(svg, svg_path, slides_dir, project_path)
        svg = _prefix_svg_ids(svg, slide_id)
        svg = _ensure_svg_runtime_attributes(svg)
        fragment = (
            f'<section class="pm-slide" data-slide-id="{html.escape(slide_id, quote=True)}" '
            f'aria-label="{html.escape(str(slide_title), quote=True)}">\n'
            f"{svg}\n"
            "</section>\n"
        )
        existing_file = existing_files_by_id.get(slide_id)
        destination_name = (
            Path(existing_file).name if existing_file is not None else f"{svg_path.stem}.html"
        )
        destination = slides_dir / destination_name
        planned[destination] = fragment
        manifest_slides.append(
            {
                "id": slide_id,
                "title": str(slide_title),
                "file": f"slides/{destination_name}",
            }
        )

    deck_title = (
        title
        or (existing_manifest or {}).get("title")
        or content_model.get("project_name")
        or project_path.name
    )
    detected_language = content_model.get("language")
    manifest_language = (
        lang
        or (existing_manifest or {}).get("lang")
        or ("zh-CN" if detected_language == "zh" else "en")
    )
    width, height = first_dimensions or (16.0, 9.0)
    manifest = {
        "schema_version": 1,
        "title": deck_title,
        "lang": manifest_language,
        "aspect_ratio": (existing_manifest or {}).get("aspect_ratio")
        or _aspect_ratio(width, height),
        "theme": (existing_manifest or {}).get("theme")
        or _theme_from_design_spec(project_path),
        "slides": manifest_slides,
    }
    planned[html_output / "presentation.json"] = (
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    planned[html_output / "presentation.css"] = DEFAULT_PRESENTATION_CSS

    created: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []
    conflicts: list[str] = []
    for path, contents in planned.items():
        relative = path.relative_to(project_path).as_posix()
        if not path.exists():
            created.append(relative)
            continue
        current = path.read_text(encoding="utf-8")
        if current == contents:
            unchanged.append(relative)
        elif force:
            updated.append(relative)
        else:
            conflicts.append(relative)

    if conflicts and not dry_run:
        joined = ", ".join(conflicts[:5])
        suffix = "" if len(conflicts) <= 5 else f" (+{len(conflicts) - 5} more)"
        raise PreparationError(
            f"refusing to overwrite existing HTML sources: {joined}{suffix}. "
            "Re-run with --dry-run to inspect or --force to replace generated targets."
        )

    if not dry_run:
        for path, contents in planned.items():
            if path.exists() and path.read_text(encoding="utf-8") == contents:
                continue
            _atomic_write(path, contents)

    return {
        "status": "planned" if dry_run else "ok",
        "project_path": str(project_path),
        "source": source,
        "slides": len(manifest_slides),
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "would_overwrite": conflicts,
        "manifest": str((html_output / "presentation.json").resolve()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare deterministic html_output sources from approved SVG slides.",
        epilog=(
            "Examples:\n"
            "  python3 prepare_single_html.py projects/quarterly-review --dry-run --json\n"
            "  python3 prepare_single_html.py projects/quarterly-review --source output\n"
            "  python3 prepare_single_html.py projects/quarterly-review --force --json"
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
    parser.add_argument("--title", help="Override the presentation title.")
    parser.add_argument("--lang", help="Override the manifest language, for example zh-CN.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace generated target files that differ. Extra files are never deleted.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report planned writes and conflicts without changing files.",
    )
    parser.add_argument("--json", action="store_true", help="Print one JSON object to stdout.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = prepare_single_html(
            args.project_path,
            source=args.source,
            force=args.force,
            dry_run=args.dry_run,
            title=args.title,
            lang=args.lang,
        )
    except (OSError, PreparationError, ValueError) as error:
        if args.json:
            print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False))
        else:
            print(f"Error: {error}", file=os.sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"Status: {result['status']}")
        print(f"Slides: {result['slides']}")
        print(f"Manifest: {result['manifest']}")
        if result["would_overwrite"]:
            print(f"Would overwrite: {len(result['would_overwrite'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
