# Troubleshooting

## Validation Failed

1. Run:

```bash
python3 scripts/project_manager.py validate <project_path>
```

2. Fix missing files or invalid directories reported by the validator.
3. Re-run validation before post-processing or export.

## SVG Preview Looks Wrong

1. Check the file path and filename.
2. Confirm naming conventions are consistent.
3. Default review surface: rebuild `preview/index.html` and open it via `file://`:

```bash
python3 scripts/build_preview_html.py <project_path> --source output
```

4. If an image is missing, check its path relative to the source SVG and confirm the asset exists. Use the offline HTML review surface; for portable drafts, embed the asset using the SVG image-embedding reference. Do not introduce a local service for the review workflow.

## Offline Draft Changes

- Mapped text and Markdown notes are editable by default. For text that does not respond to clicks, inspect the manifest's read-only list and repair its source binding; see [editable-review.md](../../references/editable-review.md).
- “Copy all changes” produces a Markdown change list with direct edits, changed note passages and comments. Older JSON records remain supported. If browser clipboard access fails, copy the full text from the fallback dialog and paste it into Codex.
- Copying does not save project files or clear drafts. Only processed feedback receipts in a rebuilt preview clear matching copied snapshots; later edits remain.
- If a short reference or baseline cannot be resolved, use the originating project with its `preview/review_index.json` and `preview/review_baselines/` intact. Do not substitute the latest notes as the missing original.
- Source conflicts are inspected and resolved in Codex. Preserve the original copied record rather than changing its baseline or record ID.

## Speaker Notes Do Not Split

Check `total.md`:
- headings must start with `# `
- heading text must match SVG filenames
- sections must be separated by `---`

Then rerun:

```bash
python3 scripts/total_md_split.py <project_path>
```

## Final Deck Quality Issues

If the issue appears in the preferred native editable final deck:

1. Check whether the reviewed skeleton in `preview/index.html` is already correct.
2. If the skeleton is correct, fix the native editable rebuild phase rather than changing unrelated SVG pages.
3. Pay special attention to wrap-sensitive and alignment-sensitive blocks such as KPI cards, metric badges, comparison numbers, and footer/page-number chrome.

## Legacy PPT Export Quality Issues

Preferred sequence:

```bash
python3 scripts/total_md_split.py <project_path>
python3 scripts/finalize_svg.py <project_path>
python3 scripts/svg_to_pptx.py <project_path> -s final
```

Do not export directly from `svg_output/` when `svg_final/` exists.

## Dependency Checklist

Most tools use the standard library. Install extra dependencies only when needed:

```bash
pip install -r requirements.txt
```

Important optional packages:
- `python-pptx` for PPTX export
- `Pillow` for image utilities
- `numpy` for watermark removal
- `PyMuPDF` for PDF conversion
- `google-genai` / `openai` for image generation backends
