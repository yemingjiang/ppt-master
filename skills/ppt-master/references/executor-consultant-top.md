# Executor Consultant Top — Top-tier Consulting Style (MBB Level)

> Common guidelines: executor-base.md. Technical constraints: shared-standards.md.

---

## Role Definition

An MBB-level (McKinsey / Bain / BCG) top-tier consulting style SVG design executor. Suitable for strategic planning, board presentations, investment roadshows, C-suite decision support, and other **premium consulting** scenarios. Core characteristics: data-driven insights, pyramid-structured narrative, extreme simplicity. Output targets C-level decision-makers.

---

## SCQA Framework (Narrative Structure)

Every MBB-level presentation follows the SCQA narrative structure:

| Element | Purpose | Typical Pages |
|---------|---------|---------------|
| **S - Situation** | Establish shared context | Cover / Pages 1-2 |
| **C - Complication** | Introduce the problem / tension | Pages 2-3 |
| **Q - Question** | The implicit or explicit question to solve | Transition page |
| **A - Answer** | Core solution | All body pages |

**Page sequencing**: Cover embodies S+C → Executive Summary answers Q → Chapters develop A → Closing revisits S

**Title writing**:

| SCQA Element | Weak Title | MBB-level Title |
|-------------|------------|-----------------|
| S | "Industry Background" | "Digital penetration surpasses 60%, industry enters deep waters" |
| C | "Challenges Faced" | "Yet three structural contradictions constrain scaled deployment" |
| Q | "Strategic Question" | "How to move from pilot to full deployment within 18 months?" |
| A | "Solution" | "Three-phase path: Focus, Expand, Scale" |

---

## Data Contextualization (Never Present Data in Isolation)

> **Golden Rule**: Never display a single data point in isolation. Every number needs context.

| Method | Pattern | Visual Implementation |
|--------|---------|----------------------|
| **Time comparison** | "From X to Y" | Line chart + arrow annotating magnitude of change |
| **Benchmark** | "X vs industry average Y" | Bar chart with gray dashed baseline |
| **Competitive comparison** | "Us X vs Competitor Y" | Side-by-side bar chart, highlight own data |
| **Target gap** | "Actual X / Target Y" | Progress bar + gap annotation |
| **Ranking** | "Ranked #N of M" | Horizontal bar chart + highlight marker |

**Data annotation three essentials**: Every data visualization must include (1) The value itself (large bold font) (2) Comparison reference (baseline / prior period / competitor) (3) Meaning interpretation ("So what?")

```xml
<text x="640" y="280" text-anchor="middle" font-size="64" font-weight="bold" fill="#1E293B">97.3%</text>
<text x="640" y="330" text-anchor="middle" font-size="24" fill="#64748B">Industry avg 82% | Competitor A 89%</text>
<text x="640" y="375" text-anchor="middle" font-size="24" fill="#047857">Leading industry by 15.3 percentage points</text>
```

This is an illustrative composition; scale and reflow it to the confirmed project typography. Essential comparison/meaning labels must remain readable in the intended viewing conditions.

---

## Pyramid Principle (Conclusion First)

> Executives don't care about your *process* — they care about *results*.

```
         ┌─────────────────┐
         │  Core Conclusion │   ← Page title / Takeaway
         └────────┬────────┘
      ┌───────────┼───────────┐
  ┌───┴───┐  ┌───┴───┐  ┌───┴───┐
  │ Arg 1 │  │ Arg 2 │  │ Arg 3 │   ← Key supporting points
  └───────┘  └───────┘  └───────┘
```

| Level | Position | Font Size |
|-------|----------|-----------|
| Core conclusion | Assertion headline / optional Takeaway Box | Project title/emphasis scale, bold |
| Arguments | Content area body | Confirmed body baseline |
| Supporting data | Charts / cards | Project label/annotation scale and minimum |

**Contrast**: Title "Market Research Results" (wrong) → "Metaverse needs 5-10 years to reach scale" (right); Body "We researched... and found..." (wrong) → "Three arguments: (1)... (2)... (3)..." (right)

---

## MBB-level Layout Patterns

### Content Page Structure Reference (1280x720)

```
┌──────────────────────────────────┐
│ Optional brand bar              │
├──────────────────────────────────┤
│ Assertion headline              │
├──────────────────────────────────┤
│ Optional takeaway              │  ← Useful when it adds meaning beyond the headline
├──────────────────────────────────┤
│ Content area                   │  ← Charts / data / analysis
├──────────────────────────────────┤
│ Optional footer                │  ← Confirmed numbering / brand / compliance policy
└──────────────────────────────────┘
```

Allocate space around the confirmed type scale; a near-blank canvas or another composition is also valid. Use `slide-style.md` for viewing context and footer policy. Keep sources in notes/handoff files unless visible attribution is requested or required. Confidentiality marks require an actual requirement.

### Strategic Roadmap

Three phases laid out horizontally, `<rect rx="8">` + title + action list, `<polygon>` arrows connecting:

```
Focus Core (0-6mo)  ──>  Expand Capability (6-12mo)  ──>  Scale Up (12-18mo)
x=40,w=380              x=450,w=380                     x=860,w=380
```

### Benchmarking Matrix

Horizontal table; own row highlighted in theme color, others in gray. Leading indicators marked green, lagging marked red. Use `<circle>` or `<rect>` to build score points.

### Waterfall Chart (Change Attribution)

Start → increase/decrease factors → End. Positive factors green bars, negative factors red bars, start/end points dark bars, cumulative line as dashed connector.

---

## Strategic Use of Color

MBB-level color usage is extremely restrained — color serves information:

| Purpose | Method |
|---------|--------|
| **Focus** | Target data in theme color, everything else gray |
| **Reduce cognitive load** | Same series differentiated by opacity (`fill-opacity` 1.0/0.6/0.3) |
| **Semantics** | Green = positive, Red = negative, Gray = baseline |
| **Branding** | Confirmed brand palette/type; optional bars or lines when useful |

**Color guidance**: Prefer a restrained palette and deliberate accent use. Same-hue variations suit related series; distinct categories may need distinct, consistently mapped colors and labels. Light backgrounds are a common report choice, while the approved project theme governs the actual background. Color counts are composition aids, not hard limits.

---

## Chart vs Table Selection Matrix

| Scenario | Recommended Form | Reason |
|----------|-----------------|--------|
| Comparing 2-7 categories | **Bar chart** | Visual comparison is intuitive |
| Time trends | **Line chart** | Time series clarity |
| Precise values / large rankings | **Table** | 50 data points in a bar chart would be chaotic |
| Proportional composition | **Donut chart** | More modern than pie charts |
| Two-dimensional positioning | **2x2 matrix** | Strategic quadrant analysis |
| Change attribution | **Waterfall chart** | Factor decomposition |

---

## Speaker Notes Style

### Narrative Tone

Targeting **executives / decision-makers**. Pyramid structure — every sentence carries information. Composed, authoritative, and insightful tone.

### Stage Direction Markers

| Marker | Purpose | Example |
|--------|---------|---------|
| `[Pause]` | Silence after key insight, let executives absorb | "This means we are missing a billion-dollar market. [Pause]" |
| `[Scan Room]` | Observe decision-makers' reactions, decide whether to elaborate | "[Scan Room] If there are questions, I can elaborate." |
| `[Data]` | Conversational number delivery | "[Data] 63% → nearly two-thirds" |
| `[Benchmark]` | Emphasize comparison baseline | "[Benchmark] Compared to the industry average of 12%, our 23% is nearly double" |
| `[Transition]` | Bridge from previous page, at start of each page's text | "[Transition] Building on the strategic framework, let's drill into the implementation path." |

### Notes Writing Guidelines

- **Pyramid structure**: Conclusion → Arguments → Details
- **Data contextualization**: Every number has a comparison reference
- **Executive language**: "The strategic implication is...", "The core insight is..."
- **Flex mechanism**: Annotate "content that can be skipped if time is tight" for flexible duration
- **Key points structure**: `Key points: (1) Core insight (2) Data support (3) Strategic implication`

### Notes Example

```markdown
# 03_strategic_path

[Transition] Having clarified the problem and the opportunity, now comes the most critical part — our response path.

We recommend a three-phase strategy. [Pause]

Phase one: Focus. Over the next six months, concentrate resources on conquering the Eastern China market.
[Data] Eastern China contributes nearly two-thirds of industry growth, [Benchmark] yet our penetration rate is only half of Competitor A's. [Pause]

Phase two: Expand. Use Eastern China as a template, replicate to Southern and Northern China.
Phase three: Scale. Leverage a digital platform for nationwide coverage.

[Scan Room] The resource allocation for phase one is in the appendix — would you like me to walk through it now?

Key points: (1) Focus-Expand-Scale three-phase approach (2) Data-backed Eastern China priority (3) 18-month full deployment
Duration: 3 minutes
Flex: [If time is tight, skip phase two and three details and go straight to financial impact]
```

---

## MBB-level Quality Checklist Supplement

### Content Level

- [ ] **SCQA complete**: Overall follows Situation-Complication-Question-Answer structure
- [ ] **Data contextualized**: Every data point has a comparison reference
- [ ] **Conclusion first**: Assertion headlines or optional takeaway boxes communicate the conclusion
- [ ] **MECE principle**: Categorized analysis is mutually exclusive and collectively exhaustive

### Visual Level

- [ ] **Color with intent**: Colors serve information delivery
- [ ] **Ample whitespace**: Not crowded; information can "breathe"
- [ ] **Visual hierarchy**: Conclusion > Arguments > Details, differentiated by font size/weight
- [ ] **Style consistency**: Confirmed palette, typography, and any required brand/footer elements remain consistent

### Notes Level

- [ ] **Pyramid structure**: Every page is conclusion-first
- [ ] **Stage markers complete**: [Pause] and [Scan Room] at key positions
- [ ] **Flex content annotated**: Supports flexible duration
