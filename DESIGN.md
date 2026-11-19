---
name: TRACE
description: Temporal Retrieval with Attributed Claim Evidence; a dark circuit board where signals run along traces to the claim they support.
colors:
  board: "#14040e"
  board-2: "#1c0614"
  trace: "#4a1239"
  trace-hi: "#7a1f5e"
  magenta: "#ff3da5"
  magenta-wash: "rgba(255, 61, 165, 0.14)"
  magenta-edge: "rgba(255, 61, 165, 0.55)"
  magenta-pale: "#ffb4dc"
  chip-deep: "#3a0b2a"
  chip-dark: "#1a0613"
  ground: "#0b0f12"
  well: "rgba(8, 11, 14, 0.55)"
  glass: "rgba(13, 18, 22, 0.66)"
  glass-2: "rgba(22, 30, 36, 0.62)"
  veil: "rgba(255, 255, 255, 0.04)"
  line: "rgba(255, 255, 255, 0.09)"
  line-2: "rgba(255, 255, 255, 0.18)"
  shade: "rgba(0, 0, 0, 0.55)"
  text: "#f2f4f6"
  text-2: "#a9b2ba"
  text-3: "#76818b"
  line-number: "#4b5660"
  white: "#ffffff"
  disabled: "#39424a"
  blue: "#2f5bff"
  blue-hover: "#1f47e6"
  blue-wash: "rgba(47, 91, 255, 0.22)"
  blue-pale: "#c9d6ff"
  mint: "#5fe3b3"
  mint-wash: "rgba(95, 227, 179, 0.13)"
  coral: "#ff6b4a"
  coral-wash: "rgba(255, 107, 74, 0.14)"
  coral-pale: "#ffd0c4"
  json-key: "#f39bd2"
  json-number: "#ffc46b"
  json-string: "#cbd5df"
typography:
  display-intro:
    fontFamily: "League Gothic, Arial Narrow, sans-serif"
    fontSize: "clamp(6rem, 21vw, 17rem)"
    fontWeight: 400
    lineHeight: 0.82
    letterSpacing: "0.04em"
  display:
    fontFamily: "League Gothic, Arial Narrow, sans-serif"
    fontSize: "clamp(3.4rem, 7.2vw, 6.6rem)"
    fontWeight: 400
    lineHeight: 0.9
    letterSpacing: "0.01em"
  display-phone:
    fontFamily: "League Gothic, Arial Narrow, sans-serif"
    fontSize: "clamp(3rem, 15vw, 4.4rem)"
    fontWeight: 400
    lineHeight: 0.9
    letterSpacing: "0.01em"
  section-title:
    fontFamily: "League Gothic, Arial Narrow, sans-serif"
    fontSize: "2.2rem"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0.03em"
  numeral:
    fontFamily: "League Gothic, Arial Narrow, sans-serif"
    fontSize: "1.8rem"
    fontWeight: 400
    lineHeight: 1
  brand:
    fontFamily: "League Gothic, Arial Narrow, sans-serif"
    fontSize: "1.6rem"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0.06em"
  panel-title:
    fontFamily: "League Gothic, Arial Narrow, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0.04em"
  date-value:
    fontFamily: "League Gothic, Arial Narrow, sans-serif"
    fontSize: "1.35rem"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0.04em"
  answer:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "1.22rem"
    fontWeight: 500
    lineHeight: 1.45
  title:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "1.15rem"
    fontWeight: 600
    lineHeight: 1.2
  lead:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "1.02rem"
    fontWeight: 500
    letterSpacing: "0.01em"
  body:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 400
    lineHeight: 1.55
    fontFeature: "'tnum' 1"
  body-sm:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "0.88rem"
    fontWeight: 400
    lineHeight: 1.55
  small:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "0.82rem"
    fontWeight: 400
    lineHeight: 1.4
  label:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.1em"
  label-sm:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "0.72rem"
    fontWeight: 600
    letterSpacing: "0.12em"
  data-head:
    fontFamily: "JetBrains Mono, ui-monospace, Consolas, monospace"
    fontSize: "0.78rem"
    fontWeight: 500
    lineHeight: 1.2
  json:
    fontFamily: "JetBrains Mono, ui-monospace, Consolas, monospace"
    fontSize: "0.78rem"
    fontWeight: 400
    lineHeight: 1.55
  document:
    fontFamily: "JetBrains Mono, ui-monospace, Consolas, monospace"
    fontSize: "0.82rem"
    fontWeight: 400
    lineHeight: 1.65
rounded:
  node: "2px"
  mark: "4px"
  tag: "5px"
  frame: "6px"
  control: "8px"
  field: "10px"
  panel: "12px"
  glass: "14px"
  pill: "999px"
spacing:
  frame-x: "3rem"
  frame-x-md: "1.8rem"
  frame-x-sm: "1rem"
  frame-y: "2.2rem"
  section: "2.2rem"
  section-lg: "2.6rem"
  gap: "1rem"
  cell: "1rem 1.1rem"
  panel: "1.1rem 1.3rem 1.3rem"
  glass-section: "1.6rem"
components:
  button-primary:
    backgroundColor: "{colors.blue}"
    textColor: "{colors.white}"
    rounded: "{rounded.pill}"
    height: "2.8rem"
    padding: "0 1.4rem"
  button-primary-hover:
    backgroundColor: "{colors.blue-hover}"
  button-primary-busy:
    backgroundColor: "{colors.disabled}"
  button-small:
    backgroundColor: "{colors.blue}"
    textColor: "{colors.white}"
    rounded: "{rounded.pill}"
    height: "2.3rem"
    padding: "0 1.1rem"
  glass-section:
    backgroundColor: "{colors.glass}"
    rounded: "{rounded.glass}"
    padding: "{spacing.glass-section}"
  panel:
    backgroundColor: "{colors.glass-2}"
    rounded: "{rounded.panel}"
    padding: "{spacing.panel}"
  input:
    backgroundColor: "{colors.veil}"
    textColor: "{colors.text}"
    rounded: "{rounded.field}"
    height: "2.9rem"
    padding: "0 1rem"
  checkbox-checked:
    backgroundColor: "{colors.magenta}"
    rounded: "{rounded.mark}"
    size: "1.05rem"
  data-head:
    textColor: "{colors.text-2}"
    typography: "{typography.data-head}"
  date-asked-tag:
    backgroundColor: "{colors.magenta-wash}"
    textColor: "{colors.magenta}"
    rounded: "{rounded.tag}"
    typography: "{typography.data-head}"
  asked-band:
    backgroundColor: "{colors.magenta-wash}"
    textColor: "{colors.text}"
    rounded: "{rounded.field}"
    padding: "0.75rem 1rem"
  as-of-chip:
    backgroundColor: "{colors.chip-deep}"
    textColor: "{colors.white}"
    rounded: "{rounded.panel}"
    typography: "{typography.date-value}"
  citation-id:
    backgroundColor: "{colors.blue-wash}"
    textColor: "{colors.blue-pale}"
    rounded: "{rounded.mark}"
    padding: "0 0.4em"
  citation-id-stale:
    backgroundColor: "{colors.coral-wash}"
    textColor: "{colors.coral-pale}"
    rounded: "{rounded.mark}"
    padding: "0 0.4em"
  cited-by-ok:
    backgroundColor: "{colors.mint-wash}"
    textColor: "{colors.mint}"
    rounded: "{rounded.tag}"
    padding: "0.1rem 0.45rem"
  cited-by-bad:
    backgroundColor: "{colors.coral-wash}"
    textColor: "{colors.coral}"
    rounded: "{rounded.tag}"
    padding: "0.1rem 0.45rem"
  verdict-call-ok:
    textColor: "{colors.mint}"
  verdict-call-bad:
    textColor: "{colors.coral}"
  verdict-call-na:
    textColor: "{colors.text-2}"
  document-line-hit:
    backgroundColor: "{colors.magenta-wash}"
    textColor: "{colors.text}"
    typography: "{typography.document}"
  log-date-asked:
    backgroundColor: "{colors.magenta-wash}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
---

# Design System: TRACE

## Overview

**Creative North Star: "The Lit Trace"**

TRACE is drawn as a circuit board, and the name is literal: magenta signals travel along dim plum traces to the claim they support. A deep plum board fills the window; the app sits on it as one near-black slate frame, and inside the frame the content floats on translucent glass. The world is pinned to the user's reference video (dark board, glowing magenta signal, tall white condensed capitals) and to a dataset-table screenshot for the claims.

Light is the only ornament, and light means signal. The magenta glow lives where a signal is: the pulses running along the backdrop traces, the "As of" chip in the hero, the emblem's hot node, the date asked. Everything else is quiet slate, hairline borders and three type voices: League Gothic capitals to announce, Archivo to explain, JetBrains Mono for anything that is data (column heads, JSON scores, documents, commit ids, dates in tags).

Color is semantic, not decorative. Mint means "valid on the date asked", coral means "not valid on that date", magenta means "the date asked" and the brand, and electric blue means "you can act here". The page refuses light SaaS cards and chat transcripts; claims are a dataset, and the verdict and evidence open in place under the row.

**Key Characteristics:**
- A plum circuit board behind a near-black slate frame (6px corners), glass sections and panels inside it.
- Zero-offset magenta glows on signal points only; traveling pulses on the backdrop traces and the chip traces.
- Venetian-blind stripe masks (6px period) on display type in motion; striped pins on the chip.
- League Gothic for display capitals, Archivo for UI, JetBrains Mono for data.
- Four meaning colors: mint valid, coral not valid, magenta the date asked, blue action.
- Minimal hover: a border brightens and a panel lifts 2px.

## Colors

A dark plum-and-slate palette lit by one neon magenta, with mint, coral and electric blue each held to one meaning.

### Primary
- **Signal Magenta** (magenta): the brand and the date asked. Backdrop and chip pulses, the emblem and brand hot node, the TRACE initials in the full form, the "as of" date tag in each row, the asked band, the date-asked row in the history, highlighted document lines (with a 2px inset left bar), the counter bar, the How-it-works numerals, checked checkboxes, focus outlines, caret, selection, link hover underlines and the "Why?" chevron.
- **Magenta Wash** (magenta-wash) and **Magenta Edge** (magenta-edge): the translucent fill and border of every magenta-marked surface (date tag, asked band, open row, selected source, date-asked row, document hit); the edge also rims the chip.
- **Magenta Pale** (magenta-pale): small uppercase keys on magenta surfaces ("As of", "Date asked", the chip's labels).
- **Chip Deep / Chip Dark** (chip-deep, chip-dark): the hero chip's 160° fill, the one place the board's plum comes forward.

### Secondary
- **Action Blue** (blue): the "Ask a question" and "Ask" pill buttons. **Action Blue Hover** (blue-hover) is darker, not lighter, so white text keeps AA contrast. **Busy** (disabled) replaces it while a question is in flight.

### Tertiary
- **Valid Mint** (mint, mint-wash): "valid on the date asked". Valid verdict lines and icons, the "time-aware" role tag, valid cited-by tags and status words, `true` in the JSON, valid commit nodes.
- **Stale Coral** (coral, coral-wash, coral-pale): "not valid on the date asked". The † verdict line and icon, stale cited-by tags and status words ("Not yet written", "Superseded"), `false` in the JSON, stale commit nodes, form errors. Coral Pale is the text tone inside coral-washed chips (stale citation ids, the stale period in the asked band).

### Neutral
- **Board / Board 2** (board, board-2): the window ground, a radial glow from Board 2 at the center to Board at the edges.
- **Trace / Trace Hi** (trace, trace-hi): the backdrop traces (every fifth trace and the pad rings in Trace Hi), the chip traces, the history log's vertical line.
- **Ground** (ground): the slate inside the frame and intro panel (at 0.9–0.94 opacity), the skip-link text, unlit log nodes.
- **Glass / Glass 2** (glass, glass-2): glass sections (claims, ask, how-it-works cards) and verdict panels; **Well** (well) under an opened row's detail; **Veil** (veil) on fields, the open button and the current log row.
- **Line / Line 2** (line, line-2): every 1px hairline; Line 2 is the hover and emphasis state.
- **Text / Text 2 / Text 3** (text, text-2, text-3): primary text, secondary text and labels, muted meta. **Line Number** (line-number) is the document gutter only.
- **Shade** (shade): the frame's and intro panel's neutral drop shadow.
- **JSON tones** (json-key, json-number, json-string): orchid keys, amber numbers and claim scores, cool grey strings; nulls and comments in Text 3 italic.

### Named Rules
**The Four Meanings Rule.** Mint is valid on the date asked, coral is not valid on the date asked, magenta is the date asked (and the brand), blue is an action. A color never borrows another's meaning; coral is never decoration and mint is never a success toast.

**The Blue Is for Action Rule.** Electric blue fills things you press: the pill buttons. It never marks state or validity. (Citation ids and the "Your question" tag still carry blue in the build; see Components.)

**The Dagger Rule.** Coral never travels alone: every not-valid mark pairs it with a † or words ("Cites a version not valid on…", "Not yet written", "Superseded").

## Typography

**Display Font:** League Gothic (with Arial Narrow, sans-serif), 400, always uppercase
**Body Font:** Archivo (with Arial, sans-serif), variable weight 400–800
**Label/Mono Font:** JetBrains Mono (with ui-monospace, Consolas) for data

**Character:** Tall condensed capitals announce, like the title cards in the reference video; a plain grotesque explains; mono marks anything that is data, so a reader can tell at a glance what is prose and what is a record.

### Hierarchy
- **Display intro** (League Gothic, clamp(6rem, 21vw, 17rem), 0.82): the TRACE word in the intro only.
- **Display** (League Gothic, clamp(3.4rem, 7.2vw, 6.6rem), 0.9, uppercase, 11ch measure, balanced): the rotating hero headline; **Display phone** (clamp(3rem, 15vw, 4.4rem)) at ≤760px.
- **Section title** (League Gothic, 2.2rem): "Ask your own question", "How it works". **Numeral** (1.8rem, magenta): the 01/02/03 steps. **Brand** (1.6rem, 0.06em): the top-bar wordmark. **Panel title** (1.5rem, uppercase): TRACE / Plain RAG. **Date value** (1.35rem): the date in the asked band; the chip date uses clamp(1.1rem, 1.8vw, 1.6rem).
- **Answer** (Archivo 500, 1.22rem / 1.45, pretty wrap): the answer sentence in each verdict panel; muted declines step to 1.05rem in Text 3.
- **Title** (Archivo 600, 1.15rem): the "TRACE › Claims" crumbs.
- **Lead** (Archivo 500, 1.02rem): the full-form line, initials in magenta 800.
- **Body** (Archivo 400, 0.95rem / 1.55): page text, fields, verdict lines (600). **Body small** (0.88rem): table answers, options, loading text. **Small** (0.82rem; 0.8rem for hints and notes): notes, hints, meta, small buttons.
- **Label** (Archivo 700, 0.78rem, 0.1em, uppercase): role tags beside panel titles, keys on magenta surfaces (0.7rem in the asked band). **Label small** (600, 0.72rem, 0.12em, uppercase): the vertical side rail. The intro full form is 600 clamp(0.8rem, 1.4vw, 1.05rem) at 0.16em.
- **Data head** (JetBrains Mono 500, 0.78rem, Text 2): column heads written as dataset keys ("question · as of", "trace_answer", "eval_scores", "trace_claim_check"), field labels, row date tags; 0.72rem in the claim-check table, 0.7rem as phone card keys.
- **JSON** (JetBrains Mono 400, 0.78rem / 1.55): the eval_scores cell. **Document** (JetBrains Mono 400, 0.82rem / 1.65): the line-numbered section text.

### Named Rules
**The Three Voices Rule.** League Gothic announces, Archivo explains, JetBrains Mono records. Prose never goes mono; data (keys, dates in tags, JSON, commit ids, file paths, documents) never goes Archivo.

**The Dataset Key Rule.** Table heads and field labels read like a dataset's keys: mono, lowercase or snake_case, Text 2. Uppercase tracked Archivo is reserved for tags and keys beside a value, never stacked above a heading.

## Layout

The window is the board; the app is one slate frame, 86rem max, inset 2.2rem from the top and centered, padded 0 3rem 2.5rem. Inside it, top to bottom:

1. **Top bar:** wordmark left; section links (Claims, Ask, How it works, GitHub) and a small blue pill right; closed by a 1px Line.
2. **Hero:** two columns (1.05fr | 1fr), min(78vh, 46rem) tall: the rotating headline, full form, description (34rem) and the "01 —— 03" counter left; the chip on its traces with the rotating ring badge right; a vertical side rail of corpus facts at the right edge.
3. **Claims dataset:** a glass section with crumbs and a note, then a hairline-bordered table: question · as of | trace_answer | plain_rag_answer | eval_scores (1.05fr | 1.2fr | 1.2fr | 1.05fr) and a 3.4rem open column, cells padded 1rem 1.1rem with hairline column rules. The opened row's detail is inserted directly under it.
4. **Detail:** the asked band, two verdict panels (1fr 1fr, 1rem gap), "Why?", then the evidence in three columns (16rem cited versions and claim check | document | 16rem history, 1.6rem gap).
5. **Ask:** a glass section; question (1fr) | as of (11rem) | Ask (9rem), checkboxes beneath.
6. **How it works:** three glass cards (1rem gap). **Footer:** 1px Line, Small text in Text 3.

Responsive behavior:
- **≤1080px:** frame margin 1.2rem, padding 0 1.8rem; the hero stacks with the art centered at 30rem max; the side rail hides; the table drops the eval_scores column (four columns); the evidence keeps 15rem sources beside the document and drops the history to full width.
- **≤760px:** the frame goes full-bleed with no side borders, padded 1rem; section links hide; each row becomes its own bordered card (12px) with the question and open button on top and mono keys above the answers and scores; panels, evidence, ask and how-it-works go to one column; the asked band also states the question.

## Elevation & Depth

Depth comes from translucency and light, not from stacked shadows. Three planes: the lit board, the slate frame on it (one soft neutral shadow), and glass inside the frame (blur, no shadow). Colored light is a signal, emitted from a point with no offset.

### Shadow Vocabulary
- **Frame lift** (`box-shadow: 0 30px 80px rgba(0,0,0,0.55)`; 0.6 on the intro panel): the only neutral shadow, separating the frame from the board.
- **Chip glow** (`0 0 0 1px rgba(255,61,165,0.15), 0 0 32px rgba(255,61,165,0.45), inset 0 0 18px rgba(255,61,165,0.25)`, breathing to 46px / 0.6 over 3.4s): the hero chip.
- **Signal glow** (`filter: drop-shadow(0 0 3px #ff3da5)`, 4px on chip traces, 6px on the emblem node; `text-shadow: 0 0 12px rgba(255,61,165,0.9)` on the chip date): pulses and signal points.
- **Node glow** (`box-shadow: 0 0 8px` in mint or coral; `0 0 10px` magenta on the date-asked node): commit nodes in the history.
- **Hit bar** (`box-shadow: inset 2px 0 0 #ff3da5`): highlighted document lines.
- **Button hover** (`0 8px 24px rgba(47,91,255,0.35)` with a 1px lift): the blue pill.

### Glass
`background: rgba(13,18,22,0.66); border: 1px solid rgba(255,255,255,0.09); backdrop-filter: blur(14px) saturate(125%)` on glass sections; verdict panels use Glass 2 with the same hairline.

### Named Rules
**The Zero-Offset Glow Rule.** Glows have no offset: they radiate from a signal point (a pulse, the chip, a hot node, a commit node) in that point's meaning color. Glow is how the board says "signal here"; it is never put on prose, panels or headings.

**The Minimal Hover Rule.** On glass, hover changes two things only: the border brightens from Line to Line 2 and the card lifts 2px (200ms, ease-out). No scale, no glow, no color fill.

## Shapes

A soft-cornered scale that tightens as things get smaller: 14px glass sections, 12px verdict panels, the chip and phone row cards, 10px the table, fields, sources, document and asked band, 8px the open button and log rows, 6px the frame and intro panel, 5px tags, 4px citation ids, inline code, checkboxes and the focus ring, 2px the date-asked node (square among round nodes). Buttons and the skip-intro control are full pills (999px). Commit nodes and pad rings are circles.

The board's geometry is orthogonal-and-45°: traces run on a 20px grid and turn only by 45°, ending in a 3.2px pad ring. The hero chip carries two rows of pins as a repeating stripe (3px pin, 6px gap) above and below.

### Named Rules
**The Six-Pixel Stripe Rule.** Stripes are a mask, not a pattern fill: repeating-linear-gradient bands on a 6px period that thin out or thicken to move display type (the headline morph, the intro outline reveal), and fixed 3px-on-9px stripes as the chip's pins. Nowhere else.

## Components

### Buttons
- **Shape:** full pill (999px), 2.8rem tall, padding 0 1.4rem; small 2.3rem with 0.82rem text; in the ask form 2.9rem and full width.
- **Primary:** Action Blue, white Archivo 700 0.9rem, 0.02em tracking.
- **Hover / Focus:** Action Blue Hover, 1px lift and the blue hover shadow over 160ms; focus is a 2px magenta outline at 3px offset. Busy: Busy grey, no lift, progress cursor, label "Asking…".
- **Skip intro:** a veiled pill (rgba white 0.05, hairline), Text 2, bottom right.

### Inputs / Fields
- **Style:** Veil fill, 1px Line, 10px corners, 2.9rem tall, Archivo 500 0.95rem; mono Data head label 0.45rem above; hints in Text 3.
- **Hover / Focus:** border to Line 2; on focus the border turns magenta, the fill warms to a 0.05 magenta tint and a 3px magenta ring (0.15) appears. Disabled: dashed border, Text 3.
- **Checkboxes:** 1.05rem box, 4px corners, 1.5px Text 3 border; checked fills magenta with a white tick.

### Navigation
Top-bar links in Archivo 600 0.84rem, Text 2; on hover the text whitens and a 1px magenta underline draws in from the left over 260ms. Hidden at ≤760px, where only the wordmark and the small pill remain. A magenta skip link jumps to the claims.

### Hero Chip (signature)
A square chip (19.2% of the art, 32% on phones) on six orthogonal traces, three of them carrying magenta pulses. Chip Deep to Chip Dark fill, Magenta Edge rim, the breathing chip glow, striped pins top and bottom; inside, "As of" and "source valid" in Magenta Pale label caps around the date in League Gothic with a magenta text glow. The date follows the open row. A ring badge of circular text (Text 2, 0.18em) rotates once per 26s around the emblem beside it.

### Claims Dataset (signature)
A hairline table read like a dataset. Each row: the question in quotes with a magenta-washed mono date tag ("as of 2022-01-01"; live questions add a "Your question" tag above); both answers clamped to four lines with citation ids; the eval_scores cell as pretty-printed JSON (`{ 2 items`, orchid keys, mint `true`, coral `false`, amber numbers); a 2rem open button whose plus rotates 45° to a cross when open. Hover tints the row white at 0.035; the open row is magenta at 0.06.

### Citation IDs
Inline tags (S1, S3) at 0.62em Archivo 700, 4px corners, raised 0.25em: Blue Pale on Blue Wash by default; Coral Pale on Coral Wash with a trailing † when the cited version was not valid on the date asked. Known drift, not a rule: the default id's blue tint and the solid-blue "Your question" tag on live rows predate the Blue Is for Action Rule; a neutral tone (Veil and Text) for the default id and a magenta or neutral tag would bring them in line.

### Verdict (signature)
- **Asked band:** magenta wash with a magenta-edge hairline, 10px; "As of" key and the date in Date value, a note on where the date came from, TRACE's source period, and Plain RAG's stale period as a coral-washed chip led by a coral †.
- **Panels:** Glass 2, 12px, hairline; Panel title with a role tag (mint "time-aware", Text 3 "baseline, no dates"); the answer; one verdict line, an authored 1.3rem circle icon (check, cross or dash, 1.75px stroke) with text in mint, coral or Text 2 and a Text 2 sub-line; TRACE adds "2 of 2 claims supported…". Answers rise 8px into place over 420ms.
- **"Why?" control:** text-only Archivo 700 0.92rem; a magenta underline draws in on hover; the magenta chevron turns 180° when open.

### Evidence (signature)
- **Cited versions:** veiled 10px buttons with section name, mono file and dates, mint or coral cited-by tags and a status word; selected is magenta-washed with a magenta edge. Below, the trace_claim_check table with mono heads, mint or coral verdict words and amber scores.
- **Document:** mono path head, then the section text in a dark 10px well with a 2.8rem Line Number gutter; lines holding values from the answer get the magenta wash and inset bar, their number in magenta 700.
- **History of this section:** a commit log on a Trace Hi line; each version is a button with its mono date range, cited-by tags and commit id; nodes light mint or coral with a glow when cited; the current version sits on Veil; the "Date asked" row is a magenta-washed band with a square magenta node placed where the date falls.

### Motion
- **Intro (signature):** plays once per session (sessionStorage `trace-intro`), never under reduced motion; `?intro=1` forces it, `?intro=0` skips it. The board's traces draw in (1400ms, staggered up to 0.7s, pads pop 1100ms later) while a slate panel settles in (600ms); the emblem draws itself (900ms, strokes staggered 0/180/320/420ms, nodes pop at 900ms); the outlined TRACE scans in through the 6px stripe mask (700ms at 900ms); the full form rises (600ms at 1600ms); the fill wipes across the outline (700ms at 2100ms). At 3100ms, or on any click, key or "Skip intro", the panel wipes away to the right (650ms) while the frame wipes in from the left (750ms, 120ms later).
- **Tagline morph:** every 5.2s the headline cycles "Know what was true, and when." → "Answers as of any date." → "Every claim, traced to its source." The old line's 6px stripes thin to nothing as it drifts up 3px while the new line's stripes thicken as it settles from 3px below (760ms, ease-in-out); the counter's magenta bar fills over the same 5.2s.
- **Pulses:** a 3-unit dash on every ninth backdrop trace runs its length in 5–11s, linear, from random phases; chip-trace pulses run every 3.4s.
- **Reduced motion:** all animation and transition off, pulses removed, no intro, the headline holds its first tagline.

## Do's and Don'ts

### Do:
- **Do** keep the four meanings fixed: mint valid, coral not valid, magenta the date asked and brand, blue action.
- **Do** put glow only on signal points, with zero offset, in the point's meaning color.
- **Do** set display text in League Gothic capitals, explanation in Archivo, and every key, date tag, JSON value, path and document in JetBrains Mono.
- **Do** write column heads and field labels as dataset keys in mono (trace_answer, eval_scores, question · as of).
- **Do** use glass (Glass, 1px Line, 14px blur) for sections and panels, and limit hover to a Line 2 border and a 2px lift.
- **Do** pair coral with a † or words every time.
- **Do** use the darker Action Blue Hover on button hover so white text keeps AA contrast.
- **Do** honor reduced motion and the once-per-session intro with a visible skip.

### Don't:
- **Don't** use light surfaces, white cards or chat bubbles; the ground is always the board and the slate frame.
- **Don't** use blue for state, validity or decoration.
- **Don't** add offset colored shadows or glows on text blocks, panels or headings.
- **Don't** use stripe masks beyond display type in motion and the chip's pins.
- **Don't** stack an uppercase tracked label above a heading as an eyebrow.
- **Don't** add a fourth typeface or set prose in mono.
- **Don't** scale, recolor or glow glass on hover.

## Streamlit surface (older)

`ui/app.py` (with `ui/style.css`) still uses the earlier light Timetable look, not this world: white paper with black ink, square corners throughout, Archivo at variable widths (expanded for the masthead, condensed uppercase column heads), timetable blue #003082 for structure, actions and "valid", signal yellow #FFC917 for the "As of" strip and the date asked, red #C8102E (with a †) for sources not valid on that date. Its layout is a yellow validity strip over a five-column comparison grid, status chips, ruled tables and a to-scale validity timeline, separated by rule weights (5px, 3px, 1px) with no shadows. Its tokens are not carried in this file's frontmatter.
