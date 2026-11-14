# Karjimut — Official Site Style Reference
> Blueprint grid under a black moon — faint graph lines, white type, one indigo spark for autonomous AI agent memory.

**Theme:** dark

Source measurements are normalized; roles and recommendations are interpreted. Font summary lists are independent, not paired by position. HTML examples are reconstructions, not source components.

Karjimut (`sleep-mcp`) operates in a midnight command-center language: a near-black canvas structured by a faint blueprint grid, with white type and a single soft indigo accent. Surfaces stack from pure black to charcoal, each step subtle enough to feel like elevation through luminance rather than shadow. The system is compact and telemetry-dense — Inter carries every reading load, JetBrains Mono stamps MCP tool signatures, memory tiers, and categorical labels, and 8px radii keep containers crisp rather than soft. Color is rationed: most of the interface stays achromatic, with `#6798ff` appearing only as functional punctuation on icons, token-efficiency markers, confidence badges, and sleep-consolidation chart elements.

## Tokens — Colors

| Name | Value | Token | Role |
|------|-------|-------|------|
| Soft Indigo | `#6798ff` | `--color-soft-indigo` | Brand accent — iconography, token-savings stat markers, sleep-cycle telemetry series, link states; the single chromatic note in an otherwise achromatic system |
| Pure Black | `#000000` | `--color-pure-black` | Deepest surface — modal backdrops, terminal code wells, inline SVG fills |
| Carbon | `#0a0a0a` | `--color-carbon` | Page canvas — the primary background; near-black with no warmth |
| Graphite | `#141414` | `--color-graphite` | Card surface — one step above the canvas to delineate memory tier blocks and telemetry previews |
| Iron | `#1e1e1e` | `--color-iron` | Elevated surface and border — secondary cards, SQLite/FTS5 table rows, subtle dividers |
| Slate Edge | `#313131` | `--color-slate-edge` | Hairline borders on terminal mockups and nested elements — visible but recessive |
| Smoke | `#454545` | `--color-smoke` | Dark borders and separators for elevated surfaces and ghost buttons. Do not promote it to the primary CTA color |
| Mist | `#7c7c7c` | `--color-mist` | Disabled or low-emphasis button text and inactive log states |
| Ash | `#a7a7a7` | `--color-ash` | Secondary text — captions, token metadata, helper text, muted labels |
| Bone | `#ffffff` | `--color-bone` | Primary text, icons, filled CTA background, card surface inverts; the dominant light element in the dark system |

## Tokens — Typography

### Inter — Primary typeface for headings, body, navigation, and buttons. Used at 64px/56px for display headlines with tight tracking, 40px for section headings, 24px/20px for subheadings, 16px for body and nav, 14px for captions. Weight 400 is the reading default; 500–600 for labels and emphasis. Negative letter-spacing tightens at scale (–0.036em at 64px tapering to –0.012em at 20px) — the optical correction keeps large display type from feeling airy. · `--font-inter`
- **Substitute:** Inter or any neo-grotesque sans (Söhne, GT America)
- **Weights:** 400, 500, 600
- **Sizes:** 14, 16, 20, 24, 40, 56, 64
- **Line height:** 1.13–1.57
- **Letter spacing:** -2.3px at 64px, -2.0px at 56px, -0.84px at 40px, -0.6px at 24px, -0.5px at 20px, -0.25px at 16px
- **OpenType features:** `"liga"`
- **Role:** Primary typeface for headings, body, navigation, and buttons.

### JetBrains Mono — All-caps category labels, section eyebrows (e.g. "TWO-TIER ARCHITECTURE", "SLEEP CONSOLIDATION"), version tags (`v2.0.13`), MCP tool primitives (`baca_ktp_proyek`), `#tag-masalah` pills, and CLI install snippets (`pip install karjimut`). Wide tracking (+0.071em to +0.083em) gives the type a stamped, technical feel — it reads as protocol metadata, not copy. · `--font-jetbrains-mono`
- **Substitute:** JetBrains Mono or IBM Plex Mono
- **Weights:** 400
- **Sizes:** 12, 14
- **Line height:** 1.00, 1.40
- **Letter spacing:** +0.85px at 12px, +1.16px at 14px
- **OpenType features:** `"liga"`
- **Role:** All-caps category labels, section eyebrows, version/status tags, MCP tool names, and micro-text.

### Type Scale

| Role | Family | Weight | Size | Line Height | Letter Spacing | Token |
|------|--------|--------|------|-------------|----------------|-------|
| caption | — | — | 12px | 1.4 | 0.85px | `--text-caption` |
| body-sm | — | — | 14px | 1.57 | -0.25px | `--text-body-sm` |
| body | — | — | 16px | 1.5 | -0.25px | `--text-body` |
| heading-sm | — | — | 20px | 1.33 | -0.42px | `--text-heading-sm` |
| heading | — | — | 24px | 1.29 | -0.6px | `--text-heading` |
| heading-lg | — | — | 40px | 1.2 | -0.84px | `--text-heading-lg` |
| display-sm | — | — | 56px | 1.14 | -1.74px | `--text-display-sm` |
| display | — | — | 64px | 1.13 | -2.3px | `--text-display` |

## Tokens — Spacing & Shapes

**Base unit:** 8px
**Density:** compact

### Spacing Scale

| Name | Value | Token |
|------|-------|-------|
| 8 | 8px | `--spacing-8` |
| 16 | 16px | `--spacing-16` |
| 24 | 24px | `--spacing-24` |
| 32 | 32px | `--spacing-32` |
| 40 | 40px | `--spacing-40` |
| 64 | 64px | `--spacing-64` |
| 96 | 96px | `--spacing-96` |
| 200 | 200px | `--spacing-200` |

### Border Radius

| Element | Value |
|---------|-------|
| tags | 4px |
| cards | 8px |
| inputs | 8px |
| buttons | 8px |
| navPills | 9999px |

### Layout

- **Page max-width:** 1200px
- **Section gap:** 80px
- **Card padding:** 24px
- **Element gap:** 8px

## Surfaces

| Level | Name | Value | Purpose |
|-------|------|-------|---------|
| 0 | Canvas | `#0a0a0a` | Full-page background; the field on which all content sits |
| 1 | Card | `#141414` | Content blocks, memory telemetry previews, feature cards |
| 2 | Elevated | `#1e1e1e` | Hover states, code snippets, nested cards, SQLite/FTS5 table headers |
| 3 | Border | `#313131` | Hairline dividers, terminal outlines, field borders |
| 4 | Inverted | `#ffffff` | Filled CTA buttons, inverted text blocks |
