# Offline editable review previews

Raw-SVG review drafts are editable by default. Click mapped slide text, edit full Markdown speaker notes, drag the left outline to reorder pages, and leave comments. The sidebar provides **“保存 HTML” / “Save HTML”**, a copy action and undo. In supported Chrome browsers, saving writes text, notes and page order into the user-selected original HTML. After saving, **“复制批注” / “Copy comments”** sends only feedback to Codex. Unsaved content retains **“复制所有修改” / “Copy all changes”** as a fallback. There is no server, edit-mode switch or downloaded modification package. Layout changes, adding/deleting pages and media replacement remain Codex-assisted work.

## Build and open

```bash
python3 ${SKILL_DIR}/scripts/build_preview_html.py <project_path> --source output --json
```

Open the resulting `preview/index.html` as a local file. Only `svg_output/` is editable, and it requires `main_content.md`. The optional `--editable` flag is retained for compatibility; `--read-only` explicitly builds a diagnostic/read-only view without deleting drafts or the manifest. This review surface does not select final HTML or PPTX production.

## Authorized offline file saving

- Serve nothing: open `preview/index.html` through `file://` in Chrome. Detect secure-context and `showOpenFilePicker` support at runtime; disable save with a clear fallback in unsupported browsers, including embedded browsers that lack the API.
- The first Save click in each tab/session opens a picker. The user selects the **currently opened HTML** and authorizes writing. Reuse the handle in memory for later saves; reopening requires selecting it again. Never claim that merely opening a local HTML grants write access.
- First-time automatic positioning at an arbitrary local path is not available: `startIn` only accepts well-known directories or previously obtained handles. Do not pass a file URL/path as `startIn`. When Save HTML needs a picker, automatically copy the original native path from the current `file://` URL (without query/hash) before opening it. Use a synchronous copy first to preserve user activation, with async clipboard fallback. If copying fails, select the visible path and ask the user to copy it and click Save again; if activation expires during permission handling, retain the copied path and ask for a fresh click. Reusing a granted file handle must not touch the clipboard. Do not add a separate path-copy button. Retain a selectable path only as the copy-failure fallback, with macOS ⌘⇧G instructions to reveal the native picker’s path input. The web page cannot restyle the native picker or force that input to appear. Use a stable project-specific picker `id` so Chrome can remember the previously selected directory; this is a browser hint, not guaranteed first-time positioning or automatic authorization.
- Verify project, build and saved-copy identity before requesting a writable stream. Reject a different file, a newer rebuilt draft, or a save made by another tab. Cancel/permission denial leaves edits intact. Edits made during a save remain dirty until saved separately.
- Replace only the inert `ppt-master-saved-state` JSON in the selected file; escape `<` and preserve the original HTML, scripts, styles and asset references. Never serialize the live editor DOM. Reopening the saved HTML in a clean browser restores text, notes and page order without localStorage. Save writes only that HTML, not Markdown/SVG project sources. Comments remain browser-local and are copied for review.
- **Before any agent-side source editing**, run `build_preview_html.py` once. It imports the saved content through existing stable bindings, baseline checks, backups and processing receipts, then rebuilds. The HTML finalizer also imports saved edits before preparing slides. A dry-run with unapplied saved edits stops and asks for the preview rebuild; it never silently exports stale source. Conflicting edits stop automatic replacement and retain the original HTML for reconciliation.
- `saved_html.py` reads only the inert JSON, never executes browser scripts. Saved packets contain text, notes and page order, and never mark comments processed. Saved drafts remain tied to the original project; keep the project together for subsequent regeneration and relative assets. Alternate preview outputs are also checked, but the normal user path is `preview/index.html`.

## Stable source bindings

`main_content.md` remains the source for content, `notes/total.md` for notes, and SVG for visual placement. `preview/editable_manifest.json` is a generated map and revision snapshot, not a competing content source.

- Each SVG root receives `data-pm-slide`, a persistent UUID independent of page numbering. Preserve it when renaming/reordering a slide; give duplicated slides new IDs.
- Mark any visible automatic page-number text as `data-pm-page-number="true"` on a plain `<text>` node, without a content-field binding. These nodes track the current continuous page number in the preview and after source application. Do not guess that an arbitrary numeric metric is a page number; migrate old unmarked page-number labels explicitly during review.
- Each editable `<text>` has a unique persistent `id` and `data-pm-field="title"`, `"takeaway"`, or `"bullets.N"` (zero-based index in that page's main-content bullets). Preserve IDs during revisions and update bindings if the content structure changes.
- For new drafts, ensure each independently editable visible text block has a corresponding content field. Use explicit bindings for repeated wording. Section markers and page numbers can stay read-only.
- First-time migration automatically binds only plain text with an unambiguous exact source match. Repeated nodes/fields, partial-string matches, inconsistent mappings and complex styled `<tspan>` structures stay read-only. Inspect the manifest's `readonly` list; repair audience-facing mappings before claiming the whole page is editable.
- Do not bind one fragment of a sentence to an entire title. A two-line title can use two bullet fields; when the page title/takeaway exactly equals the concatenated leading bullets, the editor keeps these aliases synchronized. More complex relationships require explicit content restructuring by Codex.
- A field can introduce manual line breaks. They are stored as SVG `<tspan>` layout, with unchanged font and color and 1.4em line spacing; the main content stores the joined wording. Spaces entered by the user are preserved. Overflow/overlap is flagged, never fixed by silent font shrinking. Complex typography still needs Codex reflow and visual QA.

Example explicit plain-text binding:

```xml
<text id="main-claim" data-pm-field="bullets.0" x="96" y="295"
      font-size="64" fill="#171717">把个人经验，</text>
```

IDs and binding attributes do not add scripts or editable HTML to source SVGs. The preview uses a sandboxed inline frame and a separate HTML editing overlay; final exports still consume the saved SVG/content sources.

## Save and clipboard review loop

### Reordering the deck

Drag the `⋮⋮` handle in the left outline to an insertion line. The outline scrolls at its edges; focus the handle and use Alt+Up/Down for precise movement. The selected slide stays selected, navigation follows the new order, and page numbers update from 01. Undo and browser refresh retain the same per-slide text, notes and comments.

An unsaved permutation adds one global section to **Copy all changes**, even if no text or comments changed:

```markdown
## 全局修改：页面顺序
按新顺序排列全部页面，并从 01 连续编号；正文、备注和批注跟随原页面。
原顺序：s1 → s2 → s3
新顺序：s3 → s1 → s2
```

The short references identify slides, not current page numbers. Keep this section in the complete project/version/record envelope. Do not ask the user to describe each move separately. Save HTML also persists the permutation in its inert state; a clean browser restores it and the next preview build imports it. Once saved, only remaining unsaved changes/comments need copying.

`edit_preview.py inspect/apply --dry-run/apply` accepts order-only and combined records. Applying renames `svg_output` and matching note filenames, reorders and renumbers `main_content.md`, the design-spec outline, total notes and existing asset mappings in one backed-up transaction. Existing chapter headings stay in place; after a cross-chapter move, review chapter titles, narrative transitions and custom page references in Codex. Automatic numbering changes only explicit page-number nodes. Stable IDs and archived review references survive; older text-only feedback still targets the original page. A different current order or added/removed pages requires reconciliation, never a guessed partial permutation. Existing final HTML/PPTX remains stale until the normal final-production workflow runs.

Processing receipts acknowledge the copied/saved order snapshot as content. Later reorders, including returning to the old order after copying, remain pending. Do not clear an order merely because a new preview was generated.

### Applying review feedback

1. The user edits page text, notes and comments directly. Keep the comments input and copy action before notes; assets follow notes. Hover/focus indicators should be subtle. Arrow keys move the cursor inside editors and navigate slides elsewhere.
2. Prefer saving text, notes and page order with “Save HTML”; the copy action then includes comments only. For unsaved content, “Copy all changes” copies one Markdown change list with a global order section when needed, followed by slide-specific edits. Show original/new wording, only changed note passages with minimal context, and literal comments together. Omit untouched pages, empty sections, repeated page metadata and full technical IDs. Use short project/version/slide/text/record references. For a whole-note rewrite, include the new notes once; the original stays in the version archive. The user pastes it into Codex; no file transfer is needed. If automatic copying fails, show the complete record in a selectable text dialog. Never clear drafts just because copying succeeded.
3. Codex first rebuilds the draft to import already-saved HTML content, preserves that exact copied record, inspects it, and dry-runs/applies direct edits. An agent-side temporary text file is allowed for reliable tool input; do not ask the user to download or upload a package. Prefer stdin or structured tool arguments, and never interpolate pasted content into executable shell text.
4. Codex reads and handles the comments as review instructions. Applying text does **not** mark comments handled. Resolve conflicts using original/current/edited values and the user's intent; only ask when that intent remains ambiguous. Missing or remapped fields require manual mapping repair, not guessed replacement.
5. After handling the relevant feedback, Codex acknowledges the exact record and rebuilds the preview. New previews clear only the copied snapshots confirmed as processed. Anything changed after copying remains, even a change back to the previous source wording. Run targeted visual QA after source edits.

```bash
# Feed the complete copied record to stdin; each command consumes the same exact record.
python3 ${SKILL_DIR}/scripts/edit_preview.py inspect <project_path> --stdin --json
python3 ${SKILL_DIR}/scripts/edit_preview.py apply <project_path> --stdin --dry-run --json
python3 ${SKILL_DIR}/scripts/edit_preview.py apply <project_path> --stdin --json
# Only after Codex has actually handled every comment in this record:
python3 ${SKILL_DIR}/scripts/edit_preview.py ack <project_path> --stdin --comments-processed --json
```

`inspect` is read-only and returns pending edits, page order, comments and conflicts. A changed project revision may still be compatible when the edited fields retain their original values; already-applied values are no-ops. `apply` writes direct text/notes/order edits and records a content-only acknowledgment. Comment-only and order-only records are supported. Repeating a processed record is safe; reusing its ID with different contents is rejected.

If Codex manually resolves or implements direct edits, acknowledge them with `ack --content-processed`; add `--comments-processed` only when all comments are handled too. If any comment remains unresolved, leave that category unacknowledged. Acknowledgment records processing status; it does not implement any edits. Never change a copied record's ID or baseline to bypass a conflict. Return to the original record after rebuilding a stale source manifest.

`--file <agent-side-copy>` and `--file -` are optional input conveniences, not user-facing workflows. Commands print JSON; invalid input exits 2, conflicts exit 3. Source writes may succeed even if the subsequent HTML rebuild fails: check `preview_warning`, report the saved state and rebuild separately.

## Clipboard format

```markdown
# PPT 修改清单

项目：AI实践交流会 [p123456789abc]
版本：v12｜修改记录：r81ec590a41380e29

## 03 Agent已经很强，公司为什么没有利润大涨？ [s3]

### 正文 [t1]
原：Agent已经很强，人为什么仍然很忙？
改：Agent已经很强，公司为什么没有利润大涨？

### 批注
> 补充成功新产品数量、利润、研发周期三个观察角度。
```

The header reference identifies the originating project; `v12` refers to an immutable text baseline, and `s3` / `t1` remain attached to slide/text identities after reordering. Short text uses original/new lines; multiline text and comments use quoted lines so Markdown headings, code fences, blank lines and trailing spaces stay literal. Do not manually rewrite or trim the copied record.

`备注修改` / `Notes changes` uses exact positional unified-diff hunks with one line of context. Reconstruct the entire note from its archived baseline, then use the normal original/current/edited comparison; never apply a fuzzy patch to the latest notes. `备注全文` / `Full notes` carries only the replacement Markdown. A section can name an older baseline, such as `[v8]`, when a browser draft began before the latest source update. For migrated browser-only originals without an archived match, use a readable original/new fallback rather than discarding the original or pretending it matches the latest source.

`review_markdown.py` converts this text to the existing processing format internally; users do not copy a second hidden JSON block. `edit_preview.py` still accepts previously copied schema 1/2 JSON. Its `--json` flag controls the CLI report, not the user's clipboard format.

## Source and persistence contract

Accepted text edits update mapped SVG text, affected main-content fields, and matching design-spec outline lines. Preserve unrelated slides, style attributes and chapter headings. Notes are edited as raw Markdown, not reconstructed from the parsed notes display. Applying notes updates the matching total-note section and individual note file. Do not use `# NN...` headings or the reserved `---` slide separator inside a note; use `***` for a Markdown rule.

Unsaved drafts and comments are local to the browser/profile and may be unavailable or cleared. Show an explicit warning if storage fails. Saving HTML persists text/notes independently of that storage; copying does not save files or send feedback automatically. Before final production, import saved HTML through the preview rebuild and obtain any remaining unsaved edits through “Copy all changes”.

`preview/review_index.json` preserves short-reference mappings; `preview/review_baselines/vN.json` keeps immutable text/notes snapshots, without duplicate SVG/media data. Preserve both when moving a project or rebuilding a preview; old copied records must remain resolvable. Missing or mismatched baselines stop automatic application with an actionable error. The local draft store retains per-field/comment sequence numbers and a snapshot for each copy. `preview/review_receipts.json` records processed categories for each immutable record ID; rebuilds embed these receipts in the manifest. Clear a local edit only when its sequence matches the processed copy. Rebase the original value of newer edits onto the updated source, retaining the user's latest text. Do not use a build timestamp or old-comment cleanup to discard content or feedback. Legacy comment-only drafts can be recovered as explicitly unassigned feedback with their original page key; verify identity before applying them after page reordering.

Source commits check the revision again under a project-local lock. Before-images and submitted source edits are kept in `preview/edit_history/`; write failures roll back already-written source files. Remove a stale `.edit.lock` after a crash only after checking that no writer remains active. Existing final exports are left untouched and marked stale via `preview/final_stale.json`; follow the normal finalizer/review-lock rules before regeneration. Do not overwrite accepted content using stale design specs or old generator scripts.

## Verification

After changing this feature, run source round-trip tests, clipboard/receipt tests, and the isolated browser test:

```bash
python3 -m unittest discover -s ${SKILL_DIR}/scripts -p test_saved_html.py
python3 -m unittest discover -s ${SKILL_DIR}/scripts -p test_slide_order.py
PPT_TEST_NODE_MODULES=<node_modules> node ${SKILL_DIR}/scripts/test_reorder_preview.cjs
PPT_TEST_NODE_MODULES=<node_modules> node ${SKILL_DIR}/scripts/test_save_preview.cjs
python3 -m unittest discover -s ${SKILL_DIR}/scripts -p test_preview_editing.py
python3 -m unittest discover -s ${SKILL_DIR}/scripts -p test_review_packets.py
python3 -m unittest discover -s ${SKILL_DIR}/scripts -p test_review_markdown.py
node ${SKILL_DIR}/scripts/test_editable_preview.cjs --python <python> --node-modules <node_modules>
```

The browser test uses temporary fixtures and a mocked clipboard, never the user's deck or clipboard. It covers default editing, lossless Markdown copying, full notes, combined copying, comment-only feedback, refresh recovery, undo, overflow, typing/navigation, manual-copy fallback, application/rebuild, receipt clearing and post-copy edits. The Markdown tests also cover distant note changes, repeated paragraphs, multiline content, insertions/deletions, old baselines, reordered pages, missing mappings, literal Markdown, and legacy JSON compatibility. Run existing preview tests and targeted `qa_preview_html.py` after actual slide revisions. The acceptance check is editing a visible sentence, note and comment, copying once, processing through Codex, rebuilding, and verifying that accepted edits survive while later browser edits remain pending.

The save browser test mocks only the OS picker/permission boundary and writes real temporary HTML files. It covers cancellation, denial, wrong/stale files, handle reuse, fresh-browser recovery, safe literal HTML in notes, edits during a save, comment-only copying and source regeneration. The installed browser API capability check is separate; tests do not grant OS permission on the user’s behalf.
