"""Validate source files for an offline single-file HTML presentation."""

from __future__ import annotations

import argparse
import base64
import binascii
import html
import json
import mimetypes
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import unquote, unquote_to_bytes, urlsplit

from bs4 import BeautifulSoup, Comment, NavigableString

from skeleton_utils import parse_notes_total


SKILL_DIR = Path(__file__).resolve().parent.parent
HTML_PRESENTATION_ASSET_DIR = SKILL_DIR / "assets" / "html-presentation"
_ASPECT_RATIO_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*$")
_TOKEN_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")
_CSS_HEX_COLOR_PATTERN = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_INVALID_PERCENT_ESCAPE_PATTERN = re.compile(r"%(?![0-9a-fA-F]{2})")
_MAX_IFRAME_NESTING_DEPTH = 16
_MAX_DECODED_DATA_IFRAME_BYTES = 128 * 1024 * 1024
_LARGE_DOCUMENT_WARNING_BYTES = 50 * 1024 * 1024
_VERY_LARGE_DOCUMENT_WARNING_BYTES = 100 * 1024 * 1024
_LARGE_ASSET_WARNING_BYTES = 10 * 1024 * 1024
_LARGE_GIF_WARNING_BYTES = 8 * 1024 * 1024

_RUNTIME_STRINGS = {
    "en": {
        "presentation": "Presentation",
        "controls": "Presentation controls",
        "previous": "Previous slide",
        "next": "Next slide",
        "fullscreen": "Toggle fullscreen",
        "notes": "Notes",
        "notes_toggle": "Toggle speaker notes",
        "notes_title": "Speaker notes",
        "notes_close": "Close speaker notes",
        "help_toggle": "Show shortcut help",
        "help_title": "Presentation controls",
        "help_close": "Close shortcut help",
        "help_keyboard": "Keyboard / remote",
        "help_keyboard_detail": "← ↑ PageUp P · → ↓ PageDown N Space Enter",
        "help_mouse": "Mouse / trackpad",
        "help_mouse_detail": "Click to advance · scroll · horizontal drag",
        "help_touch": "Touch",
        "help_touch_detail": "Swipe horizontally",
        "help_panels": "Panels",
        "help_panels_detail": "F fullscreen · S notes · ? help",
        "no_notes": "No speaker notes for this slide.",
    },
    "zh": {
        "presentation": "演示文稿",
        "controls": "演示控制",
        "previous": "上一页",
        "next": "下一页",
        "fullscreen": "切换全屏",
        "notes": "备注",
        "notes_toggle": "切换演讲者备注",
        "notes_title": "演讲者备注",
        "notes_close": "关闭演讲者备注",
        "help_toggle": "显示快捷键帮助",
        "help_title": "演示控制",
        "help_close": "关闭快捷键帮助",
        "help_keyboard": "键盘 / 翻页笔",
        "help_keyboard_detail": "← ↑ PageUp P · → ↓ PageDown N 空格 Enter",
        "help_mouse": "鼠标 / 触控板",
        "help_mouse_detail": "单击前进 · 滚轮 · 水平拖动",
        "help_touch": "触控",
        "help_touch_detail": "水平轻扫",
        "help_panels": "面板",
        "help_panels_detail": "F 全屏 · S 备注 · ? 帮助",
        "no_notes": "本页没有演讲者备注。",
    },
}


class PackagingError(ValueError):
    """Raised when presentation sources cannot be packaged safely."""


RESOURCE_ATTRS = {
    "img": ("src", "srcset"),
    "video": ("src", "poster"),
    "audio": ("src",),
    "source": ("src", "srcset"),
    "track": ("src",),
    "object": ("data",),
    "embed": ("src",),
    "image": ("href", "xlink:href"),
    "feimage": ("href", "xlink:href"),
}

LINK_RESOURCE_RELS = {"icon", "preload", "modulepreload"}
SVG_FRAGMENT_RESOURCE_ATTRS = {
    ("image", "href"),
    ("image", "xlink:href"),
    ("feimage", "href"),
    ("feimage", "xlink:href"),
}

REMOTE_SCHEMES = {"http", "https", "file", "blob"}

_EXPLICIT_MEDIA_TYPES = {
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".js": "text/javascript",
    ".css": "text/css",
}

_CSS_URL_PATTERN = re.compile(
    r"url\(\s*(?P<quote>['\"]?)(?P<reference>.*?)(?P=quote)\s*\)", re.IGNORECASE
)
_CSS_IMPORT_PATTERN = re.compile(
    r"""@import\s+(?:
        url\(\s*(?P<url_quote>['\"]?)(?P<url_reference>.*?)(?P=url_quote)\s*\)
        |(?P<string_quote>['\"])(?P<string_reference>.*?)(?P=string_quote)
    )\s*(?P<media>[^;]*);""",
    re.IGNORECASE | re.VERBOSE,
)


def _matching_tags(soup: BeautifulSoup, tag_name: str) -> list:
    """Return HTML-parser tags by case-insensitive name, including SVG camel case."""
    return soup.find_all(lambda tag: getattr(tag, "name", "").lower() == tag_name)


def _is_embedded_reference(reference: str, allow_fragment: bool = False) -> bool:
    normalized = reference.strip().lower()
    return normalized.startswith("data:") or (allow_fragment and normalized.startswith("#"))


def _allows_fragment_reference(tag_name: str, attribute: str) -> bool:
    return (tag_name, attribute) in SVG_FRAGMENT_RESOURCE_ATTRS


class OfflineResourcePackager:
    """Embed project-local runtime assets into HTML and CSS data URIs."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.embedded_count = 0
        self.warnings: list[str] = []
        self._data_uri_cache: dict[Path, str] = {}
        self._asset_records: dict[Path, dict[str, object]] = {}

    def rewrite_html(
        self,
        html_text: str,
        source_path: Path,
        iframe_stack: tuple[Path, ...] = (),
    ) -> str:
        """Rewrite local presentation resources relative to ``source_path``."""
        source_path = source_path.resolve()
        soup = BeautifulSoup(html_text, "html.parser")

        for tag_name, attributes in RESOURCE_ATTRS.items():
            for tag in _matching_tags(soup, tag_name):
                for attribute in attributes:
                    reference = tag.get(attribute)
                    if not reference:
                        continue
                    if attribute == "srcset":
                        tag[attribute] = self._rewrite_srcset(reference, source_path)
                    else:
                        tag[attribute] = self._rewrite_reference(reference, source_path)

        for tag in soup.find_all(style=True):
            tag["style"] = self.rewrite_css(tag["style"], source_path)

        for style in soup.find_all("style"):
            css_text = style.get_text()
            style.clear()
            style.append(NavigableString(self.rewrite_css(css_text, source_path)))

        self._rewrite_stylesheets(soup, source_path)
        self._rewrite_scripts(soup, source_path)
        self._rewrite_iframes(soup, source_path, iframe_stack)
        self._reject_external_svg_use(soup)
        return str(soup)

    def rewrite_css(self, css_text: str, source_path: Path) -> str:
        """Embed local CSS ``url(...)`` references relative to ``source_path``."""
        source_path = source_path.resolve()
        return self._rewrite_css(css_text, source_path, (source_path,))

    def _rewrite_css(
        self, css_text: str, source_path: Path, css_stack: tuple[Path, ...]
    ) -> str:
        css_text = _CSS_IMPORT_PATTERN.sub(
            lambda match: self._inline_css_import(match, source_path, css_stack), css_text
        )

        def replace(match: re.Match[str]) -> str:
            reference = match.group("reference").strip()
            rewritten = self._rewrite_reference(reference, source_path)
            if rewritten == reference:
                return match.group(0)
            return f'url("{rewritten}")'

        return _CSS_URL_PATTERN.sub(replace, css_text)

    def to_data_uri(self, path: Path) -> str:
        """Read a project-local resource and return its typed base64 data URI."""
        path = path.resolve()
        self._require_project_local(path, "resource")
        self.embedded_count += 1
        if path in self._data_uri_cache:
            self._asset_records[path]["references"] = (
                int(self._asset_records[path]["references"]) + 1
            )
            return self._data_uri_cache[path]
        try:
            contents = path.read_bytes()
        except OSError as error:
            raise PackagingError(f"unable to read resource: {path}") from error

        media_type = _EXPLICIT_MEDIA_TYPES.get(path.suffix.lower())
        if media_type is None:
            media_type = mimetypes.guess_type(path.name)[0]
        if media_type is None:
            raise PackagingError(f"unsupported or indeterminate MIME type for resource: {path}")
        encoded = base64.b64encode(contents).decode("ascii")
        data_uri = f"data:{media_type};base64,{encoded}"
        self._data_uri_cache[path] = data_uri
        self._asset_records[path] = {
            "path": path,
            "bytes": len(contents),
            "media_type": media_type,
            "extension": path.suffix.lower(),
            "data_uri_bytes": len(data_uri.encode("utf-8")),
            "references": 1,
        }
        return data_uri

    def asset_report(self) -> dict[str, object]:
        """Return stable unique-resource and embedded-payload statistics."""
        assets: list[dict[str, object]] = []
        for path, record in self._asset_records.items():
            references = int(record["references"])
            assets.append(
                {
                    "path": path.relative_to(self.project_root).as_posix(),
                    "bytes": int(record["bytes"]),
                    "media_type": str(record["media_type"]),
                    "extension": str(record["extension"]),
                    "references": references,
                    "embedded_payload_bytes": int(record["data_uri_bytes"]) * references,
                }
            )
        assets.sort(key=lambda item: (-int(item["bytes"]), str(item["path"])))
        return {
            "unique_assets": len(assets),
            "reference_count": self.embedded_count,
            "source_bytes": sum(int(item["bytes"]) for item in assets),
            "embedded_payload_bytes": sum(
                int(item["embedded_payload_bytes"]) for item in assets
            ),
            "largest_assets": assets[:10],
        }

    def _rewrite_reference(self, reference: str, source_path: Path) -> str:
        if self._is_preserved_reference(reference):
            return reference
        path = self._resolve_resource(reference, source_path)
        return self.to_data_uri(path)

    def _rewrite_srcset(self, srcset: str, source_path: Path) -> str:
        candidates = []
        for candidate in self._split_srcset(srcset):
            parts = candidate.strip().split(maxsplit=1)
            if not parts:
                continue
            rewritten = self._rewrite_reference(parts[0], source_path)
            candidates.append(" ".join((rewritten, *parts[1:])))
        return ", ".join(candidates)

    @staticmethod
    def _split_srcset(srcset: str) -> list[str]:
        """Split generated srcset candidates without breaking data URI commas."""
        candidates: list[str] = []
        position = 0
        while position < len(srcset):
            while position < len(srcset) and srcset[position].isspace():
                position += 1
            candidate_start = position
            is_data_uri = srcset[position : position + 5].lower() == "data:"

            while position < len(srcset) and not srcset[position].isspace() and (
                is_data_uri or srcset[position] != ","
            ):
                position += 1

            while position < len(srcset) and srcset[position].isspace():
                position += 1
            while position < len(srcset) and srcset[position] != ",":
                position += 1

            candidate = srcset[candidate_start:position].strip()
            if candidate:
                candidates.append(candidate)
            if position < len(srcset):
                position += 1
        return candidates

    def _inline_css_import(
        self, match: re.Match[str], source_path: Path, css_stack: tuple[Path, ...]
    ) -> str:
        reference = match.group("url_reference") or match.group("string_reference")
        if self._is_preserved_reference(reference):
            return match.group(0)
        stylesheet_path = self._resolve_resource(reference, source_path)
        if stylesheet_path in css_stack:
            cycle = (*css_stack, stylesheet_path)
            chain = " -> ".join(str(path) for path in cycle)
            raise PackagingError(f"CSS @import cycle detected: {chain}")
        try:
            css_text = stylesheet_path.read_text(encoding="utf-8")
        except OSError as error:
            raise PackagingError(f"unable to read stylesheet: {stylesheet_path}") from error
        inlined_css = self._rewrite_css(css_text, stylesheet_path, (*css_stack, stylesheet_path))
        media = match.group("media").strip()
        if media:
            return f"@media {media} {{\n{inlined_css}\n}}"
        return inlined_css

    def _rewrite_stylesheets(self, soup: BeautifulSoup, source_path: Path) -> None:
        for link in list(soup.find_all("link")):
            rel = {value.lower() for value in link.get("rel", [])}
            reference = link.get("href")
            if not reference:
                continue
            if "stylesheet" not in rel:
                if rel.intersection(LINK_RESOURCE_RELS):
                    link["href"] = self._rewrite_reference(reference, source_path)
                continue
            stylesheet_path = self._resolve_resource(reference, source_path)
            try:
                css_text = stylesheet_path.read_text(encoding="utf-8")
            except OSError as error:
                raise PackagingError(f"unable to read stylesheet: {stylesheet_path}") from error
            style = soup.new_tag("style")
            style.append(NavigableString(self.rewrite_css(css_text, stylesheet_path)))
            link.replace_with(style)

    def _rewrite_scripts(self, soup: BeautifulSoup, source_path: Path) -> None:
        for script in soup.find_all("script"):
            reference = script.get("src")
            if not reference:
                continue
            script_path = self._resolve_resource(reference, source_path)
            try:
                script_text = script_path.read_text(encoding="utf-8")
            except OSError as error:
                raise PackagingError(f"unable to read script: {script_path}") from error
            del script["src"]
            script.clear()
            script.append(NavigableString(script_text))

    def _reject_external_svg_use(self, soup: BeautifulSoup) -> None:
        for use in _matching_tags(soup, "use"):
            for attribute in ("href", "xlink:href"):
                reference = use.get(attribute)
                if reference and not reference.strip().startswith("#"):
                    raise PackagingError(
                        "external SVG <use> references are not supported; use a fragment-only reference instead: "
                        f"{reference}"
                    )

    def _rewrite_iframes(
        self, soup: BeautifulSoup, source_path: Path, iframe_stack: tuple[Path, ...]
    ) -> None:
        for iframe in soup.find_all("iframe"):
            if iframe.has_attr("srcdoc"):
                srcdoc = iframe.get("srcdoc", "")
                iframe["srcdoc"] = self.rewrite_html(
                    srcdoc, source_path, (*iframe_stack, source_path)
                )
                # Browsers prioritize srcdoc over src. Removing the ignored fallback keeps the output policy explicit.
                if iframe.has_attr("src"):
                    del iframe["src"]
                continue
            reference = iframe.get("src")
            if not reference or self._is_preserved_reference(reference):
                continue
            iframe_path = self._resolve_resource(reference, source_path)
            if iframe_path in iframe_stack:
                cycle = (*iframe_stack, iframe_path)
                chain = " -> ".join(str(path) for path in cycle)
                raise PackagingError(f"iframe cycle detected: {chain}")
            try:
                iframe_html = iframe_path.read_text(encoding="utf-8")
            except OSError as error:
                raise PackagingError(f"unable to read iframe: {iframe_path}") from error
            rewritten = self.rewrite_html(iframe_html, iframe_path, (*iframe_stack, iframe_path))
            encoded = base64.b64encode(rewritten.encode("utf-8")).decode("ascii")
            iframe["src"] = f"data:text/html;base64,{encoded}"
            self.embedded_count += 1

    def _resolve_resource(self, reference: str, source_path: Path) -> Path:
        parsed = urlsplit(reference)
        if parsed.scheme.lower() in REMOTE_SCHEMES or parsed.netloc:
            raise PackagingError(f"remote runtime resources are not supported: {reference}")
        if parsed.scheme:
            raise PackagingError(f"unsupported runtime resource URL: {reference}")
        if not parsed.path:
            raise PackagingError(f"resource URL must include a path: {reference}")
        path = (source_path.parent / unquote(parsed.path)).resolve()
        self._require_project_local(path, "resource")
        return path

    def _require_project_local(self, path: Path, field: str) -> None:
        try:
            path.relative_to(self.project_root)
        except ValueError as error:
            raise PackagingError(f"{field} must stay inside the project: {path}") from error

    @staticmethod
    def _is_preserved_reference(reference: str) -> bool:
        normalized = reference.strip().lower()
        return normalized.startswith("data:") or normalized.startswith("#")


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


def _read_presentation_asset(name: str) -> str:
    """Read a bundled runtime asset relative to the ppt-master skill directory."""
    path = HTML_PRESENTATION_ASSET_DIR / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise PackagingError(f"bundled HTML presentation asset not found: {path}") from error


def _theme_tokens_css(manifest: dict[str, object]) -> str:
    theme = _require_mapping(manifest.get("theme"), "theme")
    tokens = _require_mapping(theme.get("tokens"), "theme.tokens")
    aspect_ratio = _require_string(manifest, "aspect_ratio")
    aspect_match = _ASPECT_RATIO_PATTERN.fullmatch(aspect_ratio)
    if aspect_match is None or float(aspect_match.group(1)) <= 0 or float(aspect_match.group(2)) <= 0:
        raise PackagingError("aspect_ratio must be a positive width / height pair")

    variables = [
        f"  --pm-aspect-ratio: {aspect_match.group(1)} / {aspect_match.group(2)};",
        f"  --pm-aspect-width: {aspect_match.group(1)};",
        f"  --pm-aspect-height: {aspect_match.group(2)};",
    ]
    for name, value in tokens.items():
        if not isinstance(name, str) or not _TOKEN_NAME_PATTERN.fullmatch(name):
            raise PackagingError("theme token names must be lowercase CSS-safe identifiers")
        if not isinstance(value, str) or not _CSS_HEX_COLOR_PATTERN.fullmatch(value):
            raise PackagingError(f"theme.tokens.{name} must be a CSS hex color")
        variables.append(f"  --pm-{name.replace('_', '-')}: {value};")
    return ":root {\n" + "\n".join(variables) + "\n}"


def _safe_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def _runtime_strings(language: str) -> dict[str, str]:
    """Return the supported runtime locale, falling back to English."""
    return _RUNTIME_STRINGS["zh" if language.lower().startswith("zh") else "en"]


def render_document(
    manifest: dict[str, object],
    slides: list[str],
    project_css: str,
    notes: dict[str, dict],
) -> str:
    """Render validated presentation sources into the portable presentation shell."""
    title = _require_string(manifest, "title")
    language = _require_string(manifest, "lang")
    strings = _runtime_strings(language)
    replacements = {
        "LANG": html.escape(language, quote=True),
        "TITLE": html.escape(title, quote=True),
        "PRESENTATION_LABEL": html.escape(strings["presentation"], quote=True),
        "CONTROLS_LABEL": html.escape(strings["controls"], quote=True),
        "PREVIOUS_LABEL": html.escape(strings["previous"], quote=True),
        "NEXT_LABEL": html.escape(strings["next"], quote=True),
        "FULLSCREEN_LABEL": html.escape(strings["fullscreen"], quote=True),
        "NOTES_LABEL": html.escape(strings["notes"], quote=True),
        "NOTES_TOGGLE_LABEL": html.escape(strings["notes_toggle"], quote=True),
        "NOTES_TITLE": html.escape(strings["notes_title"], quote=True),
        "NOTES_CLOSE_LABEL": html.escape(strings["notes_close"], quote=True),
        "HELP_TOGGLE_LABEL": html.escape(strings["help_toggle"], quote=True),
        "HELP_TITLE": html.escape(strings["help_title"], quote=True),
        "HELP_CLOSE_LABEL": html.escape(strings["help_close"], quote=True),
        "HELP_KEYBOARD": html.escape(strings["help_keyboard"], quote=True),
        "HELP_KEYBOARD_DETAIL": html.escape(strings["help_keyboard_detail"], quote=True),
        "HELP_MOUSE": html.escape(strings["help_mouse"], quote=True),
        "HELP_MOUSE_DETAIL": html.escape(strings["help_mouse_detail"], quote=True),
        "HELP_TOUCH": html.escape(strings["help_touch"], quote=True),
        "HELP_TOUCH_DETAIL": html.escape(strings["help_touch_detail"], quote=True),
        "HELP_PANELS": html.escape(strings["help_panels"], quote=True),
        "HELP_PANELS_DETAIL": html.escape(strings["help_panels_detail"], quote=True),
        "THEME_TOKENS": _theme_tokens_css(manifest),
        "RUNTIME_CSS": _read_presentation_asset("runtime.css"),
        "THEME_CSS": _read_presentation_asset("executive-red.css"),
        "PROJECT_CSS": project_css,
        "SLIDES": "\n".join(slides),
        "NOTES_JSON": _safe_json(notes),
        "RUNTIME_DATA_JSON": _safe_json({"noNotes": strings["no_notes"]}),
        "RUNTIME_JS": _read_presentation_asset("runtime.js"),
    }
    shell = _read_presentation_asset("shell.html")
    return re.sub(r"\{\{([A-Z_]+)\}\}", lambda match: replacements[match.group(1)], shell)


def _read_text(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise PackagingError(f"{label} not found: {path}") from error
    except OSError as error:
        raise PackagingError(f"unable to read {label}: {path}") from error


def _build_notes(manifest: dict[str, object], project_path: Path) -> dict[str, dict]:
    notes_by_key = parse_notes_total(project_path)
    notes_source = project_path / "notes" / "total.md"
    notes: dict[str, dict] = {}
    slides = manifest.get("slides")
    if not isinstance(slides, list):
        raise PackagingError("slides must be an array")
    for index, item in enumerate(slides):
        slide = _require_mapping(item, f"slides[{index}]")
        slide_id = _require_string(slide, "id", f"slides[{index}].id")
        notes_key = slide.get("notes_key", slide_id)
        if not isinstance(notes_key, str) or not notes_key:
            raise PackagingError(f"slides[{index}].notes_key must be a non-empty string")
        if notes_key not in notes_by_key:
            raise PackagingError(
                f"slides[{index}] (slide id {slide_id!r}) notes_key {notes_key!r} "
                f"was not found in speaker-notes source: {notes_source}. "
                "Notes headings are normalized to their slide key "
                "(for example '# 01 Cover' becomes '01'); omit notes_key to use the slide id."
            )
        notes[slide_id] = notes_by_key[notes_key]
    return notes


def _decode_html_data_uri(reference: str) -> str:
    """Decode a bounded HTML data URI or raise an actionable packaging error."""
    data_uri = reference.strip()
    try:
        metadata, payload = data_uri[5:].split(",", 1)
    except ValueError as error:
        raise PackagingError("iframe data URI is malformed: missing payload separator") from error

    metadata_parts = [part.strip() for part in metadata.split(";")]
    if not metadata_parts or metadata_parts[0].lower() != "text/html":
        media_type = metadata_parts[0] if metadata_parts else ""
        raise PackagingError(
            f"iframe data URI must use the text/html media type, got {media_type or 'none'}"
        )

    charset = "utf-8"
    is_base64 = False
    for parameter in metadata_parts[1:]:
        if parameter.lower() == "base64":
            if is_base64:
                raise PackagingError("iframe data URI is malformed: duplicate base64 marker")
            is_base64 = True
            continue
        if not parameter or "=" not in parameter:
            raise PackagingError(
                f"iframe data URI is malformed: invalid media-type parameter {parameter!r}"
            )
        name, value = (part.strip() for part in parameter.split("=", 1))
        if not name or not value:
            raise PackagingError(
                f"iframe data URI is malformed: invalid media-type parameter {parameter!r}"
            )
        if name.lower() == "charset":
            charset = value.strip("\"'")

    if _INVALID_PERCENT_ESCAPE_PATTERN.search(payload):
        raise PackagingError("iframe data URI is malformed: invalid percent escape in payload")
    if len(payload) > _MAX_DECODED_DATA_IFRAME_BYTES * 4 + 4:
        raise PackagingError(
            "iframe data URI decoded payload exceeds "
            f"{_MAX_DECODED_DATA_IFRAME_BYTES} bytes"
        )

    encoded_payload = unquote_to_bytes(payload)
    if is_base64:
        maximum_base64_bytes = 4 * ((_MAX_DECODED_DATA_IFRAME_BYTES + 2) // 3)
        if len(encoded_payload) > maximum_base64_bytes:
            raise PackagingError(
                "iframe data URI decoded payload exceeds "
                f"{_MAX_DECODED_DATA_IFRAME_BYTES} bytes"
            )
        try:
            decoded_payload = base64.b64decode(encoded_payload, validate=True)
        except (binascii.Error, ValueError) as error:
            raise PackagingError("iframe data URI contains malformed base64 payload") from error
    else:
        decoded_payload = encoded_payload

    if len(decoded_payload) > _MAX_DECODED_DATA_IFRAME_BYTES:
        raise PackagingError(
            "iframe data URI decoded payload exceeds "
            f"{_MAX_DECODED_DATA_IFRAME_BYTES} bytes"
        )
    try:
        return decoded_payload.decode(charset)
    except LookupError as error:
        raise PackagingError(f"iframe data URI declares unsupported charset {charset!r}") from error
    except UnicodeDecodeError as error:
        raise PackagingError(
            f"iframe data URI payload is not decodable as charset {charset!r}"
        ) from error


def _validate_offline_document(
    document: str,
    *,
    _iframe_depth: int = 0,
    _active_data_iframes: tuple[str, ...] = (),
) -> None:
    """Reject remaining local or remote runtime resource references before writing."""
    soup = BeautifulSoup(document, "html.parser")
    for tag_name, attributes in RESOURCE_ATTRS.items():
        for tag in _matching_tags(soup, tag_name):
            for attribute in attributes:
                reference = tag.get(attribute)
                if not reference:
                    continue
                if attribute == "srcset":
                    references = [candidate.strip().split(maxsplit=1)[0] for candidate in OfflineResourcePackager._split_srcset(reference)]
                else:
                    references = [reference]
                for item in references:
                    if not _is_embedded_reference(
                        item, _allows_fragment_reference(tag_name, attribute)
                    ):
                        raise PackagingError(f"unresolved runtime resource remains in output: {item}")

    for iframe in soup.find_all("iframe"):
        if _iframe_depth >= _MAX_IFRAME_NESTING_DEPTH:
            raise PackagingError(
                f"iframe nesting depth exceeds {_MAX_IFRAME_NESTING_DEPTH} levels"
            )
        if iframe.has_attr("srcdoc"):
            _validate_offline_document(
                iframe.get("srcdoc", ""),
                _iframe_depth=_iframe_depth + 1,
                _active_data_iframes=_active_data_iframes,
            )
            continue
        reference = iframe.get("src")
        if not reference:
            continue
        normalized_reference = reference.strip()
        if not normalized_reference.lower().startswith("data:"):
            raise PackagingError(f"unresolved iframe remains in output: {reference}")
        if normalized_reference in _active_data_iframes:
            raise PackagingError("iframe data URI cycle detected in nested iframe chain")
        iframe_document = _decode_html_data_uri(normalized_reference)
        try:
            _validate_offline_document(
                iframe_document,
                _iframe_depth=_iframe_depth + 1,
                _active_data_iframes=(*_active_data_iframes, normalized_reference),
            )
        except PackagingError as error:
            raise PackagingError(
                f"iframe data URI at nesting level {_iframe_depth + 1} "
                f"contains invalid offline document: {error}"
            ) from error
    for link in soup.find_all("link"):
        rel = {value.lower() for value in link.get("rel", [])}
        if "stylesheet" in rel:
            raise PackagingError(f"unresolved stylesheet remains in output: {link.get('href', '')}")
        if rel.intersection(LINK_RESOURCE_RELS):
            reference = link.get("href")
            if reference and not _is_embedded_reference(reference):
                raise PackagingError(f"unresolved runtime link remains in output: {reference}")
    for script in soup.find_all("script"):
        if script.get("src"):
            raise PackagingError(f"unresolved script remains in output: {script['src']}")
    for use in _matching_tags(soup, "use"):
        for attribute in ("href", "xlink:href"):
            reference = use.get(attribute)
            if reference and not reference.strip().startswith("#"):
                raise PackagingError(
                    "external SVG <use> reference remains in output; only fragment-only references are supported: "
                    f"{reference}"
                )


def _default_output_path(project_path: Path) -> Path:
    return project_path / "exports" / f"{project_path.name}.single.html"


def _write_atomically(output_path: Path, document: str) -> int:
    """Write a complete document beside its target, then replace the target once."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = document.encode("utf-8")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(payload)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, output_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
    return len(payload)


def _assemble_single_html(
    project_path: Path,
) -> tuple[str, dict[str, object], OfflineResourcePackager, int]:
    """Validate and assemble the final document without writing the export."""
    project_path = project_path.resolve()
    manifest = load_manifest(project_path)
    packager = OfflineResourcePackager(project_path)
    html_output = project_path / "html_output"

    project_css_path = html_output / "presentation.css"
    project_css = packager.rewrite_css(_read_text(project_css_path, "project stylesheet"), project_css_path)
    slides: list[str] = []
    manifest_slides = manifest.get("slides")
    if not isinstance(manifest_slides, list):
        raise PackagingError("slides must be an array")
    for index, item in enumerate(manifest_slides):
        slide = _require_mapping(item, f"slides[{index}]")
        slide_id = _require_string(slide, "id", f"slides[{index}].id")
        file_name = _require_string(slide, "file", f"slides[{index}].file")
        source_path = (html_output / file_name).resolve()
        _project_local_path(project_path, source_path, f"slides[{index}].file")
        fragment = validate_slide_fragment(_read_text(source_path, "slide fragment"), slide_id, source_path)
        slides.append(packager.rewrite_html(fragment, source_path))

    document = render_document(manifest, slides, project_css, _build_notes(manifest, project_path))
    _validate_offline_document(document)
    return document, manifest, packager, len(slides)


def _build_warnings(document_bytes: int, packager: OfflineResourcePackager) -> list[str]:
    warnings = list(packager.warnings)
    if document_bytes > _LARGE_DOCUMENT_WARNING_BYTES:
        warnings.append(
            "Generated HTML exceeds 50 MB; test opening speed on the actual presentation machine."
        )
    if document_bytes > _VERY_LARGE_DOCUMENT_WARNING_BYTES:
        warnings.append("Generated HTML exceeds 100 MB and may be slow to open in a browser.")
    asset_report = packager.asset_report()
    for asset in asset_report["largest_assets"]:
        asset_bytes = int(asset["bytes"])
        asset_path = str(asset["path"])
        if asset_bytes > _LARGE_ASSET_WARNING_BYTES:
            warnings.append(
                f"Large embedded asset ({asset_bytes} bytes): {asset_path}."
            )
        if str(asset["extension"]) == ".gif" and asset_bytes > _LARGE_GIF_WARNING_BYTES:
            warnings.append(
                f"Large GIF ({asset_bytes} bytes): {asset_path}. "
                "Run optimize_single_html_media.py to inspect the presentation-sized MP4 recommendation; "
                "do not transcode automatically."
            )
    return warnings


def check_single_html(project_path: Path) -> dict[str, object]:
    """Run complete packaging validation without writing an export."""
    project_path = project_path.resolve()
    document, _manifest, packager, slide_count = _assemble_single_html(project_path)
    estimated_bytes = len(document.encode("utf-8"))
    return {
        "status": "ok",
        "mode": "check",
        "project_path": str(project_path),
        "planned_output_html": str(_default_output_path(project_path).resolve()),
        "slides": slide_count,
        "embedded_assets": packager.embedded_count,
        "estimated_bytes": estimated_bytes,
        "media": packager.asset_report(),
        "warnings": _build_warnings(estimated_bytes, packager),
    }


def build_single_html(project_path: Path, output_path: Path | None = None) -> dict[str, object]:
    """Build an offline, self-contained HTML presentation without altering a prior target on failure."""
    project_path = project_path.resolve()
    document, _manifest, packager, slide_count = _assemble_single_html(project_path)
    output_path = (output_path or _default_output_path(project_path)).resolve()
    bytes_written = _write_atomically(output_path, document)
    return {
        "status": "ok",
        "mode": "build",
        "project_path": str(project_path),
        "output_html": str(output_path),
        "output_file_url": output_path.as_uri(),
        "slides": slide_count,
        "embedded_assets": packager.embedded_count,
        "bytes": bytes_written,
        "media": packager.asset_report(),
        "warnings": _build_warnings(bytes_written, packager),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an offline, self-contained HTML presentation from html_output/presentation.json.",
        epilog=(
            "Examples:\n"
            "  python3 build_single_html.py projects/quarterly-review --check --json\n"
            "  python3 build_single_html.py projects/quarterly-review\n"
            "  python3 build_single_html.py projects/quarterly-review --output exports/review.html\n"
            "  python3 build_single_html.py projects/quarterly-review --json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("project_path", type=Path, help="Path to the presentation project directory.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Output HTML file. Default: <project_path>/exports/<project_name>.single.html.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run complete manifest, notes, resource, and offline validation without writing an export.",
    )
    parser.add_argument("--json", action="store_true", help="Print a single machine-readable JSON object.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check and args.output is not None:
            raise PackagingError("--check cannot be combined with --output")
        result = (
            check_single_html(args.project_path)
            if args.check
            else build_single_html(args.project_path, args.output)
        )
    except (OSError, PackagingError, ValueError) as error:
        if args.json:
            print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False, separators=(",", ":")))
        else:
            print(f"Error: {error}", file=os.sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    elif args.check:
        print(f"Check passed: {result['planned_output_html']}")
        print(f"Slides: {result['slides']}")
        print(f"Embedded resources: {result['embedded_assets']}")
        print(f"Estimated output bytes: {result['estimated_bytes']}")
        warnings = result["warnings"]
        print(f"Warnings: {len(warnings)} (details on stderr)" if warnings else "Warnings: none")
        for warning in warnings:
            print(f"Warning: {warning}", file=os.sys.stderr)
    else:
        print(f"Saved: {result['output_html']}")
        print(f"Slides: {result['slides']}")
        print(f"Embedded resources: {result['embedded_assets']}")
        print(f"Output bytes: {result['bytes']}")
        warnings = result["warnings"]
        print(f"Warnings: {len(warnings)} (details on stderr)" if warnings else "Warnings: none")
        for warning in warnings:
            print(f"Warning: {warning}", file=os.sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
