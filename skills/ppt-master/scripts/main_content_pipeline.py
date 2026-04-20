#!/usr/bin/env python3
"""Main content sync and comment application for ppt-master skeleton projects."""

from __future__ import annotations

import copy
import re
from pathlib import Path

from skeleton_utils import (
    build_asset_manifest_markdown,
    clean_md_inline,
    parse_design_spec,
)


CONTENT_FILE = "main_content.md"

TAKEAWAY_PREFIXES = ("收口：", "一句收口：", "一句总论：", "Takeaway:")
ASSET_LINE_PREFIXES = ("使用图像：", "使用素材：", "使用图像:", "使用素材:", "主画面使用", "辅助画面使用")


def derive_content_bullets(slide: dict) -> list[str]:
    bullets: list[str] = []
    for item in slide.get("content_items", []):
        if any(item.startswith(prefix) for prefix in TAKEAWAY_PREFIXES):
            continue
        if any(item.startswith(prefix) for prefix in ASSET_LINE_PREFIXES):
            continue
        bullets.append(item)
    return bullets


def spec_to_main_content_model(spec: dict) -> dict:
    asset_map: dict[str, list[dict]] = {}
    for slide in spec["slides"]:
        entries: list[dict] = []
        for name in slide.get("asset_names", []):
            asset_meta = spec["image_index"].get(name, {})
            entries.append(
                {
                    "filename": name,
                    "status": asset_meta.get("Status", "Existing"),
                    "type": asset_meta.get("Type", ""),
                    "purpose": asset_meta.get("Purpose", ""),
                    "source_path": f"images/{name}",
                }
            )
        asset_map[slide["key"]] = entries

    slides: list[dict] = []
    for slide in spec["slides"]:
        slides.append(
            {
                "key": slide["key"],
                "number": slide["number"],
                "heading_title": slide["heading_title"],
                "title": slide["title"],
                "takeaway": slide["takeaway"],
                "bullets": derive_content_bullets(slide),
                "assets": asset_map.get(slide["key"], []),
                "review_notes": [],
                "layout": slide.get("layout", ""),
                "visualization": slide.get("visualization", ""),
            }
        )
    return {
        "project_name": spec["project_name"],
        "language": spec["language"],
        "slides": slides,
    }


def build_main_content_markdown(spec: dict, model: dict | None = None) -> str:
    model = copy.deepcopy(model or spec_to_main_content_model(spec))
    zh = model.get("language") == "zh"
    lines: list[str] = []
    if zh:
        lines.extend(
            [
                f"# {model['project_name']} 主内容",
                "",
                "## 使用说明",
                "",
                "- 这是骨架层主内容文件，人类优先编辑这里。",
                "- 内容类批注默认回写这里，再同步到 design_spec.md。",
                "- 未能自动应用的自由批注会保留到 `Review Notes`。",
                "",
                "## Slides",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"# {model['project_name']} Main Content",
                "",
                "## Notes",
                "",
                "- This is the primary human-editable content file for the skeleton.",
                "- Content review comments should update this file first, then sync to design_spec.md.",
                "- Free-form comments that cannot be applied automatically are preserved in `Review Notes`.",
                "",
                "## Slides",
                "",
            ]
        )

    for slide in model["slides"]:
        lines.extend(
            [
                f"### Slide {slide['key']} - {slide['heading_title']}",
                f"- Title: {slide['title']}",
                f"- Takeaway: {slide['takeaway'] or ('待补充' if zh else 'TBD')}",
                "- Bullets:",
            ]
        )
        if slide.get("bullets"):
            for bullet in slide["bullets"]:
                lines.append(f"  - {bullet}")
        else:
            lines.append("  - None")

        lines.append("- Assets:")
        if slide.get("assets"):
            for asset in slide["assets"]:
                lines.append(
                    f"  - `{asset['filename']}` | {asset.get('status', '')} | {asset.get('type', '')} | {asset.get('purpose', '')} | `{asset.get('source_path', '')}`"
                )
        else:
            lines.append("  - None")

        lines.append("- Review Notes:")
        if slide.get("review_notes"):
            for note in slide["review_notes"]:
                lines.append(f"  - {note}")
        else:
            lines.append("  - None")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def parse_main_content(project_path: Path, spec: dict | None = None) -> dict:
    path = project_path / CONTENT_FILE
    if not path.exists():
        if spec is None:
            spec = parse_design_spec(project_path)
        return spec_to_main_content_model(spec)

    text = path.read_text(encoding="utf-8")
    language = "zh" if re.search(r"[\u3400-\u9fff]", text) else "en"
    project_name_match = re.search(r"^#\s+(.+?)\s+(?:主内容|Main Content)$", text, re.M)
    project_name = project_name_match.group(1).strip() if project_name_match else project_path.name

    slide_pattern = re.compile(
        r"^###\s+Slide\s+(\d+)\s+-\s+(.+?)\n(.*?)(?=^###\s+Slide\s+\d+\s+-\s+|\Z)",
        re.M | re.S,
    )
    slides: list[dict] = []
    for match in slide_pattern.finditer(text):
        key = match.group(1).zfill(2)
        heading_title = match.group(2).strip()
        block = match.group(3)
        title_match = re.search(r"^- Title:\s*(.+)$", block, re.M)
        takeaway_match = re.search(r"^- Takeaway:\s*(.+)$", block, re.M)
        bullets = _parse_nested_field(block, "Bullets")
        assets = _parse_assets_block(_parse_nested_field(block, "Assets"))
        review_notes = _parse_nested_field(block, "Review Notes")
        slides.append(
            {
                "key": key,
                "number": int(key),
                "heading_title": heading_title,
                "title": (title_match.group(1).strip() if title_match else heading_title),
                "takeaway": normalize_placeholder(takeaway_match.group(1).strip() if takeaway_match else ""),
                "bullets": normalize_placeholder_list(bullets),
                "assets": assets,
                "review_notes": normalize_placeholder_list(review_notes),
            }
        )
    return {
        "project_name": project_name,
        "language": language,
        "slides": slides,
    }


def _parse_nested_field(block: str, field_name: str) -> list[str]:
    lines = block.splitlines()
    capture = False
    results: list[str] = []
    for line in lines:
        if re.match(rf"^- {re.escape(field_name)}:\s*$", line):
            capture = True
            continue
        if capture and re.match(r"^- [A-Za-z ]+:\s*", line):
            capture = False
        if capture and re.match(r"^\s*-\s+", line):
            results.append(re.sub(r"^\s*-\s+", "", line).strip())
    return results


def _parse_assets_block(lines: list[str]) -> list[dict]:
    assets: list[dict] = []
    for line in lines:
        if line.lower() == "none":
            continue
        parts = [part.strip().strip("`") for part in line.split("|")]
        if not parts or not parts[0]:
            continue
        assets.append(
            {
                "filename": parts[0],
                "status": parts[1] if len(parts) > 1 else "",
                "type": parts[2] if len(parts) > 2 else "",
                "purpose": parts[3] if len(parts) > 3 else "",
                "source_path": parts[4] if len(parts) > 4 else f"images/{parts[0]}",
            }
        )
    return assets


def normalize_placeholder(value: str) -> str:
    return "" if value in {"TBD", "待补充", "None", "-"} else value


def normalize_placeholder_list(values: list[str]) -> list[str]:
    return [value for value in values if value not in {"TBD", "待补充", "None", "-"}]


def write_main_content(project_path: Path, spec: dict, model: dict) -> Path:
    path = project_path / CONTENT_FILE
    path.write_text(build_main_content_markdown(spec, model), encoding="utf-8")
    return path


def build_asset_manifest_from_model(spec: dict, model: dict) -> str:
    spec_copy = copy.deepcopy(spec)
    model_by_key = {slide["key"]: slide for slide in model["slides"]}
    for slide in spec_copy["slides"]:
        current = model_by_key.get(slide["key"])
        if not current:
            continue
        slide["title"] = current["title"]
        slide["takeaway"] = current["takeaway"]
        slide["asset_names"] = [asset["filename"] for asset in current.get("assets", [])]
        for asset in current.get("assets", []):
            spec_copy["image_index"].setdefault(
                asset["filename"],
                {
                    "Filename": asset["filename"],
                    "Status": asset.get("status", ""),
                    "Type": asset.get("type", ""),
                    "Purpose": asset.get("purpose", ""),
                },
            )
    return build_asset_manifest_markdown(spec_copy)


def build_content_outline_from_model(spec: dict, model: dict) -> str:
    model_by_key = {slide["key"]: slide for slide in model["slides"]}
    lines = ["## IX. Content Outline", "", "### Part 1: " + spec["use_case"], ""]
    for slide in spec["slides"]:
        current = model_by_key.get(slide["key"])
        if not current:
            continue
        lines.append(f"#### Slide {slide['key']} - {current['heading_title']}")
        lines.append("")
        lines.append(f"- **Layout**: {slide.get('layout', '-') or '-'}")
        lines.append(f"- **Title**: {current['title']}")
        if slide.get("visualization"):
            lines.append(f"- **Visualization**: {slide['visualization']}")
        lines.append("- **Content**:")
        bullets = current.get("bullets", [])
        if bullets:
            for bullet in bullets:
                lines.append(f"  - {bullet}")
        if current.get("assets"):
            asset_names = " / ".join(asset["filename"] for asset in current["assets"])
            asset_label = "使用素材" if spec["language"] == "zh" else "Assets"
            lines.append(f"  - {asset_label}：{asset_names}")
        takeaway_prefix = "收口" if spec["language"] == "zh" else "Takeaway"
        lines.append(f"  - {takeaway_prefix}：{current.get('takeaway') or ('待补充' if spec['language'] == 'zh' else 'TBD')}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def sync_design_spec_from_main_content(project_path: Path, spec: dict, model: dict) -> Path:
    spec_path = project_path / "design_spec.md"
    text = spec["design_spec_text"]
    new_section = build_content_outline_from_model(spec, model)
    new_text = re.sub(
        r"^## IX\. Content Outline\n.*?(?=^## X\. Speaker Notes Requirements)",
        new_section + "\n\n",
        text,
        flags=re.M | re.S,
    )
    spec_path.write_text(new_text, encoding="utf-8")
    return spec_path


def sync_asset_manifest_from_main_content(project_path: Path, spec: dict, model: dict) -> Path:
    asset_manifest_path = project_path / "asset_manifest.md"
    asset_manifest_path.write_text(build_asset_manifest_from_model(spec, model), encoding="utf-8")
    return asset_manifest_path


def split_comment_commands(text: str) -> list[str]:
    commands: list[str] = []
    for line in text.splitlines():
        for part in re.split(r"[；;]+", line):
            part = part.strip()
            if part:
                commands.append(part)
    return commands


def _split_items(text: str) -> list[str]:
    items = [item.strip() for item in re.split(r"[；;\n]+", text) if item.strip()]
    return items


def apply_comment_text(slide: dict, comment_text: str) -> dict:
    updated = copy.deepcopy(slide)
    review_notes = updated.setdefault("review_notes", [])
    applied: list[str] = []
    for command in split_comment_commands(comment_text):
        matched = False

        title_match = re.match(
            r"^(?:标题|title)(?:\s*(?:改成|修改为|更新为))?\s*(?::|：|=)?\s*(.+)$",
            command,
            re.I,
        )
        if title_match:
            updated["title"] = title_match.group(1).strip()
            applied.append("title")
            matched = True

        takeaway_match = re.match(
            r"^(?:takeaway|结论|一句话判断|收口)(?:\s*(?:改成|修改为|更新为))?\s*(?::|：|=)?\s*(.+)$",
            command,
            re.I,
        )
        if takeaway_match:
            updated["takeaway"] = takeaway_match.group(1).strip()
            applied.append("takeaway")
            matched = True

        replace_bullets = re.match(
            r"^(?:要点|bullets?)(?:\s*(?:改成|修改为|更新为))?\s*(?::|：|=)?\s*(.+)$",
            command,
            re.I,
        )
        if replace_bullets:
            updated["bullets"] = _split_items(replace_bullets.group(1))
            applied.append("bullets")
            matched = True

        add_bullets = re.match(r"^(?:新增要点|添加要点|增加要点|add bullet(?:s)?)\s*(?::|：|=)?\s*(.+)$", command, re.I)
        if add_bullets:
            updated.setdefault("bullets", [])
            for item in _split_items(add_bullets.group(1)):
                if item not in updated["bullets"]:
                    updated["bullets"].append(item)
            applied.append("add_bullets")
            matched = True

        remove_bullets = re.match(r"^(?:删除要点|移除要点|remove bullet(?:s)?)\s*(?::|：|=)?\s*(.+)$", command, re.I)
        if remove_bullets:
            targets = _split_items(remove_bullets.group(1))
            updated["bullets"] = [item for item in updated.get("bullets", []) if item not in targets]
            applied.append("remove_bullets")
            matched = True

        replace_bullet = re.match(r"^(?:替换要点|replace bullet)\s*(?::|：|=)?\s*(.+?)\s*(?:=>|->|→)\s*(.+)$", command, re.I)
        if replace_bullet:
            old = replace_bullet.group(1).strip()
            new = replace_bullet.group(2).strip()
            updated["bullets"] = [new if item == old else item for item in updated.get("bullets", [])]
            applied.append("replace_bullet")
            matched = True

        replace_assets = re.match(
            r"^(?:素材|assets?)(?:\s*(?:改成|修改为|更新为))?\s*(?::|：|=)?\s*(.+)$",
            command,
            re.I,
        )
        if replace_assets:
            updated["assets"] = _parse_assets_command(replace_assets.group(1))
            applied.append("assets")
            matched = True

        add_asset = re.match(r"^(?:新增素材|添加素材|增加素材|add asset(?:s)?)\s*(?::|：|=)?\s*(.+)$", command, re.I)
        if add_asset:
            updated.setdefault("assets", [])
            for asset in _parse_assets_command(add_asset.group(1)):
                if not any(existing["filename"] == asset["filename"] for existing in updated["assets"]):
                    updated["assets"].append(asset)
            applied.append("add_assets")
            matched = True

        remove_asset = re.match(r"^(?:删除素材|移除素材|remove asset(?:s)?)\s*(?::|：|=)?\s*(.+)$", command, re.I)
        if remove_asset:
            targets = {item.split("|", 1)[0].strip().strip("`") for item in _split_items(remove_asset.group(1))}
            updated["assets"] = [asset for asset in updated.get("assets", []) if asset["filename"] not in targets]
            applied.append("remove_assets")
            matched = True

        if not matched:
            if command not in review_notes:
                review_notes.append(command)

    updated["review_notes"] = [note for note in review_notes if note and note.lower() != "none"]
    return {"slide": updated, "applied": applied, "review_notes": updated["review_notes"]}


def _parse_assets_command(text: str) -> list[dict]:
    assets: list[dict] = []
    raw_items = [item.strip() for item in re.split(r"[；;\n]+", text) if item.strip()]
    for raw in raw_items:
        parts = [part.strip().strip("`") for part in raw.split("|")]
        filename = parts[0]
        assets.append(
            {
                "filename": filename,
                "status": parts[1] if len(parts) > 1 else "Existing",
                "type": parts[2] if len(parts) > 2 else "",
                "purpose": parts[3] if len(parts) > 3 else "",
                "source_path": parts[4] if len(parts) > 4 else f"images/{filename}",
            }
        )
    return assets


def apply_comments_to_main_content(project_path: Path, comments: dict[str, str]) -> dict:
    spec = parse_design_spec(project_path)
    model = parse_main_content(project_path, spec)
    slide_index = {slide["key"]: idx for idx, slide in enumerate(model["slides"])}
    updated_keys: list[str] = []
    review_note_counts: dict[str, int] = {}

    for key, comment_text in comments.items():
        normalized_key = str(key).zfill(2)
        if normalized_key not in slide_index or not comment_text.strip():
            continue
        result = apply_comment_text(model["slides"][slide_index[normalized_key]], comment_text)
        model["slides"][slide_index[normalized_key]] = result["slide"]
        updated_keys.append(normalized_key)
        review_note_counts[normalized_key] = len(result["review_notes"])

    main_content_path = write_main_content(project_path, spec, model)
    design_spec_path = sync_design_spec_from_main_content(project_path, spec, model)
    asset_manifest_path = sync_asset_manifest_from_main_content(project_path, spec, model)

    return {
        "main_content_path": str(main_content_path),
        "design_spec_path": str(design_spec_path),
        "asset_manifest_path": str(asset_manifest_path),
        "updated_slides": sorted(set(updated_keys)),
        "review_note_counts": review_note_counts,
        "model": model,
    }
