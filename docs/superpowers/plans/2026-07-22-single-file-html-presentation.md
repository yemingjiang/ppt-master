# Single-file HTML Presentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a selectable, semantic, fully offline single-file HTML presentation delivery path to `ppt-master` without changing the native editable PPTX path.

**Architecture:** Keep the current skeleton and review workflow, then route an HTML-selected project to semantic slide fragments under `html_output/`. A Python packager validates the manifest, embeds local media and recursively packages iframe documents, combines dependency-free browser runtime assets, and atomically writes one `exports/<project_name>.single.html` file.

**Tech Stack:** Python 3.10+, BeautifulSoup 4, standard-library `argparse`/`base64`/`json`/`mimetypes`/`pathlib`, dependency-free HTML/CSS/JavaScript, `unittest`, Node syntax checks, browser `file://` smoke testing.

## Global Constraints

- Each run selects one final target: HTML or PPTX; never default to simultaneous output.
- `preview/index.html` remains a review surface and is never the final HTML artifact.
- Final HTML uses semantic HTML/CSS, not SVG screenshots.
- Final HTML must work from `file://` with no server, CDN, online font, remote script, remote media, or remote iframe dependency.
- Images, audio, video, local fonts, CSS URLs, linked iframe styles/scripts, and nested local iframe HTML must be embedded.
- Ordinary external anchor links may remain, but runtime resource URLs may not.
- HTML theme colors are confirmed before generation; no runtime theme switcher is added.
- Default theme tokens are background `#FFFFFF`, surface `#F2F2F2`, primary `#B50F0A`, on-primary `#FFFFFF`, text `#222222`, muted `#666666`, and line `#D7D7D7`.
- The HTML runtime supports keyboard and touch navigation, fullscreen on `F`, notes on `N`, progress/hash state, media pause, control auto-hide, accessibility, and reduced motion.
- Keep the existing PPTX native editable and legacy export behavior intact.
- New CLI behavior is non-interactive, retry-safe, actionable on errors, and provides clean `--json` output.

---

### Task 1: Baseline skill behavior and core project loader

**Files:**
- Create: `skills/ppt-master/scripts/test_build_single_html.py`
- Create: `skills/ppt-master/scripts/build_single_html.py`

**Interfaces:**
- Consumes: `<project_path>/design_spec.md`, `<project_path>/notes/total.md`, and `<project_path>/html_output/presentation.json`.
- Produces: `PackagingError`, `load_manifest(project_path: Path) -> dict[str, object]`, `validate_slide_fragment(html_text: str, slide_id: str, source_path: Path) -> str`, and `build_single_html(project_path: Path, output_path: Path | None = None) -> dict[str, object]`.

- [ ] **Step 1: Run a clean-context baseline skill scenario**

Ask a fresh agent to use the current `ppt-master` skill for: “Create a final fully offline single-file HTML presentation with embedded video, interactive iframe content, and speaker notes.” Capture whether it routes to a real final HTML mode or mistakes `preview/index.html` for the deliverable.

Expected baseline: the current skill has no `Single-file HTML Presentation` delivery mode or final HTML branch.

- [ ] **Step 2: Write failing loader and slide-contract tests**

Add fixture helpers that create a temporary project with a minimal `design_spec.md`, `notes/total.md`, `html_output/presentation.css`, slide fragments, and this manifest:

```python
manifest = {
    "schema_version": 1,
    "title": "Offline Demo",
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
            "line": "#D7D7D7",
        },
    },
    "slides": [
        {"id": "01", "title": "封面", "file": "slides/01_cover.html", "notes_key": "01"},
        {"id": "02", "title": "概览", "file": "slides/02_overview.html", "notes_key": "02"},
    ],
}
```

Test that `load_manifest()` accepts it, rejects schema versions other than `1`, rejects duplicate IDs, rejects slide paths outside the project, and reports the manifest field responsible. Test that `validate_slide_fragment()` requires exactly one `<section class="pm-slide" data-slide-id="…">` root and rejects scripts in a slide fragment.

- [ ] **Step 3: Run tests to verify RED**

Run:

```bash
python3 -m unittest skills/ppt-master/scripts/test_build_single_html.py -v
```

Expected: import failure because `build_single_html.py` does not exist.

- [ ] **Step 4: Implement the minimal validated loader**

Create `build_single_html.py` with:

```python
class PackagingError(ValueError):
    pass


def load_manifest(project_path: Path) -> dict[str, object]:
    """Load presentation.json and validate schema, slide IDs, and project-local paths."""


def validate_slide_fragment(
    html_text: str,
    slide_id: str,
    source_path: Path,
) -> str:
    """Return the normalized root section or raise PackagingError."""
```

Use BeautifulSoup's `html.parser`, canonical `Path.resolve()`, and `Path.relative_to()` containment checks. Do not write output in this task.

- [ ] **Step 5: Run tests to verify GREEN**

Run the Task 1 unittest command. Expected: all Task 1 tests pass with no warnings.

- [ ] **Step 6: Commit**

```bash
git add skills/ppt-master/scripts/build_single_html.py skills/ppt-master/scripts/test_build_single_html.py
git commit -m "feat: validate offline HTML presentation sources"
```

### Task 2: Recursive offline resource packager

**Files:**
- Modify: `skills/ppt-master/scripts/build_single_html.py`
- Modify: `skills/ppt-master/scripts/test_build_single_html.py`

**Interfaces:**
- Consumes: validated HTML strings and source paths from Task 1.
- Produces: `OfflineResourcePackager(project_root: Path)`, `rewrite_html(html_text: str, source_path: Path, iframe_stack: tuple[Path, ...] = ()) -> str`, `rewrite_css(css_text: str, source_path: Path) -> str`, `to_data_uri(path: Path) -> str`, `embedded_count: int`, and `warnings: list[str]`.

- [ ] **Step 1: Write failing media and CSS embedding tests**

Create local fixture files for PNG bytes, MP4 bytes, MP3 bytes, WOFF2 bytes, a CSS background image, and a poster. Assert that these source forms are replaced with correctly typed `data:` URIs:

```html
<img src="../../images/chart.png">
<video src="../../images/demo.mp4" poster="../../images/poster.png"></video>
<audio src="../../images/narration.mp3"></audio>
<source src="../../images/demo.mp4" type="video/mp4">
```

```css
@font-face { font-family: Demo; src: url("../../images/demo.woff2") format("woff2"); }
.hero { background-image: url("../../images/chart.png"); }
```

Also test preservation of existing `data:` URIs and fragment-only URLs such as `url(#gradient)`.

- [ ] **Step 2: Write failing nested iframe tests**

Create `interactive/root.html` linking a local stylesheet and script and embedding `child.html`, where `child.html` uses a local image. Assert that the top-level iframe becomes `data:text/html;base64,...`, decode it recursively, and verify linked CSS/script/image dependencies are embedded with no remaining local paths.

Add a cycle `a.html → b.html → a.html` and assert `PackagingError` includes both canonical file names in order.

- [ ] **Step 3: Run tests to verify RED**

Run the focused unittest class. Expected: failures because `OfflineResourcePackager` is undefined.

- [ ] **Step 4: Implement resource embedding**

Implement these rules:

```python
RESOURCE_ATTRS = {
    "img": ("src", "srcset"),
    "video": ("src", "poster"),
    "audio": ("src",),
    "source": ("src", "srcset"),
}

REMOTE_SCHEMES = {"http", "https", "file", "blob"}
```

- Resolve local references relative to the containing source file.
- Reject resources outside `project_root`.
- Use `mimetypes.guess_type()` plus explicit mappings for `.woff2`, `.woff`, `.ttf`, `.otf`, `.mp4`, `.webm`, `.mov`, `.mp3`, `.wav`, `.m4a`, `.js`, and `.css`.
- Rewrite inline `style` attributes and `<style>` contents.
- Inline iframe `<link rel="stylesheet">` as `<style>` and iframe `<script src>` as inline `<script>`.
- Recurse into iframe documents with a canonical active stack and replace iframe `src` with base64 HTML.
- Reject remote runtime resources; do not rewrite `<a href>`.

- [ ] **Step 5: Run tests to verify GREEN**

Run the complete `test_build_single_html.py` suite. Expected: loader and recursive embedding tests pass.

- [ ] **Step 6: Commit**

```bash
git add skills/ppt-master/scripts/build_single_html.py skills/ppt-master/scripts/test_build_single_html.py
git commit -m "feat: embed offline HTML presentation resources"
```

### Task 3: Presentation shell, runtime, and default theme

**Files:**
- Create: `skills/ppt-master/assets/html-presentation/shell.html`
- Create: `skills/ppt-master/assets/html-presentation/runtime.css`
- Create: `skills/ppt-master/assets/html-presentation/runtime.js`
- Create: `skills/ppt-master/assets/html-presentation/executive-red.css`
- Modify: `skills/ppt-master/scripts/build_single_html.py`
- Modify: `skills/ppt-master/scripts/test_build_single_html.py`

**Interfaces:**
- Consumes: manifest theme tokens, normalized slide roots, project CSS, and notes parsed by `skeleton_utils.parse_notes_total()`.
- Produces: a complete standalone HTML string from `render_document(manifest: dict, slides: list[str], project_css: str, notes: dict[str, dict]) -> str`.

- [ ] **Step 1: Write failing runtime contract tests**

Assert the rendered document contains stable hooks for:

```text
data-pm-action="previous"
data-pm-action="next"
data-pm-action="fullscreen"
data-pm-action="notes"
id="pmNotesPanel"
id="pmProgress"
prefers-reduced-motion
```

Extract the runtime `<script>` and run `new vm.Script(...)` through Node. Assert the script includes keyboard cases for Arrow keys, Page keys, Space, Home, End, `f`, and `n`; touch/pointer swipe handling; interactive-target guards; hash state; media pausing; and control auto-hide.

- [ ] **Step 2: Run tests to verify RED**

Expected: missing asset/template and runtime-hook failures.

- [ ] **Step 3: Implement the shell and runtime assets**

Use a template with explicit placeholders:

```text
{{LANG}}
{{TITLE}}
{{THEME_TOKENS}}
{{RUNTIME_CSS}}
{{THEME_CSS}}
{{PROJECT_CSS}}
{{SLIDES}}
{{NOTES_JSON}}
{{RUNTIME_JS}}
```

Implement a centered aspect-ratio stage, active-slide visibility, controls, page counter, progress, hidden notes drawer, focus styles, and reduced-motion CSS. Implement dependency-free runtime functions `show(index)`, `go(delta)`, `toggleFullscreen()`, `toggleNotes()`, `pauseInactiveMedia()`, `isInteractiveTarget(target)`, and hash restoration.

- [ ] **Step 4: Implement document rendering**

Load the four bundled assets relative to `SKILL_DIR`. Escape title/lang values, serialize notes with the existing safe `</` escape pattern, inject CSS variables from manifest tokens, and concatenate validated slides. For custom theme names, continue to use variable-driven base component CSS; manifest tokens remain authoritative.

- [ ] **Step 5: Run tests to verify GREEN**

Run the HTML builder suite and Node syntax assertion. Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add skills/ppt-master/assets/html-presentation skills/ppt-master/scripts/build_single_html.py skills/ppt-master/scripts/test_build_single_html.py
git commit -m "feat: add offline HTML presentation runtime"
```

### Task 4: Atomic CLI, offline validation, and integration output

**Files:**
- Modify: `skills/ppt-master/scripts/build_single_html.py`
- Modify: `skills/ppt-master/scripts/test_build_single_html.py`

**Interfaces:**
- Consumes: `build_single_html(project_path, output_path)` core API.
- Produces: CLI flags `project_path`, `--output`, and `--json`; JSON fields `status`, `project_path`, `output_html`, `output_file_url`, `slides`, `embedded_assets`, `bytes`, and `warnings`.

- [ ] **Step 1: Write failing end-to-end and failure-safety tests**

Build a two-slide fixture with media, notes, project CSS, and a nested iframe. Assert:

- the default output is `exports/<project_name>.single.html`;
- the file contains no unresolved media, iframe, stylesheet, script, font, CSS URL, absolute local path, or runtime remote dependency;
- a normal `https://` anchor remains;
- notes are embedded and hidden by default;
- rerunning produces the same target without duplicate outputs;
- an existing target remains byte-identical if a later build fails;
- results larger than 100 MB add a warning rather than failing.

Invoke the CLI with `--json`; assert stdout parses as one JSON object and stderr is empty on success. Invoke an invalid project; assert nonzero status, empty stdout in human mode, and actionable stderr naming the missing file.

- [ ] **Step 2: Run tests to verify RED**

Expected: output/CLI/atomic-write assertions fail because the orchestration is incomplete.

- [ ] **Step 3: Implement orchestration and validation**

Implement:

```python
def build_single_html(
    project_path: Path,
    output_path: Path | None = None,
) -> dict[str, object]:
    ...


def parse_args() -> argparse.Namespace:
    ...


def main() -> int:
    ...
```

The CLI help must include three copyable examples. In `--json` mode, print only the JSON payload. Write to a `NamedTemporaryFile` in the destination directory, flush and close it, then `os.replace()` the target after validation. Delete the temporary file on failure.

- [ ] **Step 4: Run tests to verify GREEN**

Run the builder suite. Expected: all unit, integration, CLI, and atomic-write tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/ppt-master/scripts/build_single_html.py skills/ppt-master/scripts/test_build_single_html.py
git commit -m "feat: add single-file HTML presentation CLI"
```

### Task 5: Skill routing, HTML authoring reference, and repository docs

**Files:**
- Create: `skills/ppt-master/references/html-presentation.md`
- Modify: `skills/ppt-master/SKILL.md`
- Modify: `skills/ppt-master/templates/design_spec_reference.md`
- Modify: `skills/ppt-master/references/strategist.md`
- Modify: `skills/ppt-master/references/executor-base.md`
- Modify: `skills/ppt-master/scripts/README.md`
- Modify: `AGENTS.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: the implemented HTML source contract and CLI.
- Produces: a future agent can classify HTML as a final mode, author `html_output/`, run the builder, validate the artifact, and avoid generating PPTX in the same run.

- [ ] **Step 1: Add skill conformance assertions**

Extend `test_build_single_html.py` to read the skill/reference/template files and assert they contain:

```text
Single-file HTML Presentation
references/html-presentation.md
scripts/build_single_html.py
html_output/presentation.json
exports/<project_name>.single.html
```

Assert the main skill explicitly distinguishes `preview/index.html` from the final HTML and says only one final target is selected.

- [ ] **Step 2: Run tests to verify RED**

Expected: documentation conformance assertions fail.

- [ ] **Step 3: Write `references/html-presentation.md`**

Document the manifest schema, slide-root contract, main-agent sequential authoring rule, audience-facing copy rule, default theme, resource/reference rules, iframe isolation, runtime controls, speaker notes, packaging command, and final offline QA checklist. Keep detailed rules here rather than duplicating them in `SKILL.md`.

- [ ] **Step 4: Update the main workflow and role references**

- Expand the deliverable-mode contract to four modes.
- Record the selected final target before final production.
- Keep Steps 1–7 common.
- Replace the single Step 8 with a final-production router containing an HTML branch and the existing native editable branch.
- Require the HTML role reference before authoring HTML sources.
- Keep the legacy three-step export unchanged.
- Add `Single-file HTML Presentation` to the Strategist and executor mode decisions.
- Add HTML-specific fields and notes to the design-spec template.

- [ ] **Step 5: Synchronize entry-point documentation**

Add the new command and delivery mode to `AGENTS.md`, repository `README.md`, and `scripts/README.md`. Preserve the statement that review HTML is not a final deliverable.

- [ ] **Step 6: Run tests to verify GREEN**

Run the builder suite and existing Markdown-related tests. Expected: conformance assertions pass.

- [ ] **Step 7: Commit**

```bash
git add AGENTS.md README.md skills/ppt-master/SKILL.md skills/ppt-master/references/html-presentation.md skills/ppt-master/references/strategist.md skills/ppt-master/references/executor-base.md skills/ppt-master/templates/design_spec_reference.md skills/ppt-master/scripts/README.md skills/ppt-master/scripts/test_build_single_html.py
git commit -m "docs: add final HTML presentation workflow"
```

### Task 6: Full verification and clean-context forward test

**Files:**
- Modify only if verification reveals a defect in files from Tasks 1–5.

**Interfaces:**
- Consumes: the complete HTML workflow.
- Produces: verification evidence that the artifact, CLI, existing workflows, and skill behavior meet the approved design.

- [ ] **Step 1: Run the focused and regression suites**

```bash
python3 -m unittest discover -s skills/ppt-master/scripts -p 'test_*.py' -v
python3 skills/ppt-master/scripts/svg_to_pptx/test_drawingml_context.py
```

Expected: all tests pass.

- [ ] **Step 2: Run static checks**

```bash
python3 -m py_compile skills/ppt-master/scripts/build_single_html.py
git diff --check
```

Expected: no output and zero status.

- [ ] **Step 3: Build a representative artifact**

Run the new CLI against the integration fixture or a temporary representative project with image, video, nested iframe, external anchor, custom project CSS, and notes. Decode nested iframe data and verify no runtime resources remain outside data URIs.

- [ ] **Step 4: Browser smoke-test through `file://`**

Open the generated file locally and verify next/previous navigation, hash restoration, `N` notes, interactive iframe isolation, and media pause when leaving its slide. Confirm no network requests are made.

- [ ] **Step 5: Validate the skill folder**

```bash
python3 /Users/yemingjiang/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/ppt-master
```

Expected: the skill is valid.

- [ ] **Step 6: Forward-test the revised skill**

Ask a clean-context agent to use the revised skill for the same offline HTML request used in the baseline. It must select `Single-file HTML Presentation`, preserve the skeleton review gate, author semantic `html_output/` sources after approval, run `build_single_html.py`, and avoid generating PPTX.

- [ ] **Step 7: Review working tree and commit verification fixes**

```bash
git status --short
git diff --check
```

If verification required fixes, commit them with:

```bash
git add <only-the-files-fixed-during-verification>
git commit -m "fix: harden offline HTML presentation delivery"
```
