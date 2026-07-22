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

Create `html_output/presentation.json` with `schema_version: 1`, `title`, `lang`, `aspect_ratio`, a named `theme` with color `tokens`, and ordered `slides`. Each slide needs unique `id`, audience-facing `title`, project-local `file`, and `notes_key`. Use the default `executive-red` theme unless the confirmed design spec requires another named theme and its complete tokens.

Put exactly one top-level slide root in every fragment:

```html
<section class="pm-slide" data-slide-id="01">...</section>
```

Match `data-slide-id` to the manifest ID. Do not add a document wrapper, a second root, a script, or stray top-level content. Put shared rules in `presentation.css`; keep fragment-specific layout inside its slide root.

## Authoring rules

- Keep final slide copy audience-facing. Put presenter directions, source trails, and production comments in notes, never in visible slide chrome unless explicitly requested.
- Read the confirmed `design_spec.md`, `main_content.md`, `style_sheet.md`, `asset_manifest.md`, and `notes/total.md` before authoring. Reuse confirmed project-local assets; do not invent source claims or visible provenance footers.
- The current main agent MUST author final slide fragments sequentially, one slide at a time, in one continuous pass. Do not delegate final slide authoring or create grouped slide batches.
- Use only project-local resources. The builder embeds them for offline delivery; do not use remote URLs, `file:` URLs, or browser-only dependencies.
- Use an `iframe` only for intentionally isolated, self-contained embedded content. Keep its source project-local; the builder inlines it and rejects recursive or remote iframe content. Do not use iframe isolation to bypass the slide-root or offline-resource contracts.
- Let the packaged runtime provide keyboard, click/touch navigation, progress, fullscreen, and speaker-notes controls. Do not replace or remove those hooks.
- Write speaker notes in `notes/total.md` with headings that match each `notes_key`. The final runtime exposes them through its notes control; do not place the script visibly on slides.

## Package and validate

Run the final builder only after all sources are complete:

```bash
python3 ${SKILL_DIR}/scripts/build_single_html.py <project_path>
```

Deliver `<project_path>/exports/<project_name>.single.html`. `preview/index.html` is not the final HTML; it remains the review-only skeleton preview.

Before delivery, open the packaged file without a server and verify:

- it opens offline with no network requests or broken local resources;
- every slide navigates by controls, keyboard, touch/click, and URL hash;
- fullscreen, progress, and speaker-notes controls work;
- slide sequence, notes, titles, audience-facing copy, theme, fonts, and assets match the confirmed design;
- iframe content, if any, is visible and isolated without remote dependencies; and
- the artifact exists at `exports/<project_name>.single.html` and is the one selected final target.
