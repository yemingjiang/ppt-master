# Single-file HTML Presentation Design

## Context

`ppt-master` currently produces a review skeleton and can continue to a native editable PowerPoint. Its `preview/index.html` is a review surface that references project SVG files; it is not a portable final presentation.

Add a final HTML delivery path modeled on the provided `figma-planner.single.html`: one self-contained file that opens through `file://`, needs no server or network, and supports native web layouts, video, interactive iframe content, keyboard navigation, fullscreen presentation, and speaker notes.

## Goals

- Let each run select exactly one final target: review skeleton only, single-file HTML, native editable PPTX, or explicit legacy PPTX export.
- Preserve the existing common content strategy, skeleton generation, and human review loop.
- Render final HTML as semantic HTML/CSS rather than as SVG screenshots.
- Package all required local resources recursively into one `.single.html` file.
- Keep the HTML and PPTX final renderers independent. They must preserve the approved content and narrative, but they do not need pixel-identical layouts or animation.
- Make the attachment-inspired red/white/charcoal executive-report theme the default for HTML while keeping project-level color selection in the existing Eight Confirmations.
- Fail explicitly when an output would not work offline.

## Non-goals

- Do not generate HTML and PPTX together by default.
- Do not turn `preview/index.html` into the final HTML artifact.
- Do not require a local web server, CDN, online font, or remote media host.
- Do not add a runtime theme switcher to the final presentation.
- Do not promise browser and PowerPoint layouts will be visually identical.
- Do not replace the native editable PowerPoint rebuild path.

## Delivery Modes

Use these delivery modes throughout `SKILL.md`, Strategist, Executor, and the design-spec template:

1. **Review Skeleton** — stop after the review package.
2. **Single-file HTML Presentation** — after review approval, build a final offline HTML presentation.
3. **Native Editable Handoff** — after review approval, build a native editable PPTX.
4. **Legacy Direct Export** — explicit converter-oriented PPTX compatibility path only.

If the user requests a final artifact but has not stated HTML or PPTX, ask for one target before final production. Never infer simultaneous output.

## Workflow

The common pipeline remains:

`Source → Project → Template choice → Strategist Eight Confirmations → Optional images → SVG skeleton → Review package → Human review`

After the human locks the skeleton, route to exactly one final branch:

- **HTML branch**: generate semantic HTML sources in `html_output/`, package them, validate offline completeness, and deliver `exports/<project_name>.single.html`.
- **PPTX branch**: follow `references/native-editable.md` and deliver the native editable deck.
- **Legacy branch**: retain the existing three-step compatibility export.

The review package remains required for both final targets. `preview/index.html` continues to be the review and comment surface, never the final presentation.

## HTML Source Contract

Create these project files only when the selected final target is HTML:

```text
html_output/
├── presentation.json
├── presentation.css
└── slides/
    ├── 01_cover.html
    ├── 02_overview.html
    └── ...
```

### `presentation.json`

Use a small structured manifest so the packer does not infer page order or presentation settings from filenames:

```json
{
  "schema_version": 1,
  "title": "Presentation title",
  "lang": "zh-CN",
  "aspect_ratio": "16 / 9",
  "theme": {
    "name": "executive-red",
    "tokens": {
      "background": "#FFFFFF",
      "surface": "#F2F2F2",
      "primary": "#B50F0A",
      "on_primary": "#FFFFFF",
      "text": "#222222",
      "muted": "#666666",
      "line": "#D7D7D7"
    }
  },
  "slides": [
    {
      "id": "01",
      "title": "Cover",
      "file": "slides/01_cover.html",
      "notes_key": "01"
    }
  ]
}
```

Rules:

- `schema_version` must be `1`.
- Slide IDs must be unique and ordered by the `slides` array.
- Every slide file and notes key must resolve successfully.
- `aspect_ratio` comes from the confirmed canvas.
- Theme tokens come from the confirmed color scheme; `executive-red` is only the default.
- All paths must stay inside the project directory.

### Slide fragments

Each slide file contains exactly one root section:

```html
<section class="pm-slide slide-01" data-slide-id="01" aria-label="Cover">
  <!-- semantic page content -->
</section>
```

Rules:

- Use semantic HTML and project CSS, not an SVG snapshot of the page.
- Keep page-specific selectors scoped beneath the page root class.
- Do not include `<html>`, `<head>`, or `<body>` wrappers.
- Do not include top-level page scripts. Put complex interactive content in a separate local HTML document and embed it with an iframe.
- Use audience-facing visible copy. Presenter guidance stays in `notes/total.md`.
- Generate pages sequentially in the main-agent context to preserve cross-page consistency.

### Project CSS

`presentation.css` contains project-specific layout and component styling. The final builder injects confirmed theme tokens as CSS custom properties and combines the project CSS with the bundled runtime shell.

Prefer system font stacks for predictable offline use. If the user supplies local font files, reference them through `@font-face`; the packer embeds those files.

## Default HTML Theme

Name the default theme `executive-red`. Its visual language follows the supplied management-report screenshot:

- strong red title bars and vertical section labels;
- white page backgrounds and light-gray information panels;
- large charcoal headings and body text;
- red KPI figures and emphasis labels;
- restrained borders, shadows, and spacing suitable for dense executive reporting.

Default tokens:

| Role | Value |
| --- | --- |
| Background | `#FFFFFF` |
| Surface | `#F2F2F2` |
| Primary red | `#B50F0A` |
| Text on red | `#FFFFFF` |
| Main text | `#222222` |
| Muted text | `#666666` |
| Border/divider | `#D7D7D7` |

The Strategist must present the colors during the existing Eight Confirmations. User changes replace these tokens before page generation. The final HTML contains no theme selector.

## Offline Packaging

Add `scripts/build_single_html.py` as the deterministic packaging entry point:

```bash
python3 scripts/build_single_html.py <project_path>
python3 scripts/build_single_html.py <project_path> --output <file>
python3 scripts/build_single_html.py <project_path> --json
```

Default output: `<project_path>/exports/<project_name>.single.html`.

The builder must:

1. Parse and validate `presentation.json`.
2. Read slide fragments in declared order.
3. Load project CSS, the bundled presentation shell, and runtime JavaScript.
4. Parse `notes/total.md` and attach notes by `notes_key`.
5. Resolve and embed local resources with correct MIME types.
6. Recursively package local iframe HTML and its resources.
7. validate the assembled document for offline completeness.
8. Write the target atomically only after successful validation.

### Resources to embed

- `<img src>` and `srcset` candidates
- `<video src>` and `poster`
- `<audio src>`
- `<source src>`
- local iframe documents
- local script and stylesheet dependencies inside iframe documents
- CSS `url(...)` values, including local fonts and background images
- existing `data:` URIs, preserved without re-encoding

Local paths must resolve inside the project directory. Reject path traversal and filesystem references outside the project.

For a local iframe, canonicalize its path, record the active recursion stack, package its HTML and dependencies, then replace its `src` with a base64 `data:text/html` URI. Reject recursive cycles with a chain that identifies every file involved.

### Network rules

Reject runtime dependencies using `http:`, `https:`, protocol-relative URLs, or `file:` URLs in media, iframe, script, stylesheet, font, or CSS resource positions.

Allow ordinary `<a href>` external references because they are optional navigation, not runtime dependencies. The presentation must remain complete and usable when those links cannot open.

### Output reporting

Human output reports the saved path, slide count, embedded resource count, output bytes, and warnings. `--json` writes only a machine-readable object to stdout. Errors go to stderr, return nonzero, and identify the source file and unresolved reference.

Large files are valid. Emit a warning when the result exceeds 100 MB, but do not fail solely because embedded video makes the presentation large.

## Presentation Runtime

Bundle a dependency-free shell and runtime with the skill. The final file must work directly from `file://` in current Chrome, Edge, and Safari.

Required behavior:

- Center the active slide and preserve the confirmed aspect ratio.
- Navigate with Left/Right, Page Up/Page Down, Space, Home, and End.
- Advance by clicking non-interactive empty regions.
- Do not advance when the click originates in a link, button, form control, video, audio, or iframe.
- Support touch swipe navigation.
- Toggle fullscreen with `F` and a visible control.
- Toggle the current slide's notes panel with `N`.
- Display page position and progress.
- Reflect the active slide in the URL hash and restore it on reload.
- Pause media on inactive slides. Respect each media element's `autoplay`, `muted`, and `loop` attributes when a slide becomes active.
- Auto-hide presentation controls after inactivity and reveal them on pointer movement or focus.
- Respect `prefers-reduced-motion`.
- Provide accessible labels and visible keyboard focus states.

Speaker notes are embedded in the final file but hidden until the presenter presses `N`. They are not rendered as audience-facing slide content.

## Error Handling

Fail without writing or replacing the target when any of these occur:

- missing manifest, CSS, slide fragment, note key, or local asset;
- invalid JSON or unsupported schema version;
- duplicate slide ID;
- slide fragment with an invalid root contract;
- path traversal or resource outside the project;
- remote runtime dependency;
- iframe recursion cycle;
- unsupported or indeterminate MIME type for a required resource;
- final validation detects a remaining local or remote runtime reference.

Use a temporary file in the destination directory and replace the final target only after all checks pass.

## Skill and Repository Changes

Update:

- `skills/ppt-master/SKILL.md`
- `skills/ppt-master/templates/design_spec_reference.md`
- `skills/ppt-master/references/strategist.md`
- `skills/ppt-master/references/executor-base.md`
- `skills/ppt-master/scripts/README.md`
- repository `AGENTS.md` and `README.md`

Add:

- `skills/ppt-master/references/html-presentation.md`
- bundled HTML shell, runtime, and default-theme assets under `skills/ppt-master/assets/html-presentation/`
- `skills/ppt-master/scripts/build_single_html.py`
- focused automated tests and small test fixtures for the new builder

Keep detailed HTML authoring and packaging rules in `references/html-presentation.md`; keep only routing, gates, and commands in `SKILL.md` to limit further growth.

## Testing Strategy

Follow test-first development.

### Unit and integration coverage

- Build a minimal two-slide presentation and confirm one HTML file is produced.
- Embed images, video, audio, CSS backgrounds, and a local font with correct MIME data URIs.
- Package a nested local iframe containing local CSS, script, and image resources.
- Reject a missing asset with its source file and reference in the error.
- Reject iframe cycles and show the cycle chain.
- Reject remote scripts, stylesheets, fonts, media, and iframe sources.
- Preserve an ordinary external anchor link.
- Reject a path outside the project.
- Embed notes and verify the notes panel starts hidden.
- Verify generated runtime JavaScript parses successfully with Node.
- Verify the generated HTML contains the required navigation, fullscreen, notes, media-pause, progress, and reduced-motion hooks.
- Verify `--json` stdout is valid JSON without human prose.

### Regression and browser checks

- Run the existing preview, skeleton, placeholder, and SVG converter tests.
- Generate a representative final artifact and open it through `file://` in a browser.
- Smoke-test next/previous navigation, `N` notes toggle, media pause on slide change, an embedded interactive iframe, and absence of network requests.
- Validate the skill directory with the standard skill validator.
- Forward-test the revised skill from a clean agent context using a realistic request for an offline HTML presentation.

## Acceptance Criteria

The change is complete when:

1. A user can explicitly choose HTML or PPTX as the only final target.
2. The existing review loop remains intact.
3. The HTML branch creates semantic page sources and one portable `.single.html` artifact.
4. The artifact presents correctly through `file://` with no server or network.
5. Images, fonts, video, audio, and nested interactive HTML continue to work offline.
6. Keyboard, touch, fullscreen, progress, hash navigation, video lifecycle, and `N` speaker notes behave as specified.
7. The default HTML theme matches the approved red/white/charcoal direction and can be replaced during the Eight Confirmations.
8. Broken offline dependencies fail loudly before the target is written.
9. The native editable PPTX and legacy export paths remain functional and clearly separate.
10. Automated, browser, regression, skill-validation, and clean-context checks pass.
