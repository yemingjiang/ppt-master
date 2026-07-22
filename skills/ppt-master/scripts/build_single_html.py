"""Validate source files for an offline single-file HTML presentation."""

from __future__ import annotations

import base64
import html
import json
import mimetypes
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup, Comment, NavigableString


SKILL_DIR = Path(__file__).resolve().parent.parent
HTML_PRESENTATION_ASSET_DIR = SKILL_DIR / "assets" / "html-presentation"
_ASPECT_RATIO_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*$")
_TOKEN_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")
_CSS_HEX_COLOR_PATTERN = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


class PackagingError(ValueError):
    """Raised when presentation sources cannot be packaged safely."""


RESOURCE_ATTRS = {
    "img": ("src", "srcset"),
    "video": ("src", "poster"),
    "audio": ("src",),
    "source": ("src", "srcset"),
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


class OfflineResourcePackager:
    """Embed project-local runtime assets into HTML and CSS data URIs."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.embedded_count = 0
        self.warnings: list[str] = []

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
            for tag in soup.find_all(tag_name):
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

        self._rewrite_stylesheets(soup, source_path, iframe_stack)
        self._rewrite_scripts(soup, source_path, iframe_stack)
        self._rewrite_iframes(soup, source_path, iframe_stack)
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
        try:
            contents = path.read_bytes()
        except OSError as error:
            raise PackagingError(f"unable to read resource: {path}") from error

        media_type = _EXPLICIT_MEDIA_TYPES.get(path.suffix.lower())
        if media_type is None:
            media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(contents).decode("ascii")
        self.embedded_count += 1
        return f"data:{media_type};base64,{encoded}"

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

    def _rewrite_stylesheets(
        self, soup: BeautifulSoup, source_path: Path, iframe_stack: tuple[Path, ...]
    ) -> None:
        for link in list(soup.find_all("link")):
            rel = {value.lower() for value in link.get("rel", [])}
            if "stylesheet" not in rel or not link.get("href"):
                continue
            stylesheet_path = self._resolve_resource(link["href"], source_path)
            if not iframe_stack:
                continue
            try:
                css_text = stylesheet_path.read_text(encoding="utf-8")
            except OSError as error:
                raise PackagingError(f"unable to read stylesheet: {stylesheet_path}") from error
            style = soup.new_tag("style")
            style.append(NavigableString(self.rewrite_css(css_text, stylesheet_path)))
            link.replace_with(style)

    def _rewrite_scripts(
        self, soup: BeautifulSoup, source_path: Path, iframe_stack: tuple[Path, ...]
    ) -> None:
        for script in soup.find_all("script"):
            reference = script.get("src")
            if not reference:
                continue
            script_path = self._resolve_resource(reference, source_path)
            if not iframe_stack:
                continue
            try:
                script_text = script_path.read_text(encoding="utf-8")
            except OSError as error:
                raise PackagingError(f"unable to read script: {script_path}") from error
            del script["src"]
            script.clear()
            script.append(NavigableString(script_text))

    def _rewrite_iframes(
        self, soup: BeautifulSoup, source_path: Path, iframe_stack: tuple[Path, ...]
    ) -> None:
        for iframe in soup.find_all("iframe"):
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


def render_document(
    manifest: dict[str, object],
    slides: list[str],
    project_css: str,
    notes: dict[str, dict],
) -> str:
    """Render validated presentation sources into the portable presentation shell."""
    title = _require_string(manifest, "title")
    language = _require_string(manifest, "lang")
    replacements = {
        "LANG": html.escape(language, quote=True),
        "TITLE": html.escape(title, quote=True),
        "THEME_TOKENS": _theme_tokens_css(manifest),
        "RUNTIME_CSS": _read_presentation_asset("runtime.css"),
        "THEME_CSS": _read_presentation_asset("executive-red.css"),
        "PROJECT_CSS": project_css,
        "SLIDES": "\n".join(slides),
        "NOTES_JSON": _safe_json(notes),
        "RUNTIME_JS": _read_presentation_asset("runtime.js"),
    }
    shell = _read_presentation_asset("shell.html")
    return re.sub(r"\{\{([A-Z_]+)\}\}", lambda match: replacements[match.group(1)], shell)
