#!/usr/bin/env python3
"""Analyze GIF usage in ppt-master single-file HTML slides and optionally transcode it."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

try:
    from PIL import Image
except ImportError:  # pragma: no cover - optional dependency
    Image = None


TARGETS = {
    "1080p": {"width": 1920, "height": 1080, "overscan": 1.5},
    "4k": {"width": 3840, "height": 2160, "overscan": 1.15},
}
DEFAULT_MIN_BYTES = 8 * 1024 * 1024
ENCODING_PROFILE = "h264-yuv420p-crf23-v1"
COMMON_LONG_EDGES = (240, 320, 480, 640, 854, 960, 1280, 1600, 1920, 2560, 3200, 3840)
SVG_EXTENSIONS = {".html", ".htm", ".svg"}
GIF_EXTENSIONS = {".gif"}
REMOTE_SCHEMES = {"http", "https", "data", "blob", "file"}
LOOP_VIDEO_ATTRIBUTES = {
    "autoplay": True,
    "muted": True,
    "loop": True,
    "playsinline": True,
    "preload": "auto",
}


class MediaOptimizationError(RuntimeError):
    """Raised when media analysis or optimization cannot proceed safely."""


@dataclass(frozen=True)
class GifMetadata:
    width: int
    height: int
    frames: int | None
    duration_ms: int | None
    file_size: int


class SvgImageParser(HTMLParser):
    """Collect SVG GIF placements and previously optimized HTML video overlays."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._svg_stack: list[dict[str, str]] = []
        self._foreign_object_stack: list[dict[str, str]] = []
        self.records: list[tuple[dict[str, str], dict[str, str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._handle_tag(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._handle_tag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag == "foreignobject" and self._foreign_object_stack:
            self._foreign_object_stack.pop()
        elif normalized_tag == "svg" and self._svg_stack:
            self._svg_stack.pop()

    def _handle_tag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized_tag = tag.lower()
        normalized_attrs = {key.lower(): value or "" for key, value in attrs}
        if normalized_tag == "svg":
            self._svg_stack.append(normalized_attrs)
            return
        if normalized_tag == "foreignobject" and self._svg_stack:
            self._foreign_object_stack.append(normalized_attrs)
            return
        if normalized_tag == "image" and self._svg_stack:
            normalized_attrs["_source_kind"] = "image"
            self.records.append((dict(self._svg_stack[-1]), normalized_attrs))
            return
        if (
            normalized_tag == "video"
            and self._svg_stack
            and self._foreign_object_stack
            and normalized_attrs.get("data-pm-source-gif")
        ):
            placement_attrs = dict(self._foreign_object_stack[-1])
            placement_attrs.update(
                {
                    "href": normalized_attrs["data-pm-source-gif"],
                    "preserveaspectratio": normalized_attrs.get(
                        "data-pm-preserve-aspect-ratio", "xMidYMid meet"
                    ),
                    "_source_kind": "foreignobject-video",
                    "_optimized_src": normalized_attrs.get("src", ""),
                    "_placement_id": normalized_attrs.get("data-pm-placement-id", ""),
                }
            )
            self.records.append((dict(self._svg_stack[-1]), placement_attrs))
            return
        if (
            normalized_tag == "video"
            and not self._svg_stack
            and normalized_attrs.get("data-pm-source-gif")
            and normalized_attrs.get("data-pm-layout-box")
            and normalized_attrs.get("data-pm-svg-viewbox")
        ):
            layout_box = normalized_attrs["data-pm-layout-box"].replace(",", " ").split()
            if len(layout_box) != 4:
                return
            self.records.append(
                (
                    {"viewbox": normalized_attrs["data-pm-svg-viewbox"]},
                    {
                        "href": normalized_attrs["data-pm-source-gif"],
                        "x": layout_box[0],
                        "y": layout_box[1],
                        "width": layout_box[2],
                        "height": layout_box[3],
                        "preserveaspectratio": normalized_attrs.get(
                            "data-pm-preserve-aspect-ratio", "xMidYMid meet"
                        ),
                        "_source_kind": "overlay-video",
                        "_optimized_src": normalized_attrs.get("src", ""),
                        "_placement_id": normalized_attrs.get("data-pm-placement-id", ""),
                    },
                )
            )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze GIF usage in html_output/slides and recommend or create MP4 replacements "
            "for ppt-master single-file HTML presentations."
        ),
        epilog=(
            "Examples:\n"
            "  python3 optimize_single_html_media.py projects/ai-lab-demo --json\n"
            "  python3 optimize_single_html_media.py projects/ai-lab-demo --target 4k --min-bytes 8000000\n"
            "  python3 optimize_single_html_media.py projects/ai-lab-demo --apply --json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("project_path", type=Path, help="Presentation project directory.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print one JSON object to stdout.",
    )
    parser.add_argument(
        "--target",
        choices=tuple(TARGETS),
        default="1080p",
        help="Presentation playback target. Defaults to 1080p.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Transcode recommended GIFs to H.264 MP4 into html_output/media_optimized/. "
            "Replace matching final-HTML GIF placements with looping video. "
            "Original GIFs and source SVGs are never modified."
        ),
    )
    parser.add_argument(
        "--min-bytes",
        type=int,
        default=DEFAULT_MIN_BYTES,
        help=(
            "Only analyze GIFs whose source size is at least this many bytes. "
            f"Defaults to {DEFAULT_MIN_BYTES} (8 MiB); use 0 to include every GIF."
        ),
    )
    return parser.parse_args()


def _parse_gif_header(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(10)
    if len(header) < 10 or header[:6] not in {b"GIF87a", b"GIF89a"}:
        raise MediaOptimizationError(f"not a valid GIF file: {path}")
    width, height = struct.unpack("<HH", header[6:10])
    return width, height


def read_gif_metadata(path: Path) -> GifMetadata:
    width, height = _parse_gif_header(path)
    frames: int | None = None
    duration_ms: int | None = None
    if Image is not None:
        with Image.open(path) as image:
            width, height = image.size
            try:
                frames = int(getattr(image, "n_frames", 1))
            except Exception:  # pragma: no cover - Pillow edge behavior
                frames = None
            total_duration = 0
            if frames is not None:
                for frame_index in range(frames):
                    image.seek(frame_index)
                    total_duration += int(image.info.get("duration", 0))
                duration_ms = total_duration
    return GifMetadata(
        width=width,
        height=height,
        frames=frames,
        duration_ms=duration_ms,
        file_size=path.stat().st_size,
    )


def _parse_numeric(token: str, *, relative_to: float | None = None) -> float | None:
    value = token.strip()
    if not value:
        return None
    if value.endswith("%"):
        if relative_to is None:
            return None
        try:
            return relative_to * float(value[:-1]) / 100.0
        except ValueError:
            return None
    normalized = value.removesuffix("px")
    try:
        return float(normalized)
    except ValueError:
        return None


def _parse_viewbox(svg_attrs: dict[str, str]) -> tuple[float, float, float, float] | None:
    raw = svg_attrs.get("viewbox", "").replace(",", " ").split()
    if len(raw) != 4:
        return None
    try:
        min_x, min_y, width, height = (float(part) for part in raw)
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return min_x, min_y, width, height


def _resolve_svg_viewport(svg_attrs: dict[str, str]) -> tuple[float, float]:
    viewbox = _parse_viewbox(svg_attrs)
    if viewbox is not None:
        return viewbox[2], viewbox[3]
    width = _parse_numeric(svg_attrs.get("width", ""))
    height = _parse_numeric(svg_attrs.get("height", ""))
    if width and height and width > 0 and height > 0:
        return width, height
    raise MediaOptimizationError(
        "SVG viewport is missing a usable viewBox or width/height; cannot compute display size."
    )


def _normalize_reference(raw_reference: str) -> str | None:
    if not raw_reference:
        return None
    parsed = urlsplit(raw_reference)
    if parsed.scheme.lower() in REMOTE_SCHEMES:
        return None
    reference = unquote(parsed.path or raw_reference).strip()
    if not reference or reference.startswith("#"):
        return None
    return reference


def _resolve_gif_path(project_path: Path, slide_path: Path, raw_reference: str) -> Path | None:
    reference = _normalize_reference(raw_reference)
    if reference is None:
        return None
    candidate = (slide_path.parent / reference).resolve()
    if candidate.suffix.lower() not in GIF_EXTENSIONS:
        return None
    try:
        candidate.relative_to(project_path.resolve())
    except ValueError:
        raise MediaOptimizationError(
            f"GIF reference resolves outside the project: {raw_reference} from {slide_path}"
        )
    return candidate


def _require_project_local(project_path: Path, path: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(project_path.resolve())
    except ValueError as error:
        raise MediaOptimizationError(f"{label} resolves outside the project: {path}") from error
    return resolved


def _fit_mode(preserve_aspect_ratio: str) -> str:
    token = (preserve_aspect_ratio or "").strip()
    if not token:
        return "meet"
    if token == "none":
        return "none"
    parts = token.split()
    return "slice" if "slice" in parts[1:] else "meet"


def _rendered_pixels(
    box_width: float,
    box_height: float,
    source_width: int,
    source_height: int,
    preserve_aspect_ratio: str,
) -> tuple[int, int]:
    fit = _fit_mode(preserve_aspect_ratio)
    if fit == "none":
        return _round_even(box_width), _round_even(box_height)
    width_scale = box_width / source_width
    height_scale = box_height / source_height
    scale = min(width_scale, height_scale) if fit == "meet" else max(width_scale, height_scale)
    return _round_even(source_width * scale), _round_even(source_height * scale)


def _round_even(value: float) -> int:
    rounded = max(2, int(round(value)))
    if rounded % 2:
        rounded += 1
    return rounded


def _bucket_long_edge(target_long_edge: float, source_long_edge: int) -> int:
    if target_long_edge >= source_long_edge:
        return source_long_edge
    for bucket in COMMON_LONG_EDGES:
        if bucket >= target_long_edge:
            return min(bucket, source_long_edge)
    return source_long_edge


def recommend_output_size(
    *,
    source_width: int,
    source_height: int,
    rendered_width: int,
    rendered_height: int,
    target: str,
) -> tuple[int, int]:
    overscan = TARGETS[target]["overscan"]
    scale = max(
        (rendered_width * overscan) / source_width,
        (rendered_height * overscan) / source_height,
    )
    scale = min(scale, 1.0)
    raw_width = source_width * scale
    raw_height = source_height * scale
    source_long = max(source_width, source_height)
    bucket = _bucket_long_edge(max(raw_width, raw_height), source_long)
    if source_width >= source_height:
        ratio = bucket / source_width
        width = bucket
        height = _round_even(source_height * ratio)
    else:
        ratio = bucket / source_height
        width = _round_even(source_width * ratio)
        height = bucket
    return width, height


def classify_usage(target_width: int, target_height: int, visible_width: int, visible_height: int) -> str:
    ratio = (visible_width * visible_height) / float(target_width * target_height)
    if ratio >= 0.35:
        return "background or hero loop"
    if ratio >= 0.14:
        return "primary demo loop"
    if ratio >= 0.05:
        return "supporting visual loop"
    return "small accent loop"


def _sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_output_name(
    source_relpath: str,
    target: str,
    width: int,
    height: int,
    source_sha1: str = "",
) -> str:
    stem = Path(source_relpath).stem
    digest = hashlib.sha1(
        f"{source_relpath}|{source_sha1}|{ENCODING_PROFILE}".encode("utf-8")
    ).hexdigest()[:10]
    return f"{stem}.{target}.{width}x{height}.{digest}.mp4"


def _format_svg_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _object_position(preserve_aspect_ratio: str) -> str:
    alignment = (preserve_aspect_ratio or "xMidYMid meet").split()[0]
    if alignment == "none":
        return "center center"
    horizontal = "left" if "xMin" in alignment else "right" if "xMax" in alignment else "center"
    vertical = "top" if "YMin" in alignment else "bottom" if "YMax" in alignment else "center"
    return f"{horizontal} {vertical}"


def _format_percent(value: float) -> str:
    return f"{value:.8f}".rstrip("0").rstrip(".")


def _video_overlay(
    placement: dict[str, object],
    *,
    source_reference: str,
    optimized_reference: str,
    target: str,
) -> str:
    box = placement["layout_box_units"]
    viewbox = placement["svg_viewbox"]
    preserve = str(placement["preserve_aspect_ratio"])
    fit_mode = str(placement["fit_mode"])
    object_fit = "fill" if fit_mode == "none" else "cover" if fit_mode == "slice" else "contain"
    viewbox_width = float(viewbox["width"])
    viewbox_height = float(viewbox["height"])
    viewbox_min_x = float(viewbox.get("min_x", 0))
    viewbox_min_y = float(viewbox.get("min_y", 0))
    left = (float(box["x"]) - viewbox_min_x) / viewbox_width * 100
    top = (float(box["y"]) - viewbox_min_y) / viewbox_height * 100
    width = float(box["width"]) / viewbox_width * 100
    height = float(box["height"]) / viewbox_height * 100
    escaped_source = html.escape(source_reference, quote=True)
    escaped_optimized = html.escape(optimized_reference, quote=True)
    escaped_preserve = html.escape(preserve, quote=True)
    escaped_placement_id = html.escape(str(placement["placement_id"]), quote=True)
    layout_box = " ".join(
        _format_svg_number(float(box[key])) for key in ("x", "y", "width", "height")
    )
    svg_viewbox = " ".join(
        _format_svg_number(value)
        for value in (viewbox_min_x, viewbox_min_y, viewbox_width, viewbox_height)
    )
    return (
        f'<video class="pm-optimized-video pm-media-overlay" '
        f'data-pm-source-gif="{escaped_source}" '
        f'data-pm-placement-id="{escaped_placement_id}" '
        f'data-pm-preserve-aspect-ratio="{escaped_preserve}" '
        f'data-pm-layout-box="{html.escape(layout_box, quote=True)}" '
        f'data-pm-svg-viewbox="{html.escape(svg_viewbox, quote=True)}" '
        f'data-pm-target="{html.escape(target, quote=True)}" '
        f'src="{escaped_optimized}" autoplay muted loop playsinline preload="auto" '
        f'aria-hidden="true" '
        f'style="position:absolute;z-index:1;display:block;'
        f'left:{_format_percent(left)}%;top:{_format_percent(top)}%;'
        f'width:{_format_percent(width)}%;height:{_format_percent(height)}%;'
        f'object-fit:{object_fit};object-position:{_object_position(preserve)};'
        f'pointer-events:none"></video>'
    )


_IMAGE_TAG_PATTERN = re.compile(r"<image\b[^>]*?/?>", re.IGNORECASE)
_VIDEO_TAG_PATTERN = re.compile(r"<video\b[^>]*>.*?</video\s*>", re.IGNORECASE | re.DOTALL)
_FOREIGN_OBJECT_PATTERN = re.compile(
    r"<foreignObject\b[^>]*>.*?</foreignObject\s*>",
    re.IGNORECASE | re.DOTALL,
)
_SECTION_END_PATTERN = re.compile(r"</section\s*>\s*$", re.IGNORECASE)


def _attribute_value(tag: str, attribute: str) -> str | None:
    match = re.search(
        rf"\b{re.escape(attribute)}\s*=\s*([\"'])(?P<value>.*?)\1",
        tag,
        re.IGNORECASE | re.DOTALL,
    )
    return html.unescape(match.group("value")) if match else None


def _replace_attribute(tag: str, attribute: str, value: str) -> str:
    escaped_value = html.escape(value, quote=True)
    pattern = re.compile(
        rf"(\b{re.escape(attribute)}\s*=\s*)([\"']).*?\2",
        re.IGNORECASE | re.DOTALL,
    )
    if pattern.search(tag):
        return pattern.sub(rf'\1"{escaped_value}"', tag, count=1)
    return tag.replace(">", f' {attribute}="{escaped_value}">', 1)


def _append_overlay(text: str, overlay: str, slide_path: Path) -> str:
    if slide_path.suffix.lower() not in {".html", ".htm"}:
        raise MediaOptimizationError(
            "HTML video overlays require a .html slide fragment with a .pm-slide root; "
            f"cannot safely rewrite {slide_path.name}."
        )
    section_end = _SECTION_END_PATTERN.search(text)
    if section_end is None:
        raise MediaOptimizationError(
            f"unable to append optimized video overlay: missing closing section in {slide_path}"
        )
    return f"{text[:section_end.start()]}  {overlay}\n{section_end.group(0)}"


def _rewrite_slide_placement(
    project_path: Path,
    placement: dict[str, object],
    *,
    optimized_relpath: Path,
    target: str,
) -> bool:
    slide_path = _require_project_local(
        project_path,
        project_path / str(placement["slide"]),
        "slide placement",
    )
    source_reference = str(placement["reference"])
    placement_id = str(placement["placement_id"])
    optimized_path = _require_project_local(
        project_path,
        project_path / optimized_relpath,
        "optimized media",
    )
    optimized_reference = Path(os.path.relpath(optimized_path, slide_path.parent)).as_posix()
    text = slide_path.read_text(encoding="utf-8")

    source_kind = str(placement.get("source_kind", "image"))
    if source_kind == "overlay-video":
        replaced = False

        def update_video(match: re.Match[str]) -> str:
            nonlocal replaced
            tag = match.group(0)
            if replaced:
                return tag
            current_id = _attribute_value(tag, "data-pm-placement-id")
            if current_id:
                if current_id != placement_id:
                    return tag
            elif _attribute_value(tag, "data-pm-source-gif") != source_reference:
                return tag
            replaced = True
            tag = _replace_attribute(tag, "data-pm-placement-id", placement_id)
            tag = _replace_attribute(tag, "src", optimized_reference)
            return _replace_attribute(tag, "data-pm-target", target)

        rewritten = _VIDEO_TAG_PATTERN.sub(update_video, text)
    else:
        replaced = False
        replacement = _video_overlay(
            placement,
            source_reference=source_reference,
            optimized_reference=optimized_reference,
            target=target,
        )

        def remove_original(match: re.Match[str]) -> str:
            nonlocal replaced
            tag = match.group(0)
            if replaced:
                return tag
            if source_kind == "foreignobject-video":
                video_match = _VIDEO_TAG_PATTERN.search(tag)
                if video_match is None:
                    return tag
                video_tag = video_match.group(0)
                current_id = _attribute_value(video_tag, "data-pm-placement-id")
                if current_id:
                    if current_id != placement_id:
                        return tag
                elif _attribute_value(video_tag, "data-pm-source-gif") != source_reference:
                    return tag
            else:
                href = _attribute_value(tag, "href") or _attribute_value(tag, "xlink:href")
                if href != source_reference:
                    return tag
            replaced = True
            return ""

        pattern = (
            _FOREIGN_OBJECT_PATTERN
            if source_kind == "foreignobject-video"
            else _IMAGE_TAG_PATTERN
        )
        rewritten = pattern.sub(remove_original, text)
        if replaced:
            rewritten = _append_overlay(rewritten, replacement, slide_path)

    if not replaced:
        raise MediaOptimizationError(
            f"unable to locate GIF placement for rewrite: {source_reference} in {slide_path}"
        )
    if rewritten == text:
        return False
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=slide_path.parent,
        prefix=f".{slide_path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(rewritten)
        temporary_path = Path(handle.name)
    os.replace(temporary_path, slide_path)
    return True


def _transcode_to_mp4(source_path: Path, output_path: Path, width: int, height: int) -> dict[str, object]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and output_path.stat().st_size > 0:
        return {
            "status": "existing",
            "output_path": str(output_path),
            "bytes": output_path.stat().st_size,
        }
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise MediaOptimizationError(
            "ffmpeg is required for --apply but was not found in PATH. Install ffmpeg or rerun without --apply."
        )
    with tempfile.NamedTemporaryFile(
        dir=output_path.parent,
        prefix=f".{output_path.stem}.",
        suffix=".mp4",
        delete=False,
    ) as handle:
        temporary_output = Path(handle.name)
    temporary_output.unlink(missing_ok=True)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source_path),
        "-an",
        "-movflags",
        "+faststart",
        "-pix_fmt",
        "yuv420p",
        "-vf",
        f"scale={width}:{height}:flags=lanczos:force_original_aspect_ratio=decrease",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "23",
        str(temporary_output),
    ]
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "ffmpeg failed"
            raise MediaOptimizationError(
                f"ffmpeg failed while transcoding {source_path.name}: {detail}"
            )
        if not temporary_output.exists() or temporary_output.stat().st_size == 0:
            raise MediaOptimizationError(
                f"ffmpeg reported success but did not create a usable file: {output_path}"
            )
        os.replace(temporary_output, output_path)
    finally:
        temporary_output.unlink(missing_ok=True)
    return {
        "status": "created",
        "output_path": str(output_path),
        "bytes": output_path.stat().st_size,
    }


def _extract_svg_image_records(slide_path: Path) -> list[tuple[dict[str, str], dict[str, str]]]:
    parser = SvgImageParser()
    parser.feed(slide_path.read_text(encoding="utf-8"))
    parser.close()
    return parser.records


def _iter_slide_files(slides_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in slides_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SVG_EXTENSIONS
    )


def analyze_project(
    project_path: Path,
    *,
    target: str = "1080p",
    apply: bool = False,
    min_bytes: int = DEFAULT_MIN_BYTES,
) -> dict[str, object]:
    project_path = project_path.resolve()
    if min_bytes < 0:
        raise MediaOptimizationError("--min-bytes must be zero or a positive integer.")
    slides_dir = project_path / "html_output" / "slides"
    if not slides_dir.exists():
        raise MediaOptimizationError(
            f"slides directory not found: {slides_dir}. Run the HTML slide export first."
        )
    target_config = TARGETS[target]
    placements_by_gif: dict[Path, list[dict[str, object]]] = {}
    gif_cache: dict[Path, GifMetadata] = {}
    warnings: list[str] = []

    for slide_candidate in _iter_slide_files(slides_dir):
        slide_path = _require_project_local(project_path, slide_candidate, "slide file")
        slide_relpath = slide_path.relative_to(project_path).as_posix()
        for record_index, (svg_attrs, image_attrs) in enumerate(
            _extract_svg_image_records(slide_path)
        ):
            raw_reference = image_attrs.get("href") or image_attrs.get("xlink:href") or ""
            gif_path = _resolve_gif_path(project_path, slide_path, raw_reference)
            if gif_path is None:
                continue
            if not gif_path.exists():
                raise MediaOptimizationError(
                    f"GIF referenced by slide does not exist: {raw_reference} from {slide_path}"
                )
            metadata = gif_cache.setdefault(gif_path, read_gif_metadata(gif_path))
            if metadata.file_size < min_bytes:
                continue
            viewport_width, viewport_height = _resolve_svg_viewport(svg_attrs)
            parsed_viewbox = _parse_viewbox(svg_attrs)
            viewbox_min_x = parsed_viewbox[0] if parsed_viewbox is not None else 0.0
            viewbox_min_y = parsed_viewbox[1] if parsed_viewbox is not None else 0.0
            width_units = _parse_numeric(image_attrs.get("width", ""), relative_to=viewport_width)
            height_units = _parse_numeric(image_attrs.get("height", ""), relative_to=viewport_height)
            x_units = _parse_numeric(image_attrs.get("x", "0"), relative_to=viewport_width) or 0.0
            y_units = _parse_numeric(image_attrs.get("y", "0"), relative_to=viewport_height) or 0.0
            if width_units is None or height_units is None or width_units <= 0 or height_units <= 0:
                warnings.append(
                    f"Skipped {slide_path.relative_to(project_path)} image with unsupported width/height: {raw_reference}"
                )
                continue
            visible_width = _round_even(width_units * target_config["width"] / viewport_width)
            visible_height = _round_even(height_units * target_config["height"] / viewport_height)
            rendered_width, rendered_height = _rendered_pixels(
                visible_width,
                visible_height,
                metadata.width,
                metadata.height,
                image_attrs.get("preserveaspectratio", ""),
            )
            placement_id = image_attrs.get("_placement_id") or hashlib.sha1(
                (
                    f"{slide_relpath}|{record_index}|{raw_reference}|"
                    f"{x_units}|{y_units}|{width_units}|{height_units}"
                ).encode("utf-8")
            ).hexdigest()[:12]
            placements_by_gif.setdefault(gif_path, []).append(
                {
                    "slide": slide_relpath,
                    "reference": raw_reference,
                    "placement_id": placement_id,
                    "source_kind": image_attrs.get("_source_kind", "image"),
                    "svg_viewbox": {
                        "min_x": viewbox_min_x,
                        "min_y": viewbox_min_y,
                        "width": viewport_width,
                        "height": viewport_height,
                    },
                    "layout_box_units": {
                        "x": round(x_units, 3),
                        "y": round(y_units, 3),
                        "width": round(width_units, 3),
                        "height": round(height_units, 3),
                    },
                    "visible_pixels": {"width": visible_width, "height": visible_height},
                    "rendered_pixels": {"width": rendered_width, "height": rendered_height},
                    "preserve_aspect_ratio": image_attrs.get("preserveaspectratio", "xMidYMid meet")
                    or "xMidYMid meet",
                    "fit_mode": _fit_mode(image_attrs.get("preserveaspectratio", "")),
                }
            )

    assets: list[dict[str, object]] = []
    replacement_records: list[dict[str, object]] = []

    for gif_path in sorted(placements_by_gif):
        metadata = gif_cache[gif_path]
        placements = placements_by_gif[gif_path]
        max_visible = max(
            placements,
            key=lambda placement: (
                placement["visible_pixels"]["width"] * placement["visible_pixels"]["height"]
            ),
        )["visible_pixels"]
        max_rendered = max(
            placements,
            key=lambda placement: (
                placement["rendered_pixels"]["width"] * placement["rendered_pixels"]["height"]
            ),
        )["rendered_pixels"]
        recommended_width, recommended_height = recommend_output_size(
            source_width=metadata.width,
            source_height=metadata.height,
            rendered_width=max_rendered["width"],
            rendered_height=max_rendered["height"],
            target=target,
        )
        source_relpath = gif_path.relative_to(project_path).as_posix()
        source_sha1 = _sha1_file(gif_path)
        optimized_relpath = (
            Path("html_output")
            / "media_optimized"
            / _build_output_name(
                source_relpath,
                target,
                recommended_width,
                recommended_height,
                source_sha1,
            )
        )
        asset = {
            "source_relpath": source_relpath,
            "source_sha1": source_sha1,
            "source_bytes": metadata.file_size,
            "source_pixels": {"width": metadata.width, "height": metadata.height},
            "gif": {"frames": metadata.frames, "duration_ms": metadata.duration_ms},
            "placements": placements,
            "max_visible_pixels": max_visible,
            "max_rendered_pixels": max_rendered,
            "recommendation": {
                "target": target,
                "format": "video/mp4",
                "codec": "h264",
                "encoding_profile": ENCODING_PROFILE,
                "pixels": {"width": recommended_width, "height": recommended_height},
                "intended_use": classify_usage(
                    target_config["width"],
                    target_config["height"],
                    max_visible["width"],
                    max_visible["height"],
                ),
            },
            "planned_output_relpath": optimized_relpath.as_posix(),
            "replacement": None,
            "action": "analyze",
        }
        if apply:
            transcode = _transcode_to_mp4(
                gif_path,
                project_path / optimized_relpath,
                recommended_width,
                recommended_height,
            )
            if int(transcode["bytes"]) >= metadata.file_size:
                warnings.append(
                    f"Kept original GIF placements because optimized MP4 was not smaller: "
                    f"{source_relpath} ({metadata.file_size} -> {transcode['bytes']} bytes)."
                )
                asset["action"] = "not_smaller"
                asset["optimized_bytes"] = int(transcode["bytes"])
                assets.append(asset)
                continue
            replacement = {
                "source_relpath": source_relpath,
                "optimized_relpath": optimized_relpath.as_posix(),
                "mime_type": "video/mp4",
                "tag": "video",
                "attributes": {
                    "src": optimized_relpath.as_posix(),
                    **LOOP_VIDEO_ATTRIBUTES,
                },
            }
            asset["replacement"] = replacement
            asset["action"] = str(transcode["status"])
            asset["optimized_bytes"] = int(transcode["bytes"])
            asset["saved_bytes"] = metadata.file_size - int(transcode["bytes"])
            asset["reduction_percent"] = round(
                (metadata.file_size - int(transcode["bytes"])) / metadata.file_size * 100,
                1,
            )
            rewritten_count = sum(
                1
                for placement in placements
                if _rewrite_slide_placement(
                    project_path,
                    placement,
                    optimized_relpath=optimized_relpath,
                    target=target,
                )
            )
            asset["rewritten_placements"] = rewritten_count
            replacement_records.append(replacement)
        assets.append(asset)

    return {
        "status": "ok",
        "project_path": str(project_path),
        "slides_dir": str(slides_dir),
        "target": target,
        "target_pixels": {
            "width": target_config["width"],
            "height": target_config["height"],
        },
        "apply": apply,
        "min_bytes": min_bytes,
        "summary": {
            "gif_count": len(assets),
            "placement_count": sum(len(asset["placements"]) for asset in assets),
            "optimized_count": sum(1 for asset in assets if asset["action"] in {"created", "existing"}),
            "rewritten_placement_count": sum(
                int(asset.get("rewritten_placements", 0)) for asset in assets
            ),
            "source_bytes_optimized": sum(
                int(asset["source_bytes"])
                for asset in assets
                if asset["action"] in {"created", "existing"}
            ),
            "optimized_bytes": sum(
                int(asset.get("optimized_bytes", 0))
                for asset in assets
                if asset["action"] in {"created", "existing"}
            ),
            "saved_bytes": sum(
                int(asset.get("saved_bytes", 0))
                for asset in assets
                if asset["action"] in {"created", "existing"}
            ),
        },
        "assets": assets,
        "replacements": replacement_records,
        "warnings": warnings,
    }


def _print_human_report(result: dict[str, object]) -> None:
    print(
        f"Target: {result['target']} ({result['target_pixels']['width']}x{result['target_pixels']['height']})"
    )
    print(f"GIF assets: {result['summary']['gif_count']}")
    if not result["assets"]:
        print("No GIF references matched the current filters.")
        return
    for asset in result["assets"]:
        print("")
        print(asset["source_relpath"])
        print(
            "  source: "
            f"{asset['source_pixels']['width']}x{asset['source_pixels']['height']}, "
            f"{asset['source_bytes']} bytes"
        )
        print(
            "  max display: "
            f"{asset['max_visible_pixels']['width']}x{asset['max_visible_pixels']['height']} px"
        )
        print(
            "  recommend: "
            f"{asset['recommendation']['pixels']['width']}x{asset['recommendation']['pixels']['height']} "
            f"{asset['recommendation']['format']} ({asset['recommendation']['intended_use']})"
        )
        print(f"  output: {asset['planned_output_relpath']}")
        print(f"  action: {asset['action']}")
        if "saved_bytes" in asset:
            print(
                f"  reduction: {asset['saved_bytes']} bytes "
                f"({asset['reduction_percent']}%)"
            )
    for warning in result["warnings"]:
        print(f"Warning: {warning}", file=sys.stderr)


def main() -> int:
    args = _parse_args()
    try:
        result = analyze_project(
            args.project_path,
            target=args.target,
            apply=args.apply,
            min_bytes=args.min_bytes,
        )
    except (MediaOptimizationError, OSError, ValueError) as error:
        if args.json:
            print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False))
        else:
            print(f"Error: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        _print_human_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
