# Preview Navigation Below Slide Implementation Plan

> **Superseded on 2026-07-23.** The final implementation places Previous/Next on the right side of the top current-slide takeaway card. Do not execute this historical below-slide plan.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the review preview's top toolbar and place the Previous/Next controls immediately below the current slide.

**Architecture:** Keep `build_preview_html.py` as the single preview generator and change only its generated HTML/CSS/JavaScript contract. Protect the layout with direct string/DOM-order regression assertions, then document the invariant in `SKILL.md`.

**Tech Stack:** Python 3.10+, generated HTML/CSS/JavaScript, `unittest`, Node.js syntax validation, local browser inspection.

## Global Constraints

- The main review column order is takeaway card, slide viewer, bottom navigation row.
- Previous precedes Next, and the pair is right-aligned.
- The navigation row must not overlay or cover the slide.
- The duplicated current-slide title and review-scope sentence are removed from the main preview column.
- Existing button IDs, click behavior, keyboard navigation, comments, hash navigation, outline behavior, and final single-file HTML behavior remain unchanged.
- No sticky or overlay navigation is added.

---

### Task 1: Move review navigation below the slide

**Files:**
- Modify: `skills/ppt-master/scripts/test_build_preview_html.py`
- Modify: `skills/ppt-master/scripts/build_preview_html.py`
- Modify: `skills/ppt-master/SKILL.md`

**Interfaces:**
- Consumes: `build_html(title, entries, strings, project_key, review_build_id) -> str`.
- Produces: generated preview HTML containing `.summary-card`, `.viewer-shell`, then `.slide-navigation`, with `#prevBtn` before `#nextBtn`.

- [ ] **Step 1: Write the failing structural regression test**

Add assertions to `test_static_file_preview_supports_copy_review`:

```python
summary_index = html.index('<section class="summary-card">')
viewer_index = html.index('<div class="viewer-shell">')
navigation_index = html.index('<nav class="slide-navigation"')
prev_index = html.index('id="prevBtn"')
next_index = html.index('id="nextBtn"')

self.assertLess(summary_index, viewer_index)
self.assertLess(viewer_index, navigation_index)
self.assertLess(navigation_index, prev_index)
self.assertLess(prev_index, next_index)
self.assertNotIn('class="toolbar"', html)
self.assertNotIn('id="slideToolbarTitle"', html)
self.assertNotIn("toolbarTitle", html)
self.assertNotIn("推荐审稿范围：结构、结论、素材、备注。", html)
self.assertIn("justify-content: flex-end;", html)
```

Set the test fixture's `scope` string to `推荐审稿范围：结构、结论、素材、备注。` so the absence assertion is meaningful. Also assert the existing `prevBtn`/`nextBtn` event-listener strings remain present.

- [ ] **Step 2: Run the focused test to verify RED**

Run:

```bash
python3 -m unittest skills/ppt-master/scripts/test_build_preview_html.py -v
```

Expected: FAIL because `.slide-navigation` does not exist and the old toolbar is still present.

- [ ] **Step 3: Implement the minimal preview layout change**

In `build_preview_html.py`:

```html
<main class="main">
  <section class="summary-card">...</section>
  <div class="viewer-shell">...</div>
  <nav class="slide-navigation" aria-label="Slide navigation">
    <button class="nav-button" id="prevBtn">...</button>
    <button class="nav-button" id="nextBtn">...</button>
  </nav>
</main>
```

Update CSS:

```css
.main {
  grid-template-rows: auto 1fr auto;
}
.slide-navigation {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
```

Remove `.toolbar`, `.toolbar-title`, `.toolbar-note`, `.nav-buttons`, the `slideToolbarTitle` element, `toolbarTitle` JavaScript lookup, and `toolbarTitle.textContent` update. Do not change button IDs or handlers.

- [ ] **Step 4: Document the invariant in the skill**

In Step 6 and Notes of `SKILL.md`, state:

```markdown
- In `preview/index.html`, render the Previous/Next navigation row immediately below the current slide viewer. Do not render a top toolbar containing the current-slide title or review-scope guidance. Keep the controls outside the iframe and never overlay them on slide content.
```

- [ ] **Step 5: Run focused and full automated verification**

Run:

```bash
python3 -m unittest skills/ppt-master/scripts/test_build_preview_html.py -v
python3 -m unittest discover -s skills/ppt-master/scripts -p 'test_*.py' -v
python3 /Users/yemingjiang/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/ppt-master
git diff --check
```

Expected: all tests pass, skill validation reports `Skill is valid!`, and `git diff --check` is silent.

- [ ] **Step 6: Build and inspect a representative preview**

Create a disposable local fixture at `/tmp/ppt-master-preview-nav-fixture` with at least two SVG slides, then run:

```bash
python3 skills/ppt-master/scripts/build_preview_html.py /tmp/ppt-master-preview-nav-fixture --source output
```

Inspect the generated DOM and verify the navigation follows `.viewer-shell`. Open the result locally and verify:

- desktop: both buttons sit below the slide and align right;
- narrow viewport: both buttons remain below the slide without overlap;
- Previous, Next, ArrowLeft, and ArrowRight still navigate.

- [ ] **Step 7: Commit**

```bash
git add skills/ppt-master/scripts/test_build_preview_html.py \
  skills/ppt-master/scripts/build_preview_html.py \
  skills/ppt-master/SKILL.md
git commit -m "fix: move preview navigation below slide"
```
