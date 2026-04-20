---
name: ppt-master
description: >
  Use when the user has source materials and needs a presentation skeleton,
  slide-by-slide outline, visual direction, reviewable draft, and handoff package
  before building the final editable PowerPoint, or when they mention "ppt-master".
---

# PPT Master Skill

> Skeleton-first presentation workflow. Converts source documents into a reviewable presentation skeleton, fast HTML visual draft, and PowerPoint handoff package.

**Default Pipeline**: `Source Document → Create Project → Template Option → Strategist → [Image_Generator] → Skeleton Executor → Human Review Loop → PowerPoint Handoff`

**Legacy Compatibility Pipeline**: `Source Document → Create Project → Template Option → Strategist → [Image_Generator] → SVG Executor → Post-processing → Export`

> [!CAUTION]
> ## 🚨 Global Execution Discipline (MANDATORY)
>
> **This workflow is a strict serial pipeline. The following rules have the highest priority — violating any one of them constitutes execution failure:**
>
> 1. **SERIAL EXECUTION** — Steps MUST be executed in order; the output of each step is the input for the next. Non-BLOCKING adjacent steps may proceed continuously once prerequisites are met, without waiting for the user to say "continue"
> 2. **BLOCKING = HARD STOP** — Steps marked ⛔ BLOCKING require a full stop; the AI MUST wait for an explicit user response before proceeding and MUST NOT make any decisions on behalf of the user
> 3. **NO CROSS-PHASE BUNDLING** — Cross-phase bundling is FORBIDDEN. (Note: the Eight Confirmations in Step 4 are ⛔ BLOCKING — the AI MUST present recommendations and wait for explicit user confirmation before proceeding. Once the user confirms, all subsequent non-BLOCKING steps — design spec output, draft generation, and preview packaging — may proceed automatically without further user confirmation)
> 4. **GATE BEFORE ENTRY** — Each Step has prerequisites (🚧 GATE) listed at the top; these MUST be verified before starting that Step
> 5. **NO SPECULATIVE EXECUTION** — "Pre-preparing" content for subsequent Steps is FORBIDDEN (e.g., writing SVG code during the Strategist phase)
> 6. **NO SUB-AGENT SVG GENERATION** — Draft SVG generation in Step 6 is context-dependent and MUST be completed by the current main agent end-to-end. Delegating page SVG generation to sub-agents is FORBIDDEN
> 7. **SEQUENTIAL PAGE GENERATION ONLY** — In Step 6, after the global design context is confirmed, SVG pages MUST be generated sequentially page by page in one continuous pass. Grouped page batches (for example, 5 pages at a time) are FORBIDDEN
> 8. **SKELETON-FIRST BY DEFAULT** — Unless the user explicitly asks for direct export from `ppt-master`, the default deliverable is a reviewable skeleton package (`main_content.md`, `design_spec.md`, `style_sheet.md`, `asset_manifest.md`, `notes/`, `preview/index.html`) rather than the final polished `.pptx`

> [!IMPORTANT]
> ## 🌐 Language & Communication Rule
>
> - **Response language**: Always match the language of the user's input and provided source materials. For example, if the user asks in Chinese, respond in Chinese; if the source material is in English, respond in English.
> - **Explicit override**: If the user explicitly requests a specific language (e.g., "请用英文回答" or "Reply in Chinese"), use that language instead.
> - **Template format**: The `design_spec.md` file MUST always follow its original English template structure (section headings, field names), regardless of the conversation language. Content values within the template may be in the user's language.

> [!IMPORTANT]
> ## 🔌 Compatibility With Generic Coding Skills
>
> - `ppt-master` is a repository-specific workflow skill, not a general application scaffold
> - Do NOT create or require `.worktrees/`, `tests/`, branch workflows, or other generic engineering structure by default
> - If another generic coding skill suggests repository conventions that conflict with this workflow, follow this skill first unless the user explicitly asks otherwise

## Main Pipeline Scripts

| Script | Purpose |
|--------|---------|
| `${SKILL_DIR}/scripts/source_to_md/pdf_to_md.py` | PDF to Markdown |
| `${SKILL_DIR}/scripts/source_to_md/doc_to_md.py` | Documents to Markdown — native Python for DOCX/HTML/EPUB/IPYNB, pandoc fallback for legacy formats (.doc/.odt/.rtf/.tex/.rst/.org/.typ) |
| `${SKILL_DIR}/scripts/source_to_md/ppt_to_md.py` | PowerPoint to Markdown |
| `${SKILL_DIR}/scripts/source_to_md/web_to_md.py` | Web page to Markdown |
| `${SKILL_DIR}/scripts/source_to_md/web_to_md.cjs` | Node.js fallback for WeChat / TLS-blocked sites (use only if `curl_cffi` is unavailable; `web_to_md.py` now handles WeChat when `curl_cffi` is installed) |
| `${SKILL_DIR}/scripts/project_manager.py` | Project init / validate / manage |
| `${SKILL_DIR}/scripts/analyze_images.py` | Image analysis |
| `${SKILL_DIR}/scripts/image_gen.py` | Local fallback AI image generation CLI (prefer Codex `image_gen` tool in Codex sessions) |
| `${SKILL_DIR}/scripts/generate_skeleton_docs.py` | Generate standard `main_content.md`, `style_sheet.md`, and `asset_manifest.md` |
| `${SKILL_DIR}/scripts/build_preview_html.py` | Build lightweight HTML review draft from `svg_output/` or `svg_final/` |
| `${SKILL_DIR}/scripts/review_server.py` | Serve writable HTML review draft and apply comments back to `main_content.md` |
| `${SKILL_DIR}/scripts/svg_quality_checker.py` | SVG quality check |
| `${SKILL_DIR}/scripts/total_md_split.py` | Speaker notes splitting |
| `${SKILL_DIR}/scripts/finalize_svg.py` | SVG post-processing (unified entry) |
| `${SKILL_DIR}/scripts/svg_to_pptx.py` | Export to PPTX |

For complete tool documentation, see `${SKILL_DIR}/scripts/README.md`.

## Default Deliverables

By default, `ppt-master` should leave the project in a state that is easy for humans to review and easy for the `PowerPoint` skill to consume:

- `<project_path>/main_content.md` — editable skeleton outline and primary human content source
- `<project_path>/design_spec.md` — visual and narrative specification
- `<project_path>/style_sheet.md` — fonts, colors, size minimums, component rules
- `<project_path>/asset_manifest.md` — per-slide asset mapping
- `<project_path>/notes/total.md` — speaker notes
- `<project_path>/svg_output/` — raw visual draft pages
- `<project_path>/preview/index.html` — preferred fast review surface

Only create `<project_path>/exports/*.pptx` from this skill when the user explicitly asks for direct export or the `PowerPoint` skill is unavailable.

## Template Index

| Index | Path | Purpose |
|-------|------|---------|
| Layout templates | `${SKILL_DIR}/templates/layouts/layouts_index.json` | Query available page layout templates |
| Visualization templates | `${SKILL_DIR}/templates/charts/charts_index.json` | Query available visualization SVG templates (charts, infographics, diagrams, frameworks) |
| Icon library | `${SKILL_DIR}/templates/icons/` | Search icons on demand: `ls templates/icons/<library>/ \| grep <keyword>` (libraries: `chunk/`, `tabler-filled/`, `tabler-outline/`) |

## Standalone Workflows

| Workflow | Path | Purpose |
|----------|------|---------|
| `create-template` | `workflows/create-template.md` | Standalone template creation workflow |

---

## Workflow

### Step 1: Source Content Processing

🚧 **GATE**: User has provided source material (PDF / DOCX / EPUB / URL / Markdown file / text description / conversation content — any form is acceptable).

When the user provides non-Markdown content, convert immediately:

| User Provides | Command |
|---------------|---------|
| PDF file | `python3 ${SKILL_DIR}/scripts/source_to_md/pdf_to_md.py <file>` |
| DOCX / Word / Office document | `python3 ${SKILL_DIR}/scripts/source_to_md/doc_to_md.py <file>` |
| PPTX / PowerPoint deck | `python3 ${SKILL_DIR}/scripts/source_to_md/ppt_to_md.py <file>` |
| EPUB / HTML / LaTeX / RST / other | `python3 ${SKILL_DIR}/scripts/source_to_md/doc_to_md.py <file>` |
| Web link | `python3 ${SKILL_DIR}/scripts/source_to_md/web_to_md.py <URL>` |
| WeChat / high-security site | `python3 ${SKILL_DIR}/scripts/source_to_md/web_to_md.py <URL>` (requires `curl_cffi`; falls back to `node web_to_md.cjs <URL>` only if that package is unavailable) |
| Markdown | Read directly |

**✅ Checkpoint — Confirm source content is ready, proceed to Step 2.**

---

### Step 2: Project Initialization

🚧 **GATE**: Step 1 complete; source content is ready (Markdown file, user-provided text, or requirements described in conversation are all valid).

```bash
python3 ${SKILL_DIR}/scripts/project_manager.py init <project_name> --format <format>
```

Format options: `ppt169` (default), `ppt43`, `xhs`, `story`, etc. For the full format list, see `references/canvas-formats.md`.

Import source content (choose based on the situation):

| Situation | Action |
|-----------|--------|
| Has source files (PDF/MD/etc.) | `python3 ${SKILL_DIR}/scripts/project_manager.py import-sources <project_path> <source_files...> --move` |
| User provided text directly in conversation | No import needed — content is already in conversation context; subsequent steps can reference it directly |

> ⚠️ **MUST use `--move`**: All source files (original PDF / MD / images) MUST be **moved** (not copied) into `sources/` for archiving.
> - Markdown files generated in Step 1, original PDFs, original MDs — **all** must be moved into the project via `import-sources --move`
> - Intermediate artifacts (e.g., `_files/` directories) are handled automatically by `import-sources`
> - After execution, source files no longer exist at their original location

**✅ Checkpoint — Confirm project structure created successfully, `sources/` contains all source files, converted materials are ready. Proceed to Step 3.**

---

### Step 3: Template Selection

🚧 **GATE**: Step 2 complete; project directory structure is ready.

⛔ **BLOCKING**: If the user has not yet clearly expressed whether to use a template, you MUST present options and **wait for an explicit user response** before proceeding. If the user has previously stated "no template" or specified a particular template, skip this prompt and proceed directly.

**⚡ Early-exit**: If the user has already stated "no template" / "不使用模板" / "自由设计" (or equivalent) at any prior point in the conversation, **do NOT query `layouts_index.json`** — skip directly to Step 4. This avoids unnecessary token consumption.

**Template recommendation flow** (only when the user has NOT yet decided):
Query `${SKILL_DIR}/templates/layouts/layouts_index.json` to list available templates and their style descriptions.
**When presenting options, you MUST provide a professional recommendation based on the current PPT topic and content** (recommend a specific template or free design, with reasoning). By default, **lean toward free design** unless the content clearly benefits from a fixed structural preset (e.g., consulting report, annual report, academic paper). Then ask the user:

> 💡 **AI Recommendation**: Based on your content topic (brief summary), I recommend **[specific template / free design]** because...
>
> Note: Both options produce fully-designed output. A template is a validated **"structure + style" preset** (e.g., McKinsey-style, Google-style); free design lets the AI tailor structure and style to your specific content — usually yielding a more content-fitting result.
>
> Which approach would you prefer?
> **A) Use an existing template** — apply a validated structure+style preset (please specify template name or style preference)
> **B) Free design** (recommended for most cases) — AI tailors structure and style to your content

After the user confirms option A, copy template files to the project directory:
```bash
cp ${SKILL_DIR}/templates/layouts/<template_name>/*.svg <project_path>/templates/
cp ${SKILL_DIR}/templates/layouts/<template_name>/design_spec.md <project_path>/templates/
cp ${SKILL_DIR}/templates/layouts/<template_name>/*.png <project_path>/images/ 2>/dev/null || true
cp ${SKILL_DIR}/templates/layouts/<template_name>/*.jpg <project_path>/images/ 2>/dev/null || true
```

After the user confirms option B (free design), proceed directly to Step 4.

> To create a new global template, read `workflows/create-template.md`

**✅ Checkpoint — User has responded with template selection, template files copied (if option A). Proceed to Step 4.**

---

### Step 4: Strategist Phase (MANDATORY — cannot be skipped)

🚧 **GATE**: Step 3 complete; user has confirmed template selection.

First, read the role definition:
```
Read references/strategist.md
```

> ⚠️ **Mandatory gate in `strategist.md`**: Before writing `design_spec.md`, Strategist MUST `read_file templates/design_spec_reference.md` and produce the spec following its full I–XI section structure. See `strategist.md` Section 1 for the explicit gate rule.

**Must complete the Eight Confirmations** (full template structure in `templates/design_spec_reference.md`):

⛔ **BLOCKING**: The Eight Confirmations MUST be presented to the user as a bundled set of recommendations, and you MUST **wait for the user to confirm or modify** before outputting the Design Specification & Content Outline. This is one of only two core confirmation points in the workflow (the other is template selection). Once confirmed, all subsequent script execution and slide generation should proceed fully automatically.

1. Canvas format
2. Page count range
3. Target audience
4. Style objective
5. Color scheme
6. Icon usage approach
7. Typography plan
8. Image usage approach

If the user has provided images, run the analysis script **before outputting the design spec** (do NOT directly read/open image files — use the script output only):
```bash
python3 ${SKILL_DIR}/scripts/analyze_images.py <project_path>/images
```

> ⚠️ **Image handling rule**: The AI must NEVER directly read, open, or view image files (`.jpg`, `.png`, etc.). All image information must come from the `analyze_images.py` script output or the Design Specification's Image Resource List.

**Output**: `<project_path>/design_spec.md`

**✅ Checkpoint — Phase deliverables complete, auto-proceed to next step**:
```markdown
## ✅ Strategist Phase Complete
- [x] Eight Confirmations completed (user confirmed)
- [x] Design Specification & Content Outline generated
- [ ] **Next**: Auto-proceed to [Image_Generator / Skeleton Executor] phase
```

---

### Step 5: Image_Generator Phase (Conditional)

🚧 **GATE**: Step 4 complete; Design Specification & Content Outline generated and user confirmed.

> **Trigger condition**: Image approach includes "AI generation". If not triggered, skip directly to Step 6 (Step 6 GATE must still be satisfied).

Read `references/image-generator.md`

> **Codex-first execution rule**: In Codex sessions, use the built-in `image_gen` tool as the default image generation path. Use `${SKILL_DIR}/scripts/image_gen.py` only as a fallback when the user explicitly wants local/provider-controlled generation, when batch filesystem output is required, or when the built-in tool is unavailable.

1. Extract all images with status "pending generation" from the design spec
2. Generate prompt document → `<project_path>/images/image_prompts.md`
3. Generate images with the Codex `image_gen` tool and materialize them into `<project_path>/images/` using the filenames from the resource list
4. If direct materialization into `<project_path>/images/` is required and the built-in tool cannot provide it, fall back to:
   ```bash
   python3 ${SKILL_DIR}/scripts/image_gen.py "prompt" --aspect_ratio 16:9 --image_size 1K -o <project_path>/images
   ```

**✅ Checkpoint — Confirm all images are ready, proceed to Step 6**:
```markdown
## ✅ Image_Generator Phase Complete
- [x] Prompt document created
- [x] All images saved to images/
```

---

### Step 6: Skeleton Executor Phase

🚧 **GATE**: Step 4 (and Step 5 if triggered) complete; all prerequisite deliverables are ready.

Read the role definition based on the selected style:
```
Read references/executor-base.md          # REQUIRED: common guidelines
Read references/executor-general.md       # General flexible style
Read references/executor-consultant.md    # Consulting style
Read references/executor-consultant-top.md # Top consulting style (MBB level)
```

> Only need to read executor-base + one style file.

**Design Parameter Confirmation (Mandatory)**: Before generating the first SVG, the Executor MUST review and output key design parameters from the Design Specification (canvas dimensions, color scheme, font plan, body font size) to ensure spec adherence. See executor-base.md Section 2 for details.

> ⚠️ **Main-agent only rule**: SVG generation in Step 6 MUST remain with the current main agent because page design depends on full upstream context (source content, design spec, template mapping, image decisions, and cross-page consistency). Do NOT delegate any slide SVG generation to sub-agents.
> ⚠️ **Generation rhythm rule**: After confirming the global design parameters, the Executor MUST generate pages sequentially, one page at a time, while staying in the same continuous main-agent context. Do NOT split Step 6 into grouped page batches such as 5 pages per batch.

**Visual Draft Construction Phase**:
- Generate SVG pages sequentially, one page at a time, in one continuous pass → `<project_path>/svg_output/`

**Draft Packaging Phase**:
- Update or generate `<project_path>/main_content.md`
- Generate `<project_path>/style_sheet.md` and `<project_path>/asset_manifest.md`
  - Recommended command: `python3 ${SKILL_DIR}/scripts/generate_skeleton_docs.py <project_path> --overwrite`
- Generate speaker notes → `<project_path>/notes/total.md`
- Build lightweight HTML review draft → `<project_path>/preview/index.html`
  - Recommended command: `python3 ${SKILL_DIR}/scripts/build_preview_html.py <project_path> --source output`
- Start writable review surface when comments need to update files directly
  - Recommended command: `python3 ${SKILL_DIR}/scripts/review_server.py <project_path> --source output`
- Only generate `preview/draft.pdf` when the user explicitly asks for PDF review

**✅ Checkpoint — Confirm the skeleton package is fully generated. Proceed to Step 7 human review**:
```markdown
## ✅ Skeleton Executor Phase Complete
- [x] All SVGs generated to svg_output/
- [x] Skeleton files generated (`main_content.md`, `style_sheet.md`, `asset_manifest.md`, `notes/`)
- [x] HTML draft ready at preview/index.html
```

---

### Step 7: Human Review Loop

🚧 **GATE**: Step 6 complete; the skeleton package and HTML draft are available.

⛔ **BLOCKING**: Present the draft and wait for human feedback. Iterate on the skeleton until the user confirms the structure is locked.

Allowed iteration scope in this loop:

- Page count
- Page order
- Per-page title
- Per-page one-line takeaway
- Body bullets
- Asset selection
- Style direction
- Notes framing

During this loop:

- Prefer reviewing `preview/index.html`
- Use `draft.pdf` only when the user explicitly prefers a static review file
- Do not start final PowerPoint polishing until the user confirms the skeleton is stable

**✅ Checkpoint — Human confirms the skeleton is locked for final production**:
```markdown
## ✅ Human Review Loop Complete
- [x] Skeleton confirmed by user
- [x] `main_content.md` and handoff files updated to match the confirmed structure
- [ ] **Next**: Switch to the `PowerPoint` skill for final editable production
```

---

### Step 8: PowerPoint Handoff

🚧 **GATE**: Step 7 complete; the human has confirmed the skeleton, and handoff files are up to date.

The final editable deck should now be produced by the `PowerPoint` skill, not by `ppt-master`.

Required handoff inputs:

- `<project_path>/main_content.md`
- `<project_path>/design_spec.md`
- `<project_path>/style_sheet.md`
- `<project_path>/asset_manifest.md`
- reference style deck(s)
- confirmed image / video / screenshot assets

Handoff rule:

- `ppt-master` owns structure, direction, and review package
- `PowerPoint` owns the final native editable `.pptx`
- Once the project enters the `PowerPoint` phase, do not return to `ppt-master` for layout polish unless the content structure changes substantially

---

## Legacy Compatibility Mode

Only use this path when the user explicitly asks `ppt-master` to export PPTX directly, or when the `PowerPoint` skill is unavailable.

🚧 **GATE**: A completed SVG draft exists and the user explicitly wants direct export from `ppt-master`.

> ⚠️ The following three sub-steps MUST be **executed individually one at a time**. Each command must complete and be confirmed successful before running the next.
> ❌ **NEVER** put all three commands in a single code block or single shell invocation.

**Legacy Step 1** — Split speaker notes:
```bash
python3 ${SKILL_DIR}/scripts/total_md_split.py <project_path>
```

**Legacy Step 2** — SVG post-processing (icon embedding / image crop & embed / text flattening / rounded rect to path):
```bash
python3 ${SKILL_DIR}/scripts/finalize_svg.py <project_path>
```

**Legacy Step 3** — Export PPTX (embeds speaker notes by default):
```bash
python3 ${SKILL_DIR}/scripts/svg_to_pptx.py <project_path> -s final
# Output: exports/<project_name>_<timestamp>.pptx + exports/<project_name>_<timestamp>_svg.pptx
```

> ❌ **NEVER** use `cp` as a substitute for `finalize_svg.py` — it performs multiple critical processing steps
> ❌ **NEVER** export directly from `svg_output/` — MUST use `-s final` to export from `svg_final/`
> ❌ **NEVER** add extra flags like `--only`

---

## Role Switching Protocol

Before switching roles, you **MUST first read** the corresponding reference file — skipping is FORBIDDEN. Output marker:

```markdown
## [Role Switch: <Role Name>]
📖 Reading role definition: references/<filename>.md
📋 Current task: <brief description>
```

---

## Reference Resources

| Resource | Path |
|----------|------|
| Shared technical constraints | `references/shared-standards.md` |
| Canvas format specification | `references/canvas-formats.md` |
| Image layout specification | `references/image-layout-spec.md` |
| SVG image embedding | `references/svg-image-embedding.md` |

---

## Notes

- Default draft review surface: `python3 ${SKILL_DIR}/scripts/build_preview_html.py <project_path> --source output`
- Standard handoff docs: `python3 ${SKILL_DIR}/scripts/generate_skeleton_docs.py <project_path> --overwrite`
- Writable review server: `python3 ${SKILL_DIR}/scripts/review_server.py <project_path> --source output`
- Legacy direct export remains available, but it is no longer the default completion path
- **Troubleshooting**: If the user encounters issues during generation (layout overflow, export errors, blank images, etc.), recommend checking `docs/faq.md` — it contains known solutions sourced from real user reports and is continuously updated
