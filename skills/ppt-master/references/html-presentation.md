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
- For final-HTML media optimization, the dedicated optimizer may replace an SVG `<image>` GIF placement with a same-position `<foreignObject><video>` inside the final slide fragment. This exception is limited to `html_output/slides/`; never introduce `foreignObject` into review SVGs or PPTX-oriented sources.
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

`--apply` requires `ffmpeg`. It writes H.264 MP4 derivatives under `html_output/media_optimized/`, keeps original GIFs and source SVGs unchanged, and rewrites matching final HTML placements as muted, looping, inline autoplay videos. Derivative names include a source-content fingerprint, so unchanged media is reused while changed GIF content is retranscoded. A derivative that is not smaller than its GIF is not substituted.

Use `--target 4k` only when the user explicitly asks for a 4K presentation:

```bash
python3 ${SKILL_DIR}/scripts/optimize_single_html_media.py <project_path> --target 4k --json
python3 ${SKILL_DIR}/scripts/optimize_single_html_media.py <project_path> --target 4k --apply --json
```

Do not infer a 4K delivery target from a 4K or oversized source GIF. If `prepare_single_html.py --force` later refreshes the slide fragments, rerun the optimizer because the refresh deliberately restores the SVG-authored GIF placements.

## Package and validate

Use the deterministic initializer for a new final-HTML source tree, or for an intentional refresh:

```bash
python3 ${SKILL_DIR}/scripts/prepare_single_html.py <project_path> --dry-run --json
python3 ${SKILL_DIR}/scripts/prepare_single_html.py <project_path>
# Use --force only when deliberately refreshing generated files.
python3 ${SKILL_DIR}/scripts/optimize_single_html_media.py <project_path> --json
```

Preflight, package, and run real-browser QA:

```bash
python3 ${SKILL_DIR}/scripts/build_single_html.py <project_path> --check --json
python3 ${SKILL_DIR}/scripts/build_single_html.py <project_path>
python3 ${SKILL_DIR}/scripts/qa_single_html.py <project_path> --screenshots <qa_dir> --json
```

Deliver `<project_path>/exports/<project_name>.single.html`. `preview/index.html` is not the final HTML; it remains the review-only skeleton preview.

The builder reports unique asset count, reference count, source bytes, embedded payload bytes, largest assets, and advisory size warnings. A final file over 50 MB, an individual asset over 10 MB, or a GIF over 8 MB should trigger review. The builder itself never transcodes source media; use the dedicated optimizer after user approval.

Before delivery:

- it opens offline with no network requests or broken local resources;
- every slide navigates by controls, the complete keyboard / presentation-remote matrix, click on visible slide content, mouse wheel / trackpad, mouse drag, touch swipe, and URL hash;
- one physical-looking advance action causes exactly one slide change, including drag/swipe gestures that may synthesize a click;
- fullscreen, progress, and speaker-notes controls work;
- optimized autoplay videos visibly render, advance in time, loop, stay muted, and pause when their slide becomes inactive;
- slide sequence, notes, titles, audience-facing copy, theme, fonts, and assets match the confirmed design;
- iframe content, if any, is visible and isolated without remote dependencies; and
- the artifact exists at `exports/<project_name>.single.html` and is the one selected final target.

Source/reference images must be inventoried before use under the main skill's image rule. Generated slide screenshots and contact sheets are QA evidence, not source-image analysis: open and inspect them visually, checking overlap, clipping, wrapping, alignment, empty regions, incorrect asset mapping, and slide-to-slide consistency.
