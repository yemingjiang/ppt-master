# Slide Style

Read when defining or revising a project's visual style. Apply these principles through the existing template selection, Eight Confirmations, execution, and review steps; they add no approval checkpoint.

## Style and layout

Define reusable decisions in `design_spec.md` and carry them into `style_sheet.md`:

- **Stable across the deck**: color roles and category meanings, font families and weights, type scale, spacing rhythm, icon language, and any required branding.
- **Chosen per page**: composition, column count, title placement, diagrams, images, and content containers. Use the page's message and evidence to choose them.

A near-blank content page is a valid starting point. Alignment, hierarchy, and whitespace can provide a complete design. Cards, title bars, shadows, gradients, and glow are optional tools with a specific communicative purpose.

Keep General, Consulting, and Top Consulting as useful approaches. Structured reports can reuse grids and page families; speaking slides can vary composition more freely. Existing template packages remain usable. Preserve explicitly required template structures and brand elements; record which parts are fixed and which are flexible.

## Style priority and reuse

Use explicit user direction first. Ground reference/brand interpretation in the existing PPTX extraction rules, then record the agreed choices in the design spec. Once approved, that spec governs execution and every final format. Style changes during review must update the handoff files.

Reuse an established project or brand palette and typography when available. Free design permits tailored page composition within that identity; it does not require inventing new colors and fonts for every deck.

HTML and PowerPoint inherit the same confirmed style. For HTML, map its colors to the complete `background`, `surface`, `primary`, `on_primary`, `text`, `muted`, and `line` token set and record a theme name. Use `executive-red` only as a fallback when no style has been established. Confirm that the generated manifest, slide fragments, and controls follow the agreed theme before packaging; a format default must not recolor an approved deck.

## Color roles

Start with a small working palette: background/surface, text, primary, accent, and any needed status or data-category colors. Multiple roles can share one color. Keep neutral shades available without treating every shade as a new accent.

- Assign colors to purposes and reuse those meanings across pages and charts. The same business entity should retain its color.
- Use same-hue variations for related series; use distinct, consistently mapped colors when categories need differentiation. Add labels, markers, or patterns when color alone would carry meaning.
- Treat palette counts and the 60–30–10 distribution as composition aids. Neither a six-color deck palette nor a four-color page limit is an acceptance criterion; charts and brand systems may need justified exceptions.
- Check foreground/background pairs in the actual design. Light/dark mode and saturation alone do not establish legibility. Retain the existing text contrast target of at least 4.5:1, and visually check muted text and chart labels.

Record purposes in the color table and any cross-page semantic mappings under `### Style Rules` in section III. For exported PPTX, do not promise global theme recoloring solely because the specification uses semantic names; that requires actual theme-linked objects and verification.

## Typography and viewing context

Determine the viewing context with the existing audience/use-case confirmation: projected live talk, remote screen share, or self-paced reading. A consulting style may be used in any of these contexts.

Choose essential-text sizes for the intended viewing conditions before fitting content. For a 1280×720 canvas, 28–32px is a useful starting range for live presentation body text, while 18–24px can suit self-paced report reading. These are starting points, not universal minimums; adjust for viewing distance, font metrics, language, and canvas size. Record the selected baseline and supporting-text minimum in section IV.

When content is crowded, shorten it, split the page, simplify the graphic, or move detail into notes/appendices. Density alone is not a reason to shrink essential text. Important chart labels and comparison annotations must also pass the viewing check.

Use a small, intentional set of font families. One family with multiple weights is a good default; a complementary title family can serve a deliberate visual purpose. Default to a readable sans-serif for presentation body text while preserving appropriate brand and cultural choices.

- Plan Chinese, Latin, and fallback fonts together. Verify availability in the render/export environment; use installed fonts in SVG and preserve the existing prohibition on `@font-face`.
- Use monospace for code and other alignment-sensitive literal text. Handwritten fonts are optional for brief audience-facing annotations.
- Differentiate emphasis with weight, size, or color before adding another family. Prefer sentence case for ordinary English copy; reserve capitals for short labels, acronyms, or deliberate emphasis.
- Record line spacing and any deliberate character spacing under `### Typography Rules`. Check multi-line titles, quotes, mixed Chinese/Latin text, punctuation, and the final PowerPoint's actual font rendering. Use only weights the target environment can render reliably.

The type-scale table may keep 24px and 18px examples for compatibility. Fill `Current Project` for deliberate overrides; otherwise sizes follow the selected baseline column or the row's ratio. Do not copy the dense column into every style sheet.

## Page chrome

Choose a footer policy under section V's `### Page Structure`:

- **Live / keynote presentation**: no persistent footer is a useful default; place identity on the opening or closing page as appropriate.
- **Review / consulting report**: page numbers can support discussion and navigation. Add section navigation only when useful.
- **Required brand / compliance content**: retain the specified logo, confidentiality mark, or attribution in a restrained, readable form.

Do not infer a confidentiality requirement from a consulting preset. The main skill's provenance rule still applies: sources belong in notes and handoff artifacts unless visible citations are requested or required. A footer may be absent; reserve no empty footer band when it is unused. Review-UI numbering and navigation remain available independently of the slide surface.

## Review and handoff

Inspect representative rendered pages at normal size and at 50% of the authored canvas dimensions. At half size, check whether the key message, essential labels, and hierarchy remain readable. This is a quick screening technique, not proof of readability from an auditorium's back row.

Review a cover, a dense/chart page, and any changed or unusual layout. Check color semantics, font consistency, line spacing, contrast, and optional chrome along with the existing overflow/overlap checks. For native editable delivery, repeat the visual check on actual PowerPoint renders. Preserve the approved visual intent across SVG review, final HTML, and native PPTX.

## Design source

These project rules adapt selected ideas from [Build your slide template](https://martinfowler.com/articles/never-send-slides/build-your-slide-template.html), by Sumeet Gayathri Moghe, published on martinfowler.com on 14 October 2026. The article's near-blank template, restrained palette/type choices, and half-size check inform this guidance. Viewing ranges, schema fields, output mapping, and report exceptions above are ppt-master implementation choices. The author's personal layout and footer practices are not universal requirements.
