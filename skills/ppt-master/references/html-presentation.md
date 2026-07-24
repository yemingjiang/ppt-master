# Single-file HTML Presentation

Use this reference only after the review skeleton is confirmed and the selected final target is **Single-file HTML Presentation**. This is a final offline deliverable, not the review draft.

## Source contract

Author all final HTML sources under `<project_path>/html_output/`:

```text
html_output/
├── presentation.json
├── presentation.css
└── slides/
    ├── 01_cover.html
    └── 02_overview.html
```

Create `html_output/presentation.json` with `schema_version: 1`, `title`, `lang`, `aspect_ratio`, a named `theme` with color `tokens`, and ordered `slides`. Each slide needs a unique `id`, audience-facing `title`, and project-local `file`. `notes_key` is optional and defaults to the slide ID. Use the default `executive-red` theme unless the confirmed design spec requires another named theme and its complete tokens.

The confirmed theme is fixed at build time. A runtime theme switcher or chooser is forbidden.

`prepare_single_html.py` records generated-source lineage in `html_output/.ppt-master-state.json`. Keep this generated state file with `html_output/`; do not hand-edit it. It tracks source SVG hashes, the last managed fragment hash, supporting inputs, media-managed fragment revisions, and the last packaged export.

Source freshness has four states:

- `untracked`: no lineage exists yet, normally before the first scaffold or during a legacy-project migration;
- `current`: tracked sources are unchanged; deliberately customized fragments are allowed;
- `stale`: an SVG or tracked input changed while the corresponding fragment still matches the last managed version; and
- `conflict`: an SVG changed after its fragment was also customized, so automatic refresh would destroy deliberate work.

The export is independently `missing`, `current`, or `stale` by comparing the planned packaged document with the existing output. `build_single_html.py --check --json` reports both `source_state` and `export_state`. A source conflict must be resolved explicitly; never hide it by rebuilding the export.

Put exactly one top-level slide root in every fragment:

```html
<section class="pm-slide" data-slide-id="01">...</section>
```

Match `data-slide-id` to the manifest ID. Do not add a document wrapper, a second root, a script, or stray top-level content. Put shared rules in `presentation.css`; keep fragment-specific layout inside its slide root.

## Authoring rules

- Keep final slide copy audience-facing. Put presenter directions, source trails, and production comments in notes, never in visible slide chrome unless explicitly requested.
- Read the confirmed `design_spec.md`, `main_content.md`, `style_sheet.md`, `asset_manifest.md`, and `notes/total.md` before authoring. Reuse confirmed project-local assets; do not invent source claims or visible provenance footers.
- The current main agent MUST author final slide fragments sequentially, one slide at a time, in one continuous pass. Do not delegate final slide authoring or create grouped slide batches.
- `prepare_single_html.py` may deterministically scaffold all approved SVGs at once. This mechanical initialization is not creative page authoring. It prefixes SVG IDs, rebases local resources, wraps each page in `.pm-slide`, and prepares the manifest/CSS; review and refine the resulting fragments sequentially.
- Use only project-local resources. The builder embeds them for offline delivery; do not use remote URLs, `file:` URLs, or browser-only dependencies.
- For final-HTML media optimization, the dedicated optimizer may replace an SVG `<image>` GIF placement with an ordinary HTML `<video>` overlay inside the `.pm-slide` root. The overlay is positioned as percentages of the full-slide SVG `viewBox`; do not use `<foreignObject><video>`, because browser compositor behavior can move or clip it at non-default display scaling. Never introduce `foreignObject` into review SVGs, final HTML slide SVGs, or PPTX-oriented sources.
- Use an `iframe` only for intentionally isolated, self-contained embedded content. Keep its source project-local; the builder inlines it and rejects recursive or remote iframe content. Do not use iframe isolation to bypass the slide-root or offline-resource contracts.
- Let the packaged runtime provide PowerPoint-like presentation input, progress, fullscreen, and speaker-notes controls. Do not replace or remove those hooks.
- Treat the presentation input matrix as mandatory:
  - Keyboard and presentation remotes: previous with `PageUp`, `ArrowLeft`, `ArrowUp`, `Backspace`, `P`, `Shift+Space`, or media-previous; next with `PageDown`, `ArrowRight`, `ArrowDown`, `Enter`, `Space`, `N`, or media-next. Use `Home` / `End` for first / last slide, `F` for fullscreen, `S` for speaker notes, and `?` for shortcut help.
  - Mouse: bottom controls, primary click on any non-interactive slide area to advance, wheel or trackpad scrolling in either axis to move backward / forward, and horizontal drag to navigate.
  - Touch: horizontal swipe to navigate.
  - Preserve normal behavior for links, buttons, form controls, media, iframes, editable content, and elements marked `data-pm-interactive`. Modified browser shortcuts such as `Ctrl+F` / `Cmd+F` must remain available.
- Write speaker notes in `notes/total.md` with headings that match each `notes_key` or slide ID. Heading normalization accepts forms such as `# 01 Cover` as key `01`. The final runtime exposes notes through its notes control; do not place the script visibly on slides.
- Use `#slide=<id>` as the canonical shareable URL hash. The runtime also accepts the legacy raw form `#<id>` and normalizes it.

## Large GIF analysis and optimization

Analyze large GIFs after final slide authoring and before packaging:

```bash
python3 ${SKILL_DIR}/scripts/optimize_single_html_media.py <project_path> --json
```

The default target is a 1920×1080 projector/display. The analyzer converts each SVG placement into real display pixels, accounts for `viewBox` and `preserveAspectRatio`, adds presentation headroom, and recommends a source-aspect-preserving MP4 size. It analyzes GIFs of at least 8 MiB by default; pass `--min-bytes 0` to include every GIF.

Only when the user requests or approves media optimization, apply the recommendation:

```bash
python3 ${SKILL_DIR}/scripts/optimize_single_html_media.py <project_path> --apply --json
```

`--apply` requires `ffmpeg`. It writes H.264 MP4 derivatives under `html_output/media_optimized/`, keeps original GIFs and source SVGs unchanged, removes the matching GIF placement from the final slide SVG, and adds a muted, looping, inline autoplay HTML video overlay to the slide root. The overlay keeps its original SVG layout box as data attributes and uses percentage coordinates relative to the full-slide `viewBox`, so browser resolution, zoom, and display scaling do not change its anchor. Derivative names include a source-content fingerprint, so unchanged media is reused while changed GIF content is retranscoded. A derivative that is not smaller than its GIF is not substituted.

Use `--target 4k` only when the user explicitly asks for a 4K presentation:

```bash
python3 ${SKILL_DIR}/scripts/optimize_single_html_media.py <project_path> --target 4k --json
python3 ${SKILL_DIR}/scripts/optimize_single_html_media.py <project_path> --target 4k --apply --json
```

Do not infer a 4K delivery target from a 4K or oversized source GIF. If `prepare_single_html.py --force` later refreshes the slide fragments, rerun the optimizer because the refresh deliberately restores the SVG-authored GIF placements.

## Optional terminology policy

Add `<project_path>/terminology.json` when the deck has project-specific forbidden terms or required replacements:

```json
{
  "forbidden": {
    "XGU": "XGUI",
    "Flow": "工作流"
  },
  "case_sensitive": false
}
```

By default, the checker scans the handoff Markdown, notes, SVG sources, and final HTML fragments. An optional `include` array may override those glob patterns. It reports every file, line, column, found term, and replacement; it never rewrites copy automatically. `finalize_single_html.py` stops before writing when violations exist.

## Package and validate

Use the one-command finalizer for the normal path. Always inspect the dry-run first:

```bash
python3 ${SKILL_DIR}/scripts/finalize_single_html.py <project_path> --dry-run --json
python3 ${SKILL_DIR}/scripts/finalize_single_html.py <project_path> --json
```

The finalizer checks optional terminology rules, safely refreshes changed managed fragments, analyzes large GIFs, preflights, packages, and runs real-browser QA. Add `--apply-media` only after the user requests or approves GIF-to-MP4 optimization. It defaults to `qa/final-html/` for screenshots and contact sheets. For a legacy untracked tree or an intentional full reset, first inspect the dry-run, then add `--force-scaffold`; this may replace customized slide fragments.

Use the individual commands only for recovery, debugging, or a deliberately staged run:

```bash
python3 ${SKILL_DIR}/scripts/check_terminology.py <project_path> --json
python3 ${SKILL_DIR}/scripts/prepare_single_html.py <project_path> --dry-run --json
# First scaffold:
python3 ${SKILL_DIR}/scripts/prepare_single_html.py <project_path>
# Later safe refresh:
python3 ${SKILL_DIR}/scripts/prepare_single_html.py <project_path> --refresh-changed
# Intentional full generated-source reset only:
python3 ${SKILL_DIR}/scripts/prepare_single_html.py <project_path> --force
python3 ${SKILL_DIR}/scripts/optimize_single_html_media.py <project_path> --json
# Only after approval:
python3 ${SKILL_DIR}/scripts/optimize_single_html_media.py <project_path> --apply --json
python3 ${SKILL_DIR}/scripts/build_single_html.py <project_path> --check --json
python3 ${SKILL_DIR}/scripts/build_single_html.py <project_path>
python3 ${SKILL_DIR}/scripts/qa_single_html.py <project_path> --screenshots <qa_dir> --json
```

`--refresh-changed` updates only a changed slide whose current fragment still matches the last managed revision. It preserves unchanged customized fragments and media-derived revisions. If both the SVG and fragment changed, it reports a conflict and writes neither side. The media optimizer updates the managed fragment hash after a successful rewrite, so the next safe refresh recognizes the MP4-overlay fragment rather than treating it as unknown customization.

Deliver `<project_path>/exports/<project_name>.single.html`. `preview/index.html` is not the final HTML; it remains the review-only skeleton preview.

The builder reports unique asset count, reference count, source bytes, embedded payload bytes, largest assets, and advisory size warnings. A final file over 50 MB, an individual asset over 10 MB, or a GIF over 8 MB should trigger review. The builder itself never transcodes source media; use the dedicated optimizer after user approval.

Before delivery:

- it opens offline with no network requests or broken local resources;
- every slide navigates by controls, the complete keyboard / presentation-remote matrix, click on visible slide content, mouse wheel / trackpad, mouse drag, touch swipe, and URL hash;
- one physical-looking advance action causes exactly one slide change, including drag/swipe gestures that may synthesize a click;
- fullscreen, progress, and speaker-notes controls work;
- every optimized autoplay video visibly renders, advances in time, loops, stays muted and inline, pauses when its slide becomes inactive, and resumes when that slide becomes active again;
- no large embedded GIF data URI remains after an approved optimization pass;
- slide sequence, notes, titles, audience-facing copy, theme, fonts, and assets match the confirmed design;
- iframe content, if any, is visible and isolated without remote dependencies; and
- the artifact exists at `exports/<project_name>.single.html` and is the one selected final target.

Source/reference images must be inventoried before use under the main skill's image rule. Generated slide screenshots and contact sheets are QA evidence, not source-image analysis: open and inspect them visually, checking overlap, clipping, wrapping, alignment, empty regions, incorrect asset mapping, and slide-to-slide consistency.
