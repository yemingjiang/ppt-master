#!/usr/bin/env python3
"""Build an HTML review surface for ppt-master skeleton drafts."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
from pathlib import Path

from main_content_pipeline import parse_main_content
from skeleton_utils import parse_asset_manifest, parse_design_spec, parse_notes_total, slide_sort_key


STRINGS = {
    "zh": {
        "eyebrow": "骨架审稿",
        "meta": "先审结构，再审成品。这里默认只看页序、标题、takeaway、notes、素材和批注，不做最终 PowerPoint 细修。",
        "slides": "页数",
        "keyboard": "支持左右键",
        "prev": "上一页",
        "next": "下一页",
        "scope": "推荐审稿范围：结构、结论、素材、备注。",
        "takeaway": "本页 takeaway",
        "notes": "Notes 面板",
        "key_points": "Key Points",
        "duration": "时长",
        "assets": "资产清单",
        "comments": "批注入口",
        "comment_hint": "记录这页的结构、文案、视觉或素材修改意见。内容会自动保存在当前浏览器；支持直接识别“标题改成 / 结论改成 / 要点改成 / 新增要点 / 删除要点 / 素材改成”等命令。",
        "comment_placeholder": "例如：标题改成：Maya 内已打通东亚角色到动画 1.0 链路；结论改成：4 月底可交付初版；新增要点：AI 视频生成已接入验证。",
        "save": "保存批注",
        "copy": "复制当前页",
        "apply": "根据全部批注更新",
        "updating": "正在根据批注更新 main_content.md，并同步 design_spec.md 与预览…",
        "updated": "已根据批注更新 main_content.md，并刷新预览。",
        "update_failed": "更新失败，请确认当前页面由 review_server.py 提供。",
        "no_comments": "还没有可应用的批注。",
        "saved": "已保存到本地浏览器",
        "no_takeaway": "这一页还没有明确 takeaway。",
        "no_notes": "这一页还没有 notes。",
        "no_assets": "这一页暂时没有登记资产。",
        "asset_status": "状态",
        "asset_type": "类型",
        "asset_path": "路径",
        "review_title": "PPT 骨架审稿记录",
    },
    "en": {
        "eyebrow": "Draft Review",
        "meta": "Review structure first. This surface focuses on order, titles, takeaways, notes, assets, and comments before final PowerPoint polish.",
        "slides": "Slides",
        "keyboard": "Arrow keys",
        "prev": "Previous",
        "next": "Next",
        "scope": "Recommended review scope: structure, takeaways, assets, and notes.",
        "takeaway": "Takeaway",
        "notes": "Notes",
        "key_points": "Key Points",
        "duration": "Duration",
        "assets": "Assets",
        "comments": "Comments",
        "comment_hint": "Capture structural, copy, visual, or asset feedback here. Stored locally in this browser. Structured commands such as title/takeaway/bullets/assets updates can be applied automatically.",
        "comment_placeholder": "Example: title: Maya-first East Asian character pipeline; takeaway: v1 ships by end of April; add bullet: AI video generation has been validated.",
        "save": "Save comment",
        "copy": "Copy current",
        "apply": "Apply All Comments",
        "updating": "Applying comments to main_content.md, syncing design_spec.md, and rebuilding preview…",
        "updated": "Applied comments and refreshed the preview.",
        "update_failed": "Update failed. Open this page via review_server.py.",
        "no_comments": "There are no comments to apply yet.",
        "saved": "Saved locally",
        "no_takeaway": "No takeaway yet.",
        "no_notes": "No notes yet.",
        "no_assets": "No assets registered for this slide.",
        "asset_status": "Status",
        "asset_type": "Type",
        "asset_path": "Path",
        "review_title": "PPT Skeleton Review",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an HTML review viewer for a ppt-master project.",
        epilog=(
            "Examples:\n"
            "  python3 scripts/build_preview_html.py projects/demo --source output\n"
            "  python3 scripts/build_preview_html.py projects/demo --source final --title \"Demo Review\"\n"
            "  python3 scripts/build_preview_html.py projects/demo --json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("project_path", help="Path to the ppt-master project directory.")
    parser.add_argument(
        "--source",
        choices=("output", "final"),
        default="output",
        help="Which SVG directory to render into the preview: svg_output or svg_final. Default: output.",
    )
    parser.add_argument(
        "--output",
        help="Output HTML file path. Default: <project_path>/preview/index.html",
    )
    parser.add_argument(
        "--title",
        help="Viewer title. Default: project folder name + ' Draft Review'.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON summary instead of human-readable text.",
    )
    return parser.parse_args()


def safe_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def build_entries(project_path: Path, output_path: Path, source_dir_name: str) -> tuple[list[dict], str, str]:
    source_dir = project_path / source_dir_name
    svg_files = sorted(source_dir.glob("*.svg"), key=slide_sort_key)
    if not svg_files:
        raise FileNotFoundError(f"No SVG files found in {source_dir}")

    spec = parse_design_spec(project_path)
    content_model = parse_main_content(project_path, spec)
    notes_map = parse_notes_total(project_path)
    asset_map = parse_asset_manifest(project_path, spec)
    slide_by_key = {slide["key"]: slide for slide in spec["slides"]}
    content_by_key = {slide["key"]: slide for slide in content_model["slides"]}
    language = "zh" if spec["language"] == "zh" else "en"

    entries: list[dict] = []
    for svg_file in svg_files:
        key_match = re.match(r"^(\d+)", svg_file.stem)
        key = key_match.group(1).zfill(2) if key_match else svg_file.stem
        slide_spec = slide_by_key.get(key, {})
        slide_content = content_by_key.get(key, {})
        notes = notes_map.get(key, {})
        href = Path(os.path.relpath(svg_file, output_path.parent)).as_posix()
        title = slide_content.get("title") or slide_spec.get("title") or svg_file.stem
        takeaway = slide_content.get("takeaway") or slide_spec.get("takeaway") or ""
        entries.append(
            {
                "key": key,
                "number": key,
                "href": href,
                "label": title,
                "title": title,
                "takeaway": takeaway,
                "layout": slide_spec.get("layout", ""),
                "visualization": slide_spec.get("visualization", ""),
                "notes_script": notes.get("script", ""),
                "notes_key_points": notes.get("key_points", []),
                "notes_duration": notes.get("duration", ""),
                "assets": slide_content.get("assets") or asset_map.get(key, []),
            }
        )
    return entries, spec["project_name"], language


def build_html(
    title: str,
    entries: list[dict],
    strings: dict[str, str],
    project_key: str,
    preview_source: str,
) -> str:
    escaped_title = html.escape(title)
    nav_items = []
    for idx, entry in enumerate(entries):
        active = " active" if idx == 0 else ""
        nav_items.append(
            f'<button class="slide-link{active}" data-index="{idx}">'
            f'<span class="slide-no">{html.escape(entry["number"])}</span>'
            f'<span class="slide-label">{html.escape(entry["title"])}</span>'
            f'<span class="slide-comment-dot" data-comment-dot="{html.escape(entry["key"])}"></span>'
            f"</button>"
        )
    entries_json = safe_json(entries)
    strings_json = safe_json(strings)
    first_src = html.escape(entries[0]["href"]) if entries else ""
    first_title = html.escape(entries[0]["title"]) if entries else "No slides"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escaped_title}</title>
  <style>
    :root {{
      --bg: #f4efe9;
      --panel: #ffffff;
      --panel-soft: #fbf8f4;
      --line: #dbcabd;
      --text: #2b221d;
      --muted: #75655a;
      --accent: #a61e16;
      --accent-2: #c64e2e;
      --accent-soft: rgba(166, 30, 22, 0.08);
      --shadow: 0 18px 40px rgba(43, 34, 29, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Inter", "Segoe UI", "PingFang SC", sans-serif;
      background: radial-gradient(circle at top, #faf6f2 0%, var(--bg) 58%);
      color: var(--text);
    }}
    .app {{
      display: grid;
      grid-template-columns: 300px minmax(0, 1fr) 380px;
      min-height: 100vh;
    }}
    .sidebar, .inspector {{
      background: linear-gradient(180deg, #fbf8f5 0%, #f1e8df 100%);
      padding: 24px 18px;
      overflow: auto;
    }}
    .sidebar {{ border-right: 1px solid var(--line); }}
    .inspector {{ border-left: 1px solid var(--line); }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 12px;
      border-radius: 999px;
      background: var(--accent);
      color: #fff;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 14px 0 10px;
      font-size: 24px;
      line-height: 1.2;
    }}
    .meta {{
      margin: 0 0 18px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.6;
    }}
    .stats {{
      display: flex;
      gap: 8px;
      margin-bottom: 18px;
      flex-wrap: wrap;
    }}
    .stat {{
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 12px;
      padding: 8px 10px;
      font-size: 12px;
      color: var(--muted);
    }}
    .nav {{
      display: grid;
      gap: 8px;
    }}
    .slide-link {{
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.8);
      border-radius: 14px;
      padding: 12px 14px;
      display: grid;
      grid-template-columns: 42px minmax(0, 1fr) 10px;
      gap: 10px;
      align-items: center;
      text-align: left;
      cursor: pointer;
      color: inherit;
    }}
    .slide-link:hover {{
      border-color: var(--accent-2);
      transform: translateY(-1px);
    }}
    .slide-link.active {{
      border-color: var(--accent);
      box-shadow: 0 8px 24px rgba(166, 30, 22, 0.12);
      background: #fffaf7;
    }}
    .slide-no {{
      width: 42px;
      height: 42px;
      border-radius: 12px;
      background: var(--accent-soft);
      display: grid;
      place-items: center;
      color: var(--accent);
      font-weight: 700;
      font-size: 14px;
    }}
    .slide-label {{
      min-width: 0;
      font-size: 14px;
      line-height: 1.4;
      font-weight: 600;
    }}
    .slide-comment-dot {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: transparent;
    }}
    .slide-comment-dot.has-comment {{
      background: var(--accent-2);
      box-shadow: 0 0 0 4px rgba(198, 78, 46, 0.14);
    }}
    .main {{
      padding: 24px;
      display: grid;
      grid-template-rows: auto auto 1fr;
      gap: 16px;
      min-width: 0;
    }}
    .toolbar, .summary-card, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: var(--shadow);
    }}
    .toolbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 18px;
    }}
    .toolbar-title {{
      font-size: 18px;
      font-weight: 700;
      line-height: 1.3;
      margin: 0 0 4px;
    }}
    .toolbar-note {{
      font-size: 13px;
      color: var(--muted);
      line-height: 1.5;
    }}
    .nav-buttons {{
      display: flex;
      gap: 8px;
    }}
    .nav-button, .small-button {{
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
      border-radius: 10px;
      padding: 8px 12px;
      cursor: pointer;
      font-size: 13px;
      font-weight: 600;
    }}
    .summary-card {{
      padding: 18px 20px;
    }}
    .summary-label {{
      display: inline-block;
      margin-bottom: 10px;
      padding: 5px 10px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
    }}
    .summary-title {{
      margin: 0 0 10px;
      font-size: 28px;
      line-height: 1.25;
    }}
    .summary-takeaway {{
      margin: 0;
      font-size: 16px;
      line-height: 1.6;
      color: var(--muted);
    }}
    .viewer-shell {{
      background: radial-gradient(circle at top, #ffffff 0%, #ede4db 100%);
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 18px;
      min-height: 0;
      overflow: hidden;
    }}
    iframe {{
      width: 100%;
      height: calc(100vh - 260px);
      border: 0;
      border-radius: 18px;
      background: #fff;
      box-shadow: 0 30px 70px rgba(43, 34, 29, 0.14);
    }}
    .panel {{
      padding: 16px;
      margin-bottom: 14px;
    }}
    .panel:last-child {{ margin-bottom: 0; }}
    .panel-title {{
      font-size: 15px;
      font-weight: 700;
      margin: 0 0 12px;
    }}
    .panel-text {{
      font-size: 14px;
      line-height: 1.6;
      color: var(--muted);
      white-space: pre-wrap;
    }}
    .chips {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 10px;
    }}
    .chip {{
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
    }}
    .asset-list {{
      display: grid;
      gap: 10px;
    }}
    .asset-card {{
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      background: var(--panel-soft);
    }}
    .asset-name {{
      font-size: 14px;
      font-weight: 700;
      margin-bottom: 6px;
      word-break: break-all;
    }}
    .asset-meta {{
      font-size: 12px;
      color: var(--muted);
      line-height: 1.6;
    }}
    textarea {{
      width: 100%;
      min-height: 170px;
      border-radius: 14px;
      border: 1px solid var(--line);
      padding: 12px;
      font: inherit;
      line-height: 1.6;
      resize: vertical;
      background: #fff;
      color: var(--text);
    }}
    .comment-actions {{
      display: flex;
      gap: 8px;
      margin-top: 10px;
      flex-wrap: wrap;
    }}
    .save-state {{
      margin-top: 8px;
      font-size: 12px;
      color: var(--muted);
    }}
    @media (max-width: 1380px) {{
      .app {{
        grid-template-columns: 280px minmax(0, 1fr);
      }}
      .inspector {{
        grid-column: 1 / -1;
        border-left: 0;
        border-top: 1px solid var(--line);
      }}
      iframe {{
        height: 70vh;
      }}
    }}
    @media (max-width: 960px) {{
      .app {{ grid-template-columns: 1fr; }}
      .sidebar {{
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }}
      .toolbar {{
        flex-direction: column;
        align-items: stretch;
      }}
    }}
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="eyebrow">{html.escape(strings["eyebrow"])}</div>
      <h1>{escaped_title}</h1>
      <p class="meta">{html.escape(strings["meta"])}</p>
      <div class="stats">
        <div class="stat">{html.escape(strings["slides"])}: {len(entries)}</div>
        <div class="stat">{html.escape(strings["keyboard"])}</div>
      </div>
      <div class="nav">
        {"".join(nav_items)}
      </div>
    </aside>
    <main class="main">
      <div class="toolbar">
        <div>
          <div class="toolbar-title" id="slideToolbarTitle">{first_title}</div>
          <div class="toolbar-note">{html.escape(strings["scope"])}</div>
        </div>
        <div class="nav-buttons">
          <button class="nav-button" id="prevBtn">{html.escape(strings["prev"])}</button>
          <button class="nav-button" id="nextBtn">{html.escape(strings["next"])}</button>
        </div>
      </div>
      <section class="summary-card">
        <div class="summary-label">{html.escape(strings["takeaway"])}</div>
        <h2 class="summary-title" id="summaryTitle">{first_title}</h2>
        <p class="summary-takeaway" id="summaryTakeaway"></p>
      </section>
      <div class="viewer-shell">
        <iframe id="viewer" title="Draft slide preview" src="{first_src}"></iframe>
      </div>
    </main>
    <aside class="inspector">
      <section class="panel">
        <h3 class="panel-title">{html.escape(strings["notes"])}</h3>
        <div class="panel-text" id="notesScript"></div>
        <div class="chips" id="notesMeta"></div>
      </section>
      <section class="panel">
        <h3 class="panel-title">{html.escape(strings["assets"])}</h3>
        <div class="asset-list" id="assetList"></div>
      </section>
      <section class="panel">
        <h3 class="panel-title">{html.escape(strings["comments"])}</h3>
        <div class="panel-text">{html.escape(strings["comment_hint"])}</div>
        <textarea id="commentBox" placeholder="{html.escape(strings["comment_placeholder"])}"></textarea>
        <div class="comment-actions">
          <button class="small-button" id="saveCommentBtn">{html.escape(strings["save"])}</button>
          <button class="small-button" id="copyCommentBtn">{html.escape(strings["copy"])}</button>
          <button class="small-button" id="applyCommentsBtn">{html.escape(strings["apply"])}</button>
        </div>
        <div class="save-state" id="saveState">{html.escape(strings["saved"])}</div>
      </section>
    </aside>
  </div>
  <script>
    const entries = {entries_json};
    const strings = {strings_json};
    const projectKey = {json.dumps(project_key)};
    const previewSource = {json.dumps(preview_source)};
    const storageKey = `ppt-master-preview-comments::${{projectKey}}`;
    const viewer = document.getElementById('viewer');
    const toolbarTitle = document.getElementById('slideToolbarTitle');
    const summaryTitle = document.getElementById('summaryTitle');
    const summaryTakeaway = document.getElementById('summaryTakeaway');
    const notesScript = document.getElementById('notesScript');
    const notesMeta = document.getElementById('notesMeta');
    const assetList = document.getElementById('assetList');
    const commentBox = document.getElementById('commentBox');
    const saveState = document.getElementById('saveState');
    const applyCommentsBtn = document.getElementById('applyCommentsBtn');
    const links = Array.from(document.querySelectorAll('.slide-link'));
    let current = 0;

    function loadComments() {{
      try {{
        return JSON.parse(localStorage.getItem(storageKey) || '{{}}');
      }} catch (_error) {{
        return {{}};
      }}
    }}

    let comments = loadComments();

    function setSaveState(text) {{
      saveState.textContent = text;
    }}

    function escapeHtml(value) {{
      return value.replace(/[&<>\"']/g, (char) => {{
        const map = {{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }};
        return map[char];
      }});
    }}

    function renderNotes(entry) {{
      notesScript.textContent = entry.notes_script || strings.no_notes;
      const chips = [];
      if (entry.notes_duration) {{
        chips.push(`<span class="chip">${{escapeHtml(strings.duration)}}: ${{escapeHtml(entry.notes_duration)}}</span>`);
      }}
      (entry.notes_key_points || []).forEach((point) => {{
        chips.push(`<span class="chip">${{escapeHtml(point)}}</span>`);
      }});
      notesMeta.innerHTML = chips.join('') || `<span class="chip">${{escapeHtml(strings.no_notes)}}</span>`;
    }}

    function renderAssets(entry) {{
      if (!entry.assets || !entry.assets.length) {{
        assetList.innerHTML = `<div class="panel-text">${{escapeHtml(strings.no_assets)}}</div>`;
        return;
      }}
      assetList.innerHTML = entry.assets.map((asset) => `
        <div class="asset-card">
          <div class="asset-name">${{escapeHtml(asset.filename || '')}}</div>
          <div class="asset-meta">${{escapeHtml(strings.asset_status)}}: ${{escapeHtml(asset.status || '-')}}</div>
          <div class="asset-meta">${{escapeHtml(strings.asset_type)}}: ${{escapeHtml(asset.type || '-')}}</div>
          <div class="asset-meta">${{escapeHtml(asset.purpose || '-')}}</div>
          <div class="asset-meta">${{escapeHtml(strings.asset_path)}}: ${{escapeHtml(asset.source_path || '-')}}</div>
        </div>
      `).join('');
    }}

    function updateCommentDots() {{
      document.querySelectorAll('[data-comment-dot]').forEach((dot) => {{
        const key = dot.getAttribute('data-comment-dot');
        dot.classList.toggle('has-comment', Boolean((comments[key] || '').trim()));
      }});
    }}

    function saveComments() {{
      localStorage.setItem(storageKey, JSON.stringify(comments));
      updateCommentDots();
      setSaveState(strings.saved);
    }}

    function currentCommentMarkdown() {{
      const entry = entries[current];
      const body = (comments[entry.key] || '').trim();
      return `## ${{entry.number}} ${{entry.title}}\n\n- takeaway: ${{entry.takeaway || '-'}}\n- comment:\n${{body || '-'}}\n`;
    }}

    async function applyAllComments() {{
      const dirtyComments = Object.fromEntries(
        Object.entries(comments).filter(([, value]) => (value || '').trim())
      );
      if (!Object.keys(dirtyComments).length) {{
        setSaveState(strings.no_comments);
        return;
      }}

      applyCommentsBtn.disabled = true;
      setSaveState(strings.updating);
      try {{
        const response = await fetch('/__ppt_master/update_main_content', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            comments: dirtyComments,
            source: previewSource === 'svg_final' ? 'final' : 'output',
            title: document.title,
          }}),
        }});
        const payload = await response.json().catch(() => ({{ status: 'error' }}));
        if (!response.ok || payload.status !== 'ok') {{
          const message = payload.error || strings.update_failed;
          throw new Error(message);
        }}
        comments = {{}};
        localStorage.removeItem(storageKey);
        updateCommentDots();
        setSaveState(strings.updated);
        const selectedKey = entries[current] ? entries[current].key : '';
        const target = `${{window.location.pathname}}?t=${{Date.now()}}${{selectedKey ? `#slide=${{selectedKey}}` : ''}}`;
        window.location.replace(target);
      }} catch (error) {{
        const message = error && error.message ? error.message : strings.update_failed;
        setSaveState(message);
      }} finally {{
        applyCommentsBtn.disabled = false;
      }}
    }}

    function initialIndexFromHash() {{
      const match = window.location.hash.match(/slide=(\\d+)/);
      if (!match) return 0;
      const key = match[1].padStart(2, '0');
      const found = entries.findIndex((entry) => entry.key === key);
      return found >= 0 ? found : 0;
    }}

    function isEditingElement(element) {{
      if (!element) return false;
      const tagName = (element.tagName || '').toLowerCase();
      return (
        element.isContentEditable ||
        tagName === 'textarea' ||
        tagName === 'input' ||
        tagName === 'select'
      );
    }}

    function selectSlide(index) {{
      if (!entries.length) return;
      current = (index + entries.length) % entries.length;
      links.forEach((link, idx) => {{
        link.classList.toggle('active', idx === current);
      }});
      const entry = entries[current];
      viewer.src = entry.href;
      toolbarTitle.textContent = entry.title;
      summaryTitle.textContent = entry.title;
      summaryTakeaway.textContent = entry.takeaway || strings.no_takeaway;
      renderNotes(entry);
      renderAssets(entry);
      commentBox.value = comments[entry.key] || '';
      if (window.location.hash !== `#slide=${{entry.key}}`) {{
        history.replaceState(null, '', `#slide=${{entry.key}}`);
      }}
    }}

    links.forEach((link, index) => {{
      link.addEventListener('click', () => selectSlide(index));
    }});

    commentBox.addEventListener('input', () => {{
      const entry = entries[current];
      comments[entry.key] = commentBox.value;
      saveComments();
    }});

    document.getElementById('saveCommentBtn').addEventListener('click', saveComments);
    document.getElementById('copyCommentBtn').addEventListener('click', async () => {{
      await navigator.clipboard.writeText(currentCommentMarkdown());
      setSaveState(strings.saved);
    }});
    applyCommentsBtn.addEventListener('click', applyAllComments);
    document.getElementById('prevBtn').addEventListener('click', () => selectSlide(current - 1));
    document.getElementById('nextBtn').addEventListener('click', () => selectSlide(current + 1));
    window.addEventListener('keydown', (event) => {{
      if (isEditingElement(document.activeElement)) return;
      if (event.key === 'ArrowLeft') selectSlide(current - 1);
      if (event.key === 'ArrowRight') selectSlide(current + 1);
    }});

    updateCommentDots();
    selectSlide(initialIndexFromHash());
  </script>
</body>
</html>
"""


def render_preview(
    project_path: Path,
    source: str = "output",
    output_path: Path | None = None,
    title: str | None = None,
) -> dict[str, object]:
    project_path = project_path.expanduser().resolve()
    if not project_path.exists():
        raise FileNotFoundError(f"Project path does not exist: {project_path}")

    source_dir_name = "svg_output" if source == "output" else "svg_final"
    source_dir = project_path / source_dir_name
    if not source_dir.exists():
        raise FileNotFoundError(f"SVG source directory does not exist: {source_dir}")

    output_path = output_path.expanduser().resolve() if output_path else (project_path / "preview" / "index.html")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    entries, project_name, language = build_entries(project_path, output_path, source_dir_name)
    strings = STRINGS[language]
    resolved_title = title or (f"{project_name} 审稿预览" if language == "zh" else f"{project_name} Draft Review")
    output_path.write_text(
        build_html(resolved_title, entries, strings, project_path.name, source_dir_name),
        encoding="utf-8",
    )

    return {
        "status": "ok",
        "project_path": str(project_path),
        "source": source_dir_name,
        "output_html": str(output_path),
        "slides": len(entries),
    }


def main() -> int:
    args = parse_args()
    project_path = Path(args.project_path).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve() if args.output else None
    payload = render_preview(project_path, source=args.source, output_path=output_path, title=args.title)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Saved: {payload['output_html']}")
        print(f"Slides: {payload['slides']}")
        print(f"Source: {Path(payload['project_path']) / payload['source']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
