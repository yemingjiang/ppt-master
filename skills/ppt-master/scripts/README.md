# PPT Master Toolset

This directory contains user-facing scripts for conversion, project setup, skeleton-doc generation, draft preview, SVG processing, export, and local fallback image generation.

## Directory Layout

- Top-level `scripts/`: runnable entry scripts
- `scripts/source_to_md/`: source-document → Markdown converters (`pdf_to_md.py`, `doc_to_md.py`, `ppt_to_md.py`, `web_to_md.py`, `web_to_md.cjs`)
- `scripts/image_backends/`: internal provider implementations used by the local fallback `image_gen.py`
- `scripts/template_import/`: internal PPTX reference-preparation helpers used by `pptx_template_import.py`
- `scripts/svg_finalize/`: internal post-processing helpers used by `finalize_svg.py`
- `scripts/docs/`: topic-focused script documentation
- `scripts/assets/`: static assets consumed by scripts

## Quick Start

Recommended skeleton-first workflow:

```bash
python3 scripts/source_to_md/pdf_to_md.py <file.pdf>
# or
python3 scripts/source_to_md/ppt_to_md.py <deck.pptx>
python3 scripts/project_manager.py init <project_name> --format ppt169
python3 scripts/project_manager.py import-sources <project_path> <source_files...> --move
# AI produces design_spec.md, main_content.md, style_sheet.md, asset_manifest.md, notes/, and svg_output/
python3 scripts/generate_skeleton_docs.py <project_path> --overwrite
python3 scripts/build_preview_html.py <project_path> --source output
```

Final polished deck:

- By default, hand the confirmed skeleton package to the `PowerPoint` skill for native editable `.pptx` production

Legacy direct export from `ppt-master` (explicit request only):

```bash
python3 scripts/total_md_split.py <project_path>
python3 scripts/finalize_svg.py <project_path>
python3 scripts/svg_to_pptx.py <project_path> -s final
```

Repository update:

```bash
python3 scripts/update_repo.py
```

## Script Index

| Area | Primary scripts | Documentation |
|------|-----------------|---------------|
| Conversion | `source_to_md/pdf_to_md.py`, `source_to_md/doc_to_md.py`, `source_to_md/ppt_to_md.py`, `source_to_md/web_to_md.py`, `source_to_md/web_to_md.cjs` | [docs/conversion.md](./docs/conversion.md) |
| Project management | `project_manager.py`, `batch_validate.py`, `generate_examples_index.py`, `error_helper.py`, `pptx_template_import.py` | [docs/project.md](./docs/project.md) |
| Skeleton docs | `generate_skeleton_docs.py` | this README |
| Draft preview | `build_preview_html.py` | this README |
| SVG pipeline / legacy export | `finalize_svg.py`, `svg_to_pptx.py`, `total_md_split.py`, `svg_quality_checker.py` | [docs/svg-pipeline.md](./docs/svg-pipeline.md) |
| Image tools | `image_gen.py` (local fallback), `analyze_images.py`, `gemini_watermark_remover.py` | [docs/image.md](./docs/image.md) |
| Repo maintenance | `update_repo.py` | README install/update section |
| Troubleshooting | validation, preview, export, dependency issues | [docs/troubleshooting.md](./docs/troubleshooting.md) |

## High-Frequency Commands

Conversion:

```bash
python3 scripts/source_to_md/pdf_to_md.py <file.pdf>
python3 scripts/source_to_md/ppt_to_md.py <deck.pptx>
python3 scripts/source_to_md/doc_to_md.py <file.docx>
python3 scripts/source_to_md/web_to_md.py <url>
```

Project setup:

```bash
python3 scripts/project_manager.py init <project_name> --format ppt169
python3 scripts/project_manager.py import-sources <project_path> <source_files...> --move
python3 scripts/project_manager.py validate <project_path>
```

Draft review:

```bash
python3 scripts/generate_skeleton_docs.py <project_path> --overwrite
python3 scripts/build_preview_html.py <project_path> --source output
```

Template source import:

```bash
python3 scripts/pptx_template_import.py <template.pptx>
python3 scripts/pptx_template_import.py <template.pptx> --manifest-only
```

Legacy post-processing and export:

```bash
python3 scripts/total_md_split.py <project_path>
python3 scripts/finalize_svg.py <project_path>
python3 scripts/svg_to_pptx.py <project_path> -s final
```

Image generation:

In Codex sessions, prefer the built-in `image_gen` tool first.
Use the local CLI below when you need provider-controlled or direct filesystem output.

```bash
python3 scripts/image_gen.py "A modern futuristic workspace"
python3 scripts/image_gen.py --list-backends
python3 scripts/analyze_images.py <project_path>/images
```

Repository update:

```bash
python3 scripts/update_repo.py
python3 scripts/update_repo.py --skip-pip
```

## Recommendations

- Keep one user-facing entry point per workflow at the top level of `scripts/`
- Move provider-specific or helper internals into subdirectories
- Prefer the unified entry points `project_manager.py` and `finalize_svg.py`; in Codex sessions prefer the built-in `image_gen` tool before the local `image_gen.py`
- Prefer `generate_skeleton_docs.py` to keep `main_content.md`, `style_sheet.md`, and `asset_manifest.md` synchronized
- Prefer `preview/index.html` over static PDF when reviewing draft skeletons
- Treat `preview/index.html` as the main review entry point. In Codex desktop, return its absolute file URL to the user.
- `preview/index.html` opened via `file://` should support the no-server review loop: keep comments in local browser storage, then use copy-all and paste the review comments back to Codex
- After Codex applies the pasted review and rebuilds `preview/index.html`, treat that rebuilt file as the next review round; old local comments should not carry over
- Prefer handing the confirmed skeleton package to the `PowerPoint` skill for final editable production
- Prefer `svg_final/` over `svg_output/` only when doing legacy direct export

## Related Docs

- [Conversion Tools](./docs/conversion.md)
- [Project Tools](./docs/project.md)
- [SVG Pipeline Tools](./docs/svg-pipeline.md)
- [Image Tools](./docs/image.md)
- [Troubleshooting](./docs/troubleshooting.md)
- [AGENTS Guide](../../../AGENTS.md)

_Last updated: 2026-04-20_
