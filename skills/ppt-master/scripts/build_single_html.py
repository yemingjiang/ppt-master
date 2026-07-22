"""Validate source files for an offline single-file HTML presentation."""

from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup, Comment, NavigableString


class PackagingError(ValueError):
    """Raised when presentation sources cannot be packaged safely."""


def _require_mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise PackagingError(f"{field} must be an object")
    return value


def _require_string(mapping: dict[str, object], key: str, field: str | None = None) -> str:
    field = field or key
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise PackagingError(f"{field} must be a non-empty string")
    return value


def _project_local_path(project_path: Path, path: Path, field: str) -> Path:
    try:
        path.relative_to(project_path)
    except ValueError as error:
        raise PackagingError(f"{field} must stay inside the project") from error
    return path


def load_manifest(project_path: Path) -> dict[str, object]:
    """Load presentation.json and validate schema, slide IDs, and project-local paths."""
    project_path = project_path.resolve()
    manifest_path = project_path / "html_output" / "presentation.json"
    try:
        manifest = _require_mapping(json.loads(manifest_path.read_text(encoding="utf-8")), "manifest")
    except FileNotFoundError as error:
        raise PackagingError(f"manifest not found: {manifest_path}") from error
    except json.JSONDecodeError as error:
        raise PackagingError(f"manifest contains invalid JSON: {error.msg}") from error

    if manifest.get("schema_version") != 1:
        raise PackagingError("schema_version must be 1")

    for field in ("title", "lang", "aspect_ratio"):
        _require_string(manifest, field)
    _require_mapping(manifest.get("theme"), "theme")

    slides = manifest.get("slides")
    if not isinstance(slides, list):
        raise PackagingError("slides must be an array")

    output_path = (project_path / "html_output").resolve()
    slide_ids: set[str] = set()
    for index, item in enumerate(slides):
        slide = _require_mapping(item, f"slides[{index}]")
        slide_id = _require_string(slide, "id", f"slides[{index}].id")
        if slide_id in slide_ids:
            raise PackagingError(f"slides[{index}].id duplicates {slide_id!r}")
        slide_ids.add(slide_id)

        file_name = _require_string(slide, "file", f"slides[{index}].file")
        slide_path = (output_path / file_name).resolve()
        _project_local_path(project_path, slide_path, f"slides[{index}].file")

    return manifest


def validate_slide_fragment(html_text: str, slide_id: str, source_path: Path) -> str:
    """Return the normalized root section or raise PackagingError."""
    soup = BeautifulSoup(html_text, "html.parser")
    if soup.find("script") is not None:
        raise PackagingError(f"{source_path}: slide fragments must not contain script elements")

    if any(
        isinstance(node, NavigableString) and not isinstance(node, Comment) and node.strip()
        for node in soup.contents
    ):
        raise PackagingError(f"{source_path}: expected exactly one slide root section")

    roots = [element for element in soup.contents if getattr(element, "name", None)]
    if len(roots) != 1 or roots[0].name != "section" or "pm-slide" not in roots[0].get("class", []):
        raise PackagingError(f"{source_path}: expected exactly one slide root section")

    root = roots[0]
    if root.get("data-slide-id") != slide_id:
        raise PackagingError(f"{source_path}: data-slide-id must match {slide_id!r}")
    return str(root)
