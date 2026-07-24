# Skeleton Review Loop

Use this reference when packaging or revising `preview/index.html`, applying pasted review comments, or receiving new skeleton feedback after a final artifact already exists.

## Review surface

Build and browser-QA the preview:

```bash
python3 ${SKILL_DIR}/scripts/build_preview_html.py <project_path> --source output
python3 ${SKILL_DIR}/scripts/svg_quality_checker.py <project_path>/svg_output
python3 ${SKILL_DIR}/scripts/qa_preview_html.py <project_path> --slides <changed_slide_ids> --screenshots <qa_dir> --json
```

Use `preview/index.html` as the default review entry. Keep comments in browser-local storage, copy all comments, and paste them back into Codex. Generate a PDF only when the user explicitly requests static review.

The preview must:

- place Previous / Next controls in the current-slide takeaway card;
- keep the desktop/tablet outline independently scrollable and automatically move the active item into view;
- keep the full SVG canvas visible with aspect-preserving `contain` scaling and no internal viewer scrolling or cropping;
- keep SVG text selectable and copyable;
- forward Left / Right keys from the slide document when same-origin iframe access is available; and
- treat every rebuilt preview as a fresh review round without carrying old local comments forward.

## Allowed review changes

The human review loop may change:

- page count and order;
- titles, takeaways, visible copy, terminology, and metric wording;
- layout, spacing, visual hierarchy, and component sizing;
- asset selection and asset-to-claim / asset-to-technical-point mapping;
- style direction; and
- speaker-note framing.

Update the affected SVG, `main_content.md`, project handoff files, and notes when their content changes. A visual-only coordinate adjustment may update only the SVG.

## Feedback after final production

When new skeleton feedback arrives after a final HTML or PPTX already exists:

1. Reopen the Human Review Loop only for the requested scope.
2. Update the skeleton and rebuild `preview/index.html`.
3. Treat every existing final artifact as stale.
4. Report that stale state explicitly.
5. Do not overwrite or regenerate the final artifact unless the user requests final regeneration or confirms the revised skeleton for final production.

For single-file HTML, `build_single_html.py --check --json` must report the stale source or export state. Refresh only tracked generated fragments with `prepare_single_html.py --refresh-changed`; never use `--force` merely to avoid resolving a customized-fragment conflict.
