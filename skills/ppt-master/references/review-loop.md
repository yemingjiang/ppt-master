# Skeleton Review Loop

Use this reference when packaging or revising `preview/index.html`, processing copied changes and comments, or receiving new skeleton feedback after a final artifact already exists.

## Review surface

Build and browser-QA the preview:

```bash
python3 ${SKILL_DIR}/scripts/build_preview_html.py <project_path> --source output
python3 ${SKILL_DIR}/scripts/svg_quality_checker.py <project_path>/svg_output
python3 ${SKILL_DIR}/scripts/qa_preview_html.py <project_path> --slides <changed_slide_ids> --screenshots <qa_dir> --json
```

Use the offline `preview/index.html` as the default review entry. Read [editable-review.md](editable-review.md) when building or revising it. Mapped page text and full Markdown notes are editable immediately. One “复制所有修改” / “Copy all changes” button copies a concise Markdown change list grouped by slide for pasting into Codex. Show only changed text/note passages and comments, plus short location references; complete baselines stay in the project. There is no online mode, local server, edit toggle, or download step. Generate a PDF only when the user explicitly requests static review.

The preview must:

- order the review panels as comments (input and “Copy all changes” action), speaker notes, then assets, so long notes do not push the comment entry below the fold;
- place Previous / Next controls in the current-slide takeaway card;
- keep the desktop/tablet outline independently scrollable and automatically move the active item into view;
- keep the full SVG canvas visible with aspect-preserving `contain` scaling and no internal viewer scrolling or cropping;
- keep SVG text selectable and copyable;
- forward Left / Right keys from the slide document, while keeping normal cursor movement inside text and note editors;
- retain drafts and comments after copying and rebuilding, and clear only copied snapshots that Codex explicitly acknowledged as processed;
- preserve changes made after copying, including reverting text to its old value;
- distinguish browser-only drafts from feedback copied to Codex and edits applied to project sources;
- preserve Markdown paragraph spacing and all speaker-note metadata during editing;
- provide undo and warn about text overflow without silently shrinking fonts; and
- show a selectable full-text dialog if automatic clipboard copying fails. Source conflicts are compared in Codex, not in a browser conflict UI.

## Allowed review changes

The human review loop may change:

- page count and order;
- titles, takeaways, visible copy, terminology, and metric wording;
- layout, spacing, visual hierarchy, and component sizing;
- asset selection and asset-to-claim / asset-to-technical-point mapping;
- style direction; and
- speaker-note framing.

Update the affected SVG, `main_content.md`, project handoff files, and notes when their content changes. A visual-only coordinate adjustment may update only the SVG.

Text edits must survive rebuilding the preview from these sources. Keep stable slide/text IDs when authoring revisions and reordering pages. If source mappings become stale or ambiguous, repair them before reopening the affected fields for editing.

For pasted structured feedback, inspect and apply direct edits first, then handle all comments in that record. Acknowledge direct edits and comments separately using `edit_preview.py ack`; do not acknowledge unresolved comments. Rebuilds include these receipts to clear only processed snapshots. A new build alone never authorizes clearing drafts. Legacy comment-only feedback can still be handled manually; do not guess stable slide identity from an old page number after reordering.

## Feedback after final production

When new skeleton feedback arrives after a final HTML or PPTX already exists:

1. Reopen the Human Review Loop only for the requested scope.
2. Update the skeleton and rebuild `preview/index.html`.
3. Treat every existing final artifact as stale.
4. Report that stale state explicitly.
5. Do not overwrite or regenerate the final artifact unless the user requests final regeneration or confirms the revised skeleton for final production.

For single-file HTML, `build_single_html.py --check --json` must report the stale source or export state. Refresh only tracked generated fragments with `prepare_single_html.py --refresh-changed`; never use `--force` merely to avoid resolving a customized-fragment conflict.
