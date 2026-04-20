#!/usr/bin/env python3
"""Shared helpers for ppt-master skeleton docs and review preview."""

from __future__ import annotations

import re
from pathlib import Path


SECTION_HEADERS = {
    "project": "## I. Project Information",
    "visual": "## III. Visual Theme",
    "typography": "## IV. Typography System",
    "layout": "## V. Layout Principles",
    "icons": "## VI. Icon Usage Specification",
    "images": "## VIII. Image Resource List (if needed)",
    "outline": "## IX. Content Outline",
    "notes": "## X. Speaker Notes Requirements",
}


def has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", text))


def detect_language(text: str) -> str:
    return "zh" if has_cjk(text) else "en"


def slide_sort_key(path: Path) -> tuple[int, str]:
    match = re.match(r"^(\d+)[_\-]?(.*)$", path.stem)
    if match:
        return (int(match.group(1)), match.group(2))
    return (10**9, path.stem)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def extract_section(text: str, header: str) -> str:
    pattern = re.compile(rf"^{re.escape(header)}\n(.*?)(?=^##\s+[IVXLCDM]+\.\s|\Z)", re.M | re.S)
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def find_heading_index(lines: list[str], heading: str) -> int | None:
    for idx, line in enumerate(lines):
        if line.strip() == heading:
            return idx
    return None


def collect_table(lines: list[str], start_idx: int) -> list[dict[str, str]]:
    idx = start_idx
    while idx < len(lines) and not lines[idx].lstrip().startswith("|"):
        idx += 1
    block: list[str] = []
    while idx < len(lines) and lines[idx].lstrip().startswith("|"):
        block.append(lines[idx].rstrip())
        idx += 1
    if len(block) < 2:
        return []
    headers = [cell.strip() for cell in block[0].strip().strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for line in block[2:]:
        parts = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(parts) != len(headers):
            continue
        rows.append(dict(zip(headers, parts)))
    return rows


def normalize_key(text: str) -> str:
    stripped = re.sub(r"`", "", text)
    stripped = re.sub(r"\*\*", "", stripped)
    return stripped.strip()


def clean_md_inline(text: str) -> str:
    return normalize_key(text).replace("\\|", "|")


def parse_kv_table(rows: list[dict[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows:
        if len(row) < 2:
            continue
        keys = list(row.keys())
        key = normalize_key(row.get(keys[0], ""))
        value = row.get(keys[1], "").strip()
        if key:
            result[key] = value
    return result


def split_key_points(text: str) -> list[str]:
    if not text:
        return []
    if re.search(r"[①②③④⑤⑥⑦⑧⑨⑩]", text):
        matches = re.findall(r"[①②③④⑤⑥⑦⑧⑨⑩]\s*([^①②③④⑤⑥⑦⑧⑨⑩]+)", text)
        points = [item.strip(" ：:;；") for item in matches if item.strip(" ：:;；")]
        if points:
            return points
    return [item.strip() for item in re.split(r"[;；]|(?:\s{2,})", text) if item.strip()]


def parse_bullets(text: str) -> list[str]:
    return [re.sub(r"^\s*-\s+", "", line).strip() for line in text.splitlines() if re.match(r"^\s*-\s+", line)]


def parse_design_spec(project_path: Path) -> dict:
    spec_path = project_path / "design_spec.md"
    spec_text = read_text(spec_path)
    if not spec_text:
        raise FileNotFoundError(f"Missing design_spec.md: {spec_path}")

    language = detect_language(spec_text)
    project_section = extract_section(spec_text, SECTION_HEADERS["project"])
    visual_section = extract_section(spec_text, SECTION_HEADERS["visual"])
    typography_section = extract_section(spec_text, SECTION_HEADERS["typography"])
    layout_section = extract_section(spec_text, SECTION_HEADERS["layout"])
    icons_section = extract_section(spec_text, SECTION_HEADERS["icons"])
    images_section = extract_section(spec_text, SECTION_HEADERS["images"])
    outline_section = extract_section(spec_text, SECTION_HEADERS["outline"])
    notes_section = extract_section(spec_text, SECTION_HEADERS["notes"])

    project_rows = collect_table(project_section.splitlines(), 0)
    project_info = parse_kv_table(project_rows)

    visual_lines = visual_section.splitlines()
    color_rows = collect_table(visual_lines, find_heading_index(visual_lines, "### Color Scheme") or 0)
    visual_bullets = parse_bullets(visual_section)
    visual_theme: dict[str, str] = {}
    for bullet in visual_bullets:
        if ":" in bullet:
            key, value = bullet.split(":", 1)
            visual_theme[normalize_key(key)] = value.strip()

    typography_lines = typography_section.splitlines()
    font_rows = collect_table(typography_lines, find_heading_index(typography_lines, "### Font Plan") or 0)
    size_rows = collect_table(typography_lines, find_heading_index(typography_lines, "### Font Size Hierarchy") or 0)
    baseline_match = re.search(r"Baseline:\s*Body font size\s*=\s*([0-9]+)px", typography_section)
    font_stack_match = re.search(r"Font stack:\s*`([^`]+)`", typography_section)

    layout_lines = layout_section.splitlines()
    mode_rows = collect_table(layout_lines, find_heading_index(layout_lines, "### Common Layout Modes") or 0)
    spacing_rows = collect_table(layout_lines, find_heading_index(layout_lines, "### Spacing Specification") or 0)
    page_structure_match = re.search(r"### Page Structure\n(.*?)(?=\n### |\Z)", layout_section, re.S)
    page_structure = parse_bullets(page_structure_match.group(1)) if page_structure_match else []

    icons_lines = icons_section.splitlines()
    icon_rows = collect_table(icons_lines, find_heading_index(icons_lines, "### Recommended Icon List (fill as needed)") or 0)

    image_lines = images_section.splitlines()
    image_rows = collect_table(image_lines, 0)
    image_index = {row.get("Filename", "").strip(): row for row in image_rows if row.get("Filename", "").strip()}

    slides: list[dict] = []
    slide_pattern = re.compile(
        r"^####\s+Slide\s+(\d+)\s+-\s+(.+?)\n(.*?)(?=^####\s+Slide\s+\d+\s+-\s+|\Z)",
        re.M | re.S,
    )
    for match in slide_pattern.finditer(outline_section):
        slide_no = int(match.group(1))
        heading_title = match.group(2).strip()
        block = match.group(3).strip()
        title_match = re.search(r"^- \*\*Title\*\*:\s*(.+)$", block, re.M)
        layout_match = re.search(r"^- \*\*Layout\*\*:\s*(.+)$", block, re.M)
        viz_match = re.search(r"^- \*\*Visualization\*\*:\s*(.+)$", block, re.M)

        content_items: list[str] = []
        in_content = False
        for line in block.splitlines():
            if re.match(r"^- \*\*Content\*\*:", line):
                in_content = True
                continue
            if in_content and re.match(r"^- \*\*.+\*\*:", line):
                in_content = False
            if in_content and re.match(r"^\s*-\s+", line):
                content_items.append(re.sub(r"^\s*-\s+", "", line).strip())

        takeaway = ""
        for item in content_items:
            for prefix in ("收口：", "一句收口：", "一句总论：", "Takeaway:"):
                if item.startswith(prefix):
                    takeaway = item.split("：", 1)[1].strip() if "：" in item else item.split(":", 1)[1].strip()
                    break
            if takeaway:
                break

        asset_names: list[str] = []
        for item in content_items:
            asset_names.extend(re.findall(r"[\w\-.]+\.(?:png|jpg|jpeg|webp|gif|mp4|mov)", item, re.I))
        asset_names = list(dict.fromkeys(asset_names))

        slides.append(
            {
                "number": slide_no,
                "key": f"{slide_no:02d}",
                "stem": f"{slide_no:02d}_{heading_title}",
                "heading_title": heading_title,
                "title": title_match.group(1).strip() if title_match else heading_title,
                "layout": layout_match.group(1).strip() if layout_match else "",
                "visualization": viz_match.group(1).strip() if viz_match else "",
                "content_items": content_items,
                "takeaway": takeaway,
                "asset_names": asset_names,
            }
        )

    notes_bullets = parse_bullets(notes_section)
    notes_requirements: dict[str, str] = {}
    for bullet in notes_bullets:
        if ":" in bullet:
            key, value = bullet.split(":", 1)
            notes_requirements[normalize_key(key)] = value.strip()

    return {
        "project_path": str(project_path),
        "project_name": project_info.get("Project Name", project_path.name),
        "canvas_format": project_info.get("Canvas Format", ""),
        "page_count": project_info.get("Page Count", str(len(slides))),
        "design_style": project_info.get("Design Style", ""),
        "target_audience": project_info.get("Target Audience", ""),
        "use_case": project_info.get("Use Case", ""),
        "created_date": project_info.get("Created Date", ""),
        "language": language,
        "visual_theme": visual_theme,
        "colors": color_rows,
        "font_plan": font_rows,
        "font_sizes": size_rows,
        "body_baseline_px": int(baseline_match.group(1)) if baseline_match else 18,
        "font_stack": font_stack_match.group(1) if font_stack_match else "",
        "page_structure": page_structure,
        "layout_modes": mode_rows,
        "spacing": spacing_rows,
        "icons": icon_rows,
        "image_index": image_index,
        "slides": slides,
        "notes_requirements": notes_requirements,
        "design_spec_text": spec_text,
    }


def parse_notes_total(project_path: Path) -> dict[str, dict]:
    notes_text = read_text(project_path / "notes" / "total.md")
    if not notes_text:
        return {}

    blocks = re.split(r"\n---\n", notes_text.strip())
    notes_map: dict[str, dict] = {}
    for block in blocks:
        lines = [line.rstrip() for line in block.splitlines()]
        if not lines or not lines[0].startswith("# "):
            continue
        heading = lines[0][2:].strip()
        key_match = re.match(r"^(\d+)", heading)
        key = key_match.group(1).zfill(2) if key_match else heading

        script_lines: list[str] = []
        key_points = ""
        duration = ""
        for line in lines[1:]:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("要点：") or stripped.startswith("Key points:"):
                key_points = stripped.split("：", 1)[1].strip() if "：" in stripped else stripped.split(":", 1)[1].strip()
                continue
            if stripped.startswith("时长：") or stripped.startswith("Duration:"):
                duration = stripped.split("：", 1)[1].strip() if "：" in stripped else stripped.split(":", 1)[1].strip()
                continue
            script_lines.append(stripped)

        notes_map[key] = {
            "heading": heading,
            "script": "\n".join(script_lines).strip(),
            "key_points": split_key_points(key_points),
            "duration": duration,
        }
    return notes_map


def build_default_asset_map(spec: dict) -> dict[str, list[dict]]:
    asset_map: dict[str, list[dict]] = {}
    for slide in spec["slides"]:
        entries: list[dict] = []
        for name in slide["asset_names"]:
            asset_meta = spec["image_index"].get(name, {})
            entries.append(
                {
                    "filename": name,
                    "status": asset_meta.get("Status", "Unspecified"),
                    "type": asset_meta.get("Type", ""),
                    "purpose": asset_meta.get("Purpose", ""),
                    "source_path": f"images/{name}",
                }
            )
        asset_map[slide["key"]] = entries
    return asset_map


def parse_asset_manifest(project_path: Path, spec: dict) -> dict[str, list[dict]]:
    manifest_path = project_path / "asset_manifest.md"
    text = read_text(manifest_path)
    if not text:
        return build_default_asset_map(spec)

    slide_pattern = re.compile(
        r"^###\s+Slide\s+(\d+)\s+-\s+(.+?)\n(.*?)(?=^###\s+Slide\s+\d+\s+-\s+|\Z)",
        re.M | re.S,
    )
    asset_map: dict[str, list[dict]] = {}
    for match in slide_pattern.finditer(text):
        key = match.group(1).zfill(2)
        block = match.group(3)
        assets: list[dict] = []
        in_assets = False
        for line in block.splitlines():
            if re.match(r"^- \*\*Assets\*\*:", line):
                in_assets = True
                continue
            if in_assets and re.match(r"^- \*\*.+\*\*:", line):
                in_assets = False
            if in_assets and re.match(r"^\s*-\s+", line):
                value = re.sub(r"^\s*-\s+", "", line).strip()
                if value.lower() in {"none", "none yet", "暂无", "无"}:
                    continue
                parts = [part.strip().strip("`") for part in value.split("|")]
                assets.append(
                    {
                        "filename": parts[0] if len(parts) > 0 else "",
                        "status": parts[1] if len(parts) > 1 else "",
                        "type": parts[2] if len(parts) > 2 else "",
                        "purpose": parts[3] if len(parts) > 3 else "",
                        "source_path": parts[4] if len(parts) > 4 else "",
                    }
                )
        asset_map[key] = [asset for asset in assets if asset.get("filename")]
    if asset_map:
        return asset_map
    return build_default_asset_map(spec)


def build_style_sheet_markdown(spec: dict) -> str:
    zh = spec["language"] == "zh"
    project_name = spec["project_name"]
    min_font = 16 if spec["body_baseline_px"] >= 18 else 14
    lines: list[str] = []
    if zh:
        lines.extend(
            [
                f"# {project_name} 样式表",
                "",
                "## 风格定位",
                "",
                f"- 设计风格：`{spec['design_style']}`",
                f"- 目标受众：`{spec['target_audience']}`",
                f"- 使用场景：`{spec['use_case']}`",
                f"- 主题描述：`{spec['visual_theme'].get('Theme', '')} / {spec['visual_theme'].get('Tone', '')}`".rstrip(" / "),
                "",
                "## 配色体系",
                "",
            ]
        )
        for row in spec["colors"]:
            lines.append(f"- {clean_md_inline(row.get('Role', 'Color'))} `{clean_md_inline(row.get('HEX', ''))}`")
            if row.get("Purpose"):
                lines.append(f"  用途：{clean_md_inline(row['Purpose'])}")
        lines.extend(["", "## 字体", ""])
        for row in spec["font_plan"]:
            lines.append(
                f"- {clean_md_inline(row.get('Role', 'Role'))}：`{clean_md_inline(row.get('Chinese', ''))}` / `{clean_md_inline(row.get('English', ''))}`"
            )
        if spec["font_stack"]:
            lines.append(f"- 字体栈：`{spec['font_stack']}`")
        lines.extend(["", "## 字级体系", "", f"- `最小字体`：`{min_font}`", f"- `正文基线`：`{spec['body_baseline_px']}`"])
        for row in spec["font_sizes"]:
            lines.append(
                f"- `{clean_md_inline(row.get('Purpose', 'Level'))}`：{clean_md_inline(row.get('Weight', ''))}，建议区间 `{clean_md_inline(row.get('18px baseline (dense)', ''))}`"
            )
        lines.extend(["", "## 版式规则", ""])
        for item in spec["page_structure"]:
            lines.append(f"- {clean_md_inline(item)}")
        if spec["layout_modes"]:
            lines.extend(["", "## 常用布局模式", ""])
            for row in spec["layout_modes"]:
                lines.append(f"- `{clean_md_inline(row.get('Mode', ''))}`：{clean_md_inline(row.get('Suitable Scenarios', ''))}")
        if spec["spacing"]:
            lines.extend(["", "## 间距和组件", ""])
            for row in spec["spacing"]:
                lines.append(
                    f"- `{clean_md_inline(row.get('Element', ''))}`：建议 `{clean_md_inline(row.get('Recommended Range', ''))}`，当前项目 `{clean_md_inline(row.get('Current Project', ''))}`"
                )
        if spec["icons"]:
            lines.extend(["", "## 图标规则", ""])
            for row in spec["icons"]:
                lines.append(
                    f"- `{clean_md_inline(row.get('Purpose', ''))}`：`{clean_md_inline(row.get('Icon Path', ''))}`（{clean_md_inline(row.get('Page', ''))}）"
                )
        lines.extend(
            [
                "",
                "## 交接给 PowerPoint 的要求",
                "",
                "- 保留标题、正文、卡片、页码的统一层级，不在成品阶段重新发明一套样式。",
                "- 优先通过减少文字和调整容器解决拥挤问题，不把正文字号压到最小值以下。",
                "- PowerPoint 成品阶段只做成品化和原生可编辑化，不回退重写内容结构。",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"# {project_name} Style Sheet",
                "",
                "## Style Positioning",
                "",
                f"- Design style: `{spec['design_style']}`",
                f"- Target audience: `{spec['target_audience']}`",
                f"- Use case: `{spec['use_case']}`",
                "",
                "## Color System",
                "",
            ]
        )
        for row in spec["colors"]:
            lines.append(f"- {clean_md_inline(row.get('Role', 'Color'))} `{clean_md_inline(row.get('HEX', ''))}`")
            if row.get("Purpose"):
                lines.append(f"  Purpose: {clean_md_inline(row['Purpose'])}")
        lines.extend(["", "## Typography", ""])
        for row in spec["font_plan"]:
            lines.append(f"- {clean_md_inline(row.get('Role', 'Role'))}: `{clean_md_inline(row.get('English', ''))}`")
        if spec["font_stack"]:
            lines.append(f"- Font stack: `{spec['font_stack']}`")
        lines.extend(["", "## Type Scale", "", f"- Minimum font size: `{min_font}`", f"- Body baseline: `{spec['body_baseline_px']}`"])
        for row in spec["font_sizes"]:
            lines.append(f"- `{clean_md_inline(row.get('Purpose', 'Level'))}`: `{clean_md_inline(row.get('18px baseline (dense)', ''))}`")
        lines.extend(["", "## Layout Rules", ""])
        for item in spec["page_structure"]:
            lines.append(f"- {clean_md_inline(item)}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_asset_manifest_markdown(spec: dict) -> str:
    zh = spec["language"] == "zh"
    asset_map = build_default_asset_map(spec)
    used_in: dict[str, list[str]] = {}
    for slide in spec["slides"]:
        label = f"{slide['key']} {slide['title']}"
        for asset in asset_map.get(slide["key"], []):
            used_in.setdefault(asset["filename"], []).append(label)

    lines: list[str] = []
    if zh:
        lines.extend(
            [
                f"# {spec['project_name']} 资产清单",
                "",
                "## 总览",
                "",
                f"- 项目：`{spec['project_name']}`",
                f"- 页面数：`{spec['page_count']}`",
                "- 这份清单用于骨架审稿和 PowerPoint 成品交接。",
                "",
                "## 全局资产索引",
                "",
                "| Asset | Status | Type | Purpose | Source Path | Used In |",
                "| ----- | ------ | ---- | ------- | ----------- | ------- |",
            ]
        )
        for filename, row in spec["image_index"].items():
            lines.append(
                f"| `{filename}` | {clean_md_inline(row.get('Status', ''))} | {clean_md_inline(row.get('Type', ''))} | {clean_md_inline(row.get('Purpose', ''))} | `images/{filename}` | {', '.join(used_in.get(filename, [])) or '-'} |"
            )
        lines.extend(["", "## Slide Mapping", ""])
        for slide in spec["slides"]:
            lines.extend(
                [
                    f"### Slide {slide['key']} - {slide['heading_title']}",
                    f"- **Title**: {slide['title']}",
                    f"- **Takeaway**: {slide['takeaway'] or '待补充'}",
                    f"- **Layout**: {slide['layout'] or '-'}",
                    f"- **Visualization**: {slide['visualization'] or '-'}",
                    "- **Assets**:",
                ]
            )
            slide_assets = asset_map.get(slide["key"], [])
            if slide_assets:
                for asset in slide_assets:
                    lines.append(
                        f"  - `{asset['filename']}` | {asset['status']} | {asset['type']} | {asset['purpose']} | `{asset['source_path']}`"
                    )
            else:
                lines.append("  - None")
            lines.append("")
    else:
        lines.extend(
            [
                f"# {spec['project_name']} Asset Manifest",
                "",
                "## Global Asset Index",
                "",
                "| Asset | Status | Type | Purpose | Source Path | Used In |",
                "| ----- | ------ | ---- | ------- | ----------- | ------- |",
            ]
        )
        for filename, row in spec["image_index"].items():
            lines.append(
                f"| `{filename}` | {clean_md_inline(row.get('Status', ''))} | {clean_md_inline(row.get('Type', ''))} | {clean_md_inline(row.get('Purpose', ''))} | `images/{filename}` | {', '.join(used_in.get(filename, [])) or '-'} |"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"
