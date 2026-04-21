---
name: ppt-master-native-editable
description: Use when a reviewed ppt-master skeleton package needs a final native editable .pptx rebuild with close visual fidelity, predictable manual editability, and PPT-native layout QA.
---

# PPT Master Native Editable

Use this skill after `ppt-master` has already completed the skeleton and review loop.

In normal user-facing operation, the user still invokes only `ppt-master`. This skill is the internal native-editable continuation point after the reviewed skeleton is locked.

This is the native editable rebuild phase for `ppt-master` projects. It takes the confirmed handoff package and produces the final editable `.pptx` with native PowerPoint text, shapes, tables, charts, media placement, and post-export QA.

## When to Use

Use this skill when all of the following are true:

- the project already has a reviewed `ppt-master` package
- `preview/index.html` reflects the approved page order, copy, and visual intent
- the user now wants the final editable `.pptx`

Do **not** use this skill for:

- early content exploration
- SVG skeleton review
- legacy `svg_to_pptx.py` compatibility export
- generic one-off PowerPoint edits outside the `ppt-master` workflow

## Required Inputs

The handoff package should already exist:

- `<project_path>/main_content.md`
- `<project_path>/design_spec.md`
- `<project_path>/style_sheet.md`
- `<project_path>/asset_manifest.md`
- `<project_path>/notes/`
- `<project_path>/preview/index.html`
- confirmed image / video / screenshot assets

Treat missing handoff files as a blocker. Go back to `ppt-master` first rather than improvising the final deck from partial state.

## Core Contract

- Build the final deck natively. Meaningful content should become editable PowerPoint objects, not full-slide screenshots.
- Treat `preview/index.html` as approved **structure and visual intent**, not as proof that native PPT text will fit identically.
- Use the installed `@oai/artifact-tool` runtime and a single local JS builder for construction, render previews, and export.
- Keep screenshots, photography, video covers, and other true evidence images as media; rebuild headings, body copy, cards, labels, tables, timelines, and recurring layout chrome natively.
- If the user wants editability, do **not** fall back to `svg_to_pptx.py` unless they explicitly accept a compatibility export.

## Build Rules

- Run builders from a writable local directory, not from managed runtime directories.
- Prefer one builder file that is patched and rerun through the iteration loop.
- Keep page numbers and footer chrome explicit when the reviewed design authored them explicitly.
- Do not rely on implicit slide-number placeholders unless the user explicitly asks for built-in PowerPoint numbering.
- After export, verify that no unintended empty placeholders remain, especially `sldNum` slide-number placeholders.

## Native Rebuild Workflow

1. Inspect the approved handoff package.
   Confirm that slide order, titles, takeaways, assets, and notes are stable.

2. Map reviewed pages into native modules.
   Identify which parts are:
   - editable text and shapes
   - native tables / charts
   - media-only plates

3. Build the deck in JS.
   Use native text boxes, cards, labels, tables, timelines, KPI modules, and page chrome.

4. Render PPT-native previews.
   Compare them against the approved `preview/index.html` intent.

5. Fix layout drift in the native builder, not in the approved skeleton, unless the handoff content itself is wrong.

6. Export `.pptx`, run post-export cleanup, and perform a final QA pass.

## QA Priorities

### 1. Wrap-sensitive blocks

Always inspect:

- KPI cards
- metric badges
- short right-side tags
- dense executive callouts
- paired title+note panels
- one-line conclusions that should ideally stay one or two lines

Typical failure modes:

- unnecessary extra wraps
- manual line breaks that no longer fit
- orphan punctuation or single-character last lines
- title/body overlap
- bottom lines hanging outside the intended visual grouping

### 2. Alignment-sensitive blocks

Always inspect:

- large-number + adjacent-title composites
- left-number/right-title comparison cards
- footer/page-number chrome

Typical failure modes:

- numerals visually sagging below adjacent titles
- baselines that look wrong even though text technically fits
- footer chrome drifting off the intended axis

### 3. Placeholder cleanup

Always inspect the exported deck for accidental placeholders:

- slide-number placeholders
- empty imported placeholder text boxes
- unwanted auto-generated footer artifacts

Use the repo helper when needed:

```bash
python3 skills/ppt-master/scripts/clean_pptx_placeholders.py <deck.pptx> --in-place
```

## Default Output Expectations

- final editable `.pptx`
- native preview renders used privately for QA
- speaker notes preserved
- no unintended placeholder text boxes
- no avoidable wrap/overlap drift relative to the approved review draft

## Relationship to Other Skills

- `ppt-master` owns source processing, skeleton generation, review loop, and handoff packaging.
- `ppt-master-native-editable` owns the final native editable rebuild.
- Generic `slides` / PowerPoint skill remains for non-`ppt-master` deck work and broad PowerPoint authoring tasks.

## Completion Criteria

Complete only when:

- the final `.pptx` is exported successfully
- meaningful content is editable
- PPT-native previews were checked against the approved review intent
- wrap-sensitive and alignment-sensitive modules were explicitly QA'd
- accidental placeholders were removed
- the final response links only the final `.pptx` artifact unless the user explicitly asks for support files
