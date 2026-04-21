# Technical Design

[English](./technical-design.md) | [中文](./zh/technical-design.md)

---

## Design Philosophy — AI as Your Designer, Not Your Finisher

The reviewed skeleton package and rebuilt PPTX are still **design deliverables**, not magic one-click perfection. Think of them like an architect's rendering plus a build-ready model: the AI handles visual direction, layout structure, and most of the assembly work, but the last-mile judgment still belongs to the human. The goal is to eliminate 90% of blank-page work, not to replace human taste in the final mile.

**A tool's ceiling is your ceiling.** PPT Master amplifies the skills you already have — if you have a strong sense of design and content, it helps you execute faster. If you don't know what a great presentation looks like, the tool won't know either. The output quality is ultimately a reflection of your own taste and judgment.

---

## System Architecture

```
User Input (PDF/DOCX/URL/Markdown)
    ↓
[Source Content Conversion] → source_to_md/pdf_to_md.py / doc_to_md.py / web_to_md.py
    ↓
[Create Project] → project_manager.py init <project_name> --format <format>
    ↓
[Template Option] A) Use existing template B) Free design
    ↓
[Need New Template?] → Use /create-template workflow separately
    ↓
[Strategist] - Eight Confirmations & Design Specifications
    ↓
[Image_Generator] (When AI generation is selected)
    ↓
[Skeleton Executor] - Review-first draft generation
    ├── SVG draft pages → svg_output/
    ├── main_content.md / design_spec.md / style_sheet.md / asset_manifest.md
    ├── Speaker notes → notes/total.md
    └── HTML review surface → preview/index.html
    ↓
[Human Review Loop] → review structure, takeaways, notes, and assets in preview/index.html
    ↓
[Native Editable Rebuild] → repo-local ppt-master-native-editable
    ↓
Output: final editable .pptx rebuilt with native PowerPoint text, shapes, tables, and media

Legacy compatibility branch (explicit request only):
    Skeleton draft / svg_output/
        ↓
    total_md_split.py → finalize_svg.py → svg_to_pptx.py
        ↓
    exports/<timestamp>.pptx + exports/<timestamp>_svg.pptx
```

---

## Technical Pipeline

**Default pipeline: AI generates a reviewable SVG-based skeleton first, then a separate native-editable rebuild produces the final PPTX.**

The full flow now breaks into four stages:

**Stage 1 — Content Understanding & Design Planning**
Source documents (PDF/DOCX/URL/Markdown) are converted to structured text. The Strategist role analyzes the content, plans the slide structure, and confirms the visual style, producing a complete design specification.

**Stage 2 — Review Skeleton Generation**
The Executor role generates each slide as an SVG draft plus the synchronized support files (`main_content.md`, `style_sheet.md`, `asset_manifest.md`, `notes/total.md`). The output of this stage is a **review package**, not a finished deck.

**Stage 3 — Human Review Loop**
The draft is reviewed through `preview/index.html`, where structure, takeaways, assets, and notes are adjusted before any final PowerPoint build is attempted.

**Stage 4 — Native Editable Rebuild**
Once the skeleton is approved, the downstream `ppt-master-native-editable` skill rebuilds the final `.pptx` with native PowerPoint objects. This is the preferred editable-delivery path.

**Legacy branch — Engineering Conversion**
`svg_to_pptx.py` still exists as a compatibility export path, but it is no longer the default for final editable delivery.

---

## Why SVG?

SVG still sits at the center of the drafting pipeline. The choice was made by elimination.

**Direct DrawingML generation** seems most direct — skip the intermediate format, have AI output PowerPoint's underlying XML. But DrawingML is extremely verbose; a simple rounded rectangle requires dozens of lines of nested XML. AI has far less training data for it than SVG, output is unreliable, and debugging is nearly impossible by eye.

**HTML/CSS** is one of the formats AI knows best. But HTML and PowerPoint have fundamentally different world views. HTML describes a *document* — headings, paragraphs, lists — where element positions are determined by content flow. PowerPoint describes a *canvas* — every element is an independent, absolutely positioned object with no flow and no context. This isn't just a layout calculation problem; it's a structural mismatch. Even if you solved the browser layout engine problem (what Chromium does in millions of lines of code), an HTML `<table>` still has no natural mapping to a set of independent shapes on a slide.

**WMF/EMF** (Windows Metafile) is Microsoft's own native vector graphics format and shares direct ancestry with DrawingML — the conversion loss would be minimal. But AI has essentially no training data for it, so this path is dead on arrival. Notably, even Microsoft's own format loses to SVG here.

**SVG as embedded images** is the simplest path — render each slide as an image and embed it. But this destroys editability entirely: shapes become pixels, text cannot be selected, colors cannot be changed. No different from a screenshot.

SVG wins because it shares the same world view as DrawingML: both are absolute-coordinate 2D vector graphics formats built around the same concepts:

| SVG | DrawingML |
|---|---|
| `<path d="...">` | `<a:custGeom>` |
| `<rect rx="...">` | `<a:prstGeom prst="roundRect">` |
| `<circle>` / `<ellipse>` | `<a:prstGeom prst="ellipse">` |
| `transform="translate/scale/rotate"` | `<a:xfrm>` |
| `linearGradient` / `radialGradient` | `<a:gradFill>` |
| `fill-opacity` / `stroke-opacity` | `<a:alpha>` |

The conversion is a translation between two dialects of the same idea — not a format mismatch.

SVG is also the only format that simultaneously satisfies every role in the drafting pipeline: **AI can reliably generate it, humans can preview and debug it in any browser, and scripts can precisely convert or reinterpret it**. That is why SVG remains the review-stage source of visual intent even though the preferred final editable delivery path is now a downstream native rebuild rather than direct conversion.
