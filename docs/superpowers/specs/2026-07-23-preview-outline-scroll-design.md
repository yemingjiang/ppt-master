# Preview Outline Scroll Design

## Goal

Fix the review skeleton preview so the left outline can scroll independently and automatically follows the active slide during navigation.

## Root Cause

The current `.sidebar` uses `overflow: auto`, but the grid row grows to the full content height because `.app` only has `min-height: 100vh`. In a 23-slide preview at a 1600 × 900 viewport, the sidebar has:

- `clientHeight = 2205`
- `scrollHeight = 2205`
- `scrollTop = 0` after navigating from slide 1 to slide 19

Because the sidebar box is as tall as its contents, it never becomes a scroll container.

## Approved Interaction

### Desktop and Tablet

- Keep the sidebar title, metadata, and slide count visible.
- Make only the outline list (`.nav`) independently scrollable.
- When the active slide changes through outline clicks, previous/next buttons, keyboard navigation, or the initial URL hash, move the active outline item into the nearest visible position.
- Scroll only the outline list; do not move the document or the slide viewer.
- Avoid animated scrolling so rapid keyboard navigation remains deterministic.

### Mobile

- At widths up to 960px, keep the existing single-column document flow.
- Disable the fixed-height sidebar and independent outline scroll so the page does not create nested mobile scroll areas.
- Automatic outline following becomes a no-op when the outline has no overflow.

## Implementation

### CSS

- Convert `.sidebar` into a viewport-height flex column on layouts wider than 960px.
- Keep header elements at natural height.
- Give `.nav` `flex: 1`, `min-height: 0`, and `overflow-y: auto`.
- Add contained overscroll and a stable scrollbar gutter where supported.
- Reset sidebar and outline sizing/overflow in the existing mobile media query.

### JavaScript

- Cache the outline container.
- Add a focused helper that compares the active item bounds against the outline viewport.
- Adjust only `outline.scrollTop` when the active item is above or below the visible area.
- Call the helper from `selectSlide()` after the active class is updated.

## Tests

1. Add a regression test that verifies the generated preview contains the independent outline scroll CSS.
2. Verify the generated script contains the outline-follow helper and invokes it from slide selection.
3. Run the existing preview generator unit tests.
4. Rebuild the current 23-slide project and use a browser measurement test to confirm:
   - outline `scrollHeight > clientHeight`;
   - manual outline scrolling changes `scrollTop`;
   - navigating to slide 19 automatically increases `scrollTop`;
   - the active outline item is within the outline viewport.

## Scope

- Modify `skills/ppt-master/scripts/build_preview_html.py`.
- Modify `skills/ppt-master/scripts/test_build_preview_html.py`.
- Update the preview behavior description in `skills/ppt-master/SKILL.md`.
- Rebuild the current AI Lab review preview for end-to-end verification.
- Do not change slide content, comment storage, final HTML packaging, or presentation export behavior.
