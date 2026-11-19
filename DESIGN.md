---
name: TRACE
description: Temporal Retrieval with Attributed Claim Evidence; answers set as a printed timetable page with a stated validity period.
colors:
  ink: "#111111"
  ink-2: "#4a4a48"
  ink-3: "#6b6b67"
  rule: "#cfcfcb"
  paper: "#ffffff"
  paper-2: "#f3f3f1"
  timetable-blue: "#003082"
  timetable-blue-deep: "#00256a"
  blue-tint: "#e8edf6"
  signal-yellow: "#ffc917"
  stale-red: "#c8102e"
  red-tint: "#fbe9ec"
typography:
  display:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "4.25rem"
    fontWeight: 800
    lineHeight: 0.82
    letterSpacing: "0.01em"
    fontVariation: "'wdth' 112"
  display-md:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "3.2rem"
    fontWeight: 800
    lineHeight: 0.82
    fontVariation: "'wdth' 112"
  display-sm:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "2.6rem"
    fontWeight: 800
    lineHeight: 0.82
    fontVariation: "'wdth' 112"
  verdict:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "1.6rem"
    fontWeight: 500
    lineHeight: 1.32
    fontVariation: "'wdth' 96"
  verdict-md:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "1.32rem"
    fontWeight: 500
    lineHeight: 1.32
    fontVariation: "'wdth' 96"
  verdict-sm:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "1.04rem"
    fontWeight: 500
    lineHeight: 1.4
    fontVariation: "'wdth' 96"
  answer:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "1.22rem"
    fontWeight: 500
    lineHeight: 1.42
  strip-value:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "1.1rem"
    fontWeight: 800
  title:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "1.05rem"
    fontWeight: 800
    lineHeight: 1.2
  detail:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "0.98rem"
    fontWeight: 700
    lineHeight: 1.3
  body:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "0.9rem"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "'tnum' 1"
  label:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 700
    letterSpacing: "0.04em"
    fontVariation: "'wdth' 72"
  caption:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 400
    lineHeight: 1.4
  code:
    fontFamily: "JetBrains Mono, ui-monospace, Consolas, monospace"
    fontSize: "0.86em"
    fontWeight: 400
  document:
    fontFamily: "JetBrains Mono, ui-monospace, Consolas, monospace"
    fontSize: "0.86rem"
    fontWeight: 400
    lineHeight: 1.6
rounded:
  none: "0px"
spacing:
  page-x: "2.5rem"
  page-x-sm: "1rem"
  field-gap: "1.2rem"
  panel-x: "2rem"
  panel-y: "1.4rem"
  column-gap: "2rem"
  section: "2rem"
  section-lg: "3rem"
  cell-gap: "1.4rem"
  row-y: "1.05rem"
components:
  button-primary:
    backgroundColor: "{colors.timetable-blue}"
    textColor: "{colors.paper}"
    rounded: "{rounded.none}"
    height: "2.75rem"
    width: "8.5rem"
  button-primary-hover:
    backgroundColor: "{colors.timetable-blue-deep}"
  button-primary-busy:
    backgroundColor: "{colors.ink-3}"
  input:
    backgroundColor: "{colors.paper-2}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    height: "2.75rem"
    padding: "0 0.85rem"
  input-focus:
    backgroundColor: "{colors.paper}"
  checkbox:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.none}"
    size: "1rem"
  checkbox-checked:
    backgroundColor: "{colors.timetable-blue}"
  validity-strip:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "0.7rem 1rem"
  stale-chip:
    backgroundColor: "{colors.red-tint}"
    textColor: "{colors.ink}"
    padding: "0.05rem 0.4rem"
  verdict-answer:
    textColor: "{colors.ink}"
    typography: "{typography.verdict}"
    width: "34rem"
  verdict-call-ok:
    textColor: "{colors.timetable-blue}"
    typography: "{typography.detail}"
  verdict-call-bad:
    textColor: "{colors.stale-red}"
    typography: "{typography.detail}"
  verdict-call-na:
    textColor: "{colors.ink-2}"
    typography: "{typography.detail}"
  citation-id:
    backgroundColor: "{colors.blue-tint}"
    textColor: "{colors.timetable-blue}"
    rounded: "{rounded.none}"
    padding: "0 0.35em"
  citation-id-stale:
    backgroundColor: "{colors.red-tint}"
    textColor: "{colors.stale-red}"
  cited-by-ok:
    backgroundColor: "{colors.blue-tint}"
    textColor: "{colors.timetable-blue}"
    typography: "{typography.caption}"
    padding: "0.08rem 0.4rem"
  cited-by-bad:
    backgroundColor: "{colors.red-tint}"
    textColor: "{colors.stale-red}"
    typography: "{typography.caption}"
    padding: "0.08rem 0.4rem"
  source-row-current:
    backgroundColor: "{colors.blue-tint}"
    padding: "0.65rem 0.5rem"
  document-line-hit:
    backgroundColor: "{colors.blue-tint}"
    textColor: "{colors.ink}"
    typography: "{typography.document}"
  log-current:
    backgroundColor: "{colors.paper-2}"
  log-date-asked:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.ink}"
  status-valid:
    backgroundColor: "{colors.blue-tint}"
    textColor: "{colors.timetable-blue}"
    typography: "{typography.label}"
    padding: "0.1rem 0.4rem"
  status-invalid:
    backgroundColor: "{colors.red-tint}"
    textColor: "{colors.stale-red}"
    padding: "0.1rem 0.4rem"
  status-neutral:
    backgroundColor: "{colors.paper-2}"
    textColor: "{colors.ink-2}"
    padding: "0.1rem 0.4rem"
---

# Design System: TRACE

## Overview

**Creative North Star: "The Timetable Page"**

TRACE's answers are set like a printed railway timetable: a heavy masthead over a thick blue rule, a yellow band stating the date asked and the period each answer's source is valid for, and the systems compared under ruled heads. The page reads as a public information document, not a chat product. Nothing floats; everything sits on a rule.

Density is that of a working timetable: tabular figures throughout, condensed uppercase column heads, compact cells, and one deliberately large element per system (the answer sentence). Color is functional signage with three fixed meanings: blue for structure, action and "valid", yellow for "the date you asked", red for "not valid on that date". White paper and black ink carry everything else.

The world refuses the AI-search defaults of chat bubbles, soft cards, gradients and drop shadows. Depth is never simulated; hierarchy comes from rule weight (5px, 3px, 1px), type weight and width, and the three signal colors. The web demo (`web/`) is the primary surface; the Streamlit page (`ui/app.py`, `ui/style.css`) is the older surface on the same tokens.

**Key Characteristics:**
- White paper, black ink, square corners on every surface, field, button and chip (0px radius).
- Rules, not containers: a 5px blue masthead rule, 3px ink rules opening each verdict panel and the evidence, 1px ink under column heads, 1px grey between rows.
- Archivo throughout at variable width: expanded (112%) for the masthead, condensed (72%) for column heads and labels, slightly condensed (96%) for the verdict answer.
- Tabular figures on the whole page; dates are the primary data.
- Three signal colors, each with exactly one meaning.

## Colors

A public-transport palette: paper and ink, one institutional blue, one signal yellow, one alarm red.

### Primary
- **Timetable Blue** (timetable-blue): the masthead rule, the Ask button, checked checkboxes, focus outlines, caret, links, the "Why?" control, valid verdict lines and their icons, TRACE's role tag, citation ids, cited-by tags and commit dots for valid versions. Also the Streamlit `primaryColor`.
- **Deep Timetable Blue** (timetable-blue-deep): hover state of the primary button only.
- **Blue Tint** (blue-tint): background of citation ids, valid cited-by tags, the selected cited version, and the highlighted lines in the document view.

### Secondary
- **Signal Yellow** (signal-yellow): the "As of" strip above the verdict, the "Date asked" row in the commit history, the skip link and text selection. It always means "the date being asked about / the period this answer holds for".

### Tertiary
- **Stale Red** (stale-red): only for sources not valid on the asked date: the dagger (†) on stale citation ids and in the strip, the "Cites a version not valid on…" verdict line and its icon, red cited-by tags, "Not yet written"/"Superseded" status, red commit dots, form errors.
- **Red Tint** (red-tint): background of stale citation ids, red cited-by tags and, on the yellow strip, the stale date chip.

### Neutral
- **Ink** (ink): body text, headings, heavy 3px rules and 1px column-head rules, the date-asked node in the history.
- **Ink 2** (ink-2): column heads and field labels, verdict sub-lines, the claims line, the "not judged" verdict line.
- **Ink 3** (ink-3): muted text (hints, file paths and commit meta, line numbers, footer), the baseline's role tag and its 3px panel rule, unchecked checkbox border, the busy Ask button.
- **Rule Grey** (rule): 1px rules between rows, around the question bar and verdict panels, the panel divider, the history's vertical line, field borders.
- **Paper** (paper): page ground, focused fields.
- **Paper 2** (paper-2): fields at rest, inline code, the current version in the history, hover on cited versions.

### Named Rules
**The One Meaning Rule.** Each signal color has a single meaning across the page: blue = structure/action/valid, yellow = the date asked, red = not valid on that date. Red never decorates, yellow never highlights anything except the date asked or a validity period.

**The Paper and Ink Rule.** Surfaces are white or Paper 2. There are no tinted panels, gradients, or colored section backgrounds other than the yellow strip and the date-asked row; Blue Tint and Red Tint appear only on chips, tags, the selected source and highlighted document lines.

**The Ink-on-Yellow Rule.** Nothing red sits directly on Signal Yellow: red text on yellow fails contrast. A stale date in the strip is ink inside a Red Tint chip, led by a red dagger.

## Typography

**Display Font:** Archivo (with Arial, sans-serif), variable width 62–125, weights 400–800
**Body Font:** Archivo (same family)
**Label/Mono Font:** JetBrains Mono (with ui-monospace, Consolas) for inline code, file paths and the document view

**Character:** One grotesque used at different widths does all the work, the way transit signage does: wide and black for the name, condensed and capitalized for column heads, regular for reading. Mono appears only where the docs themselves are quoted.

### Hierarchy
- **Display** (800, 4.25rem; 3.2rem at ≤760px; 2.6rem at ≤480px; line-height 0.82; width 112%): the TRACE masthead only.
- **Verdict** (500, 1.6rem / 1.32, width 96%, 34rem measure; 1.32rem at ≤760px; 1.04rem / 1.4 at ≤480px): the answer sentence in each verdict panel, the largest text after the masthead. Values in it may be 800.
- **Answer** (500, 1.22rem): a declined or empty answer, set muted in Ink 3; also the Streamlit grid's answer sentence.
- **Strip value** (800, 1.1rem): the date asked in the "As of" strip.
- **Title** (800, 1.05rem / 1.2): system names heading each verdict panel; the masthead expansion sits at 500 1.05rem with its initials in blue 800.
- **Detail** (700, 0.98rem): verdict lines (at 600), the "Why?" control, cited-version names.
- **Body** (400, 0.9rem / 1.5): fields, sub-lines, claims table, history dates (700), "How it works".
- **Label** (700, 0.78rem, 0.04em tracking, uppercase, width 72%, Ink 2): field labels, column and section heads, strip keys, the role tag beside a system name, the "Date asked" key.
- **Caption** (400–500, 0.78rem, sentence case): hints, file path and date meta, cited-by tags, commit meta, document note, footer. Never uppercase.
- **Document** (JetBrains Mono 400, 0.86rem / 1.6): the line-numbered section text.

### Named Rules
**The Tabular Figures Rule.** `font-variant-numeric: tabular-nums` is set on the root; dates and scores must align in columns.

**The Width-Not-Size Rule.** Labels are distinguished by condensed width, weight and capitals, not by shrinking below 0.78rem. Option text (checkboxes) is sentence case at 0.9rem/500 and is never styled as a label; captions share the label's size but never its capitals.

## Layout

A single column, 75rem max, with 2.5rem side padding (1rem at ≤760px). The web page runs top to bottom as one document:

1. **Masthead:** three columns aligned to the baseline (name | expansion + one-line description | "Source on GitHub"), closed by the 5px blue rule.
2. **Question bar:** one ruled row, no card: Question (flexible) | Example select (19rem) | As of ISO text field with its range hint (10.5rem) | Ask (8.5rem), 1.2rem column gap, with the two square checkboxes on a line beneath; closed by a 1px grey rule.
3. **Verdict:** the yellow "As of" strip, then two verdict panels side by side (1fr 1fr) split by a 1px grey vertical rule, each opened by a 3px rule (Ink for TRACE, Ink 3 for the baseline) and padded 1.4rem / 2rem; the "Why?" control beneath.
4. **Evidence (on "Why?"):** opened by a 3px ink rule; three columns (17rem cited versions and claim check | flexible document view | 17rem history), 2rem gap.
5. **How it works:** 3rem above, opened by a 1px ink rule, a numbered list at 60rem measure.
6. **Footer:** 2rem above, 1px grey rule, caption text.

Responsive behavior:
- **≤1080px:** the question bar becomes two columns with the question full width; the evidence keeps sources (15rem) and document side by side and drops the history to full width beneath.
- **≤760px:** the masthead stacks; panels stack, the second gaining a 1px grey top rule; the evidence is one column. Order changes so the verdict comes first: strip (now also stating the question), both panels, "Why?", then the question bar opened by a 3px ink rule.
- **≤480px:** the masthead description hides and the masthead and strip tighten; the strip drops its source and corpus pairs; verdict lines and sub-lines step down to body and caption.

## Elevation & Depth

Flat. No box shadows anywhere. Depth and grouping come from rule weight and from the two yellow fills (the strip and the date-asked row) as the only filled bands.

### Named Rules
**The Rule-Weight Rule.** Hierarchy of separation is expressed in line weight: 5px Timetable Blue closes the masthead; 3px Ink opens a verdict panel, the evidence, or (on phones) the question bar, with Ink 3 for the baseline's panel; 1px Ink sits under column heads and above "How it works"; 1px Rule Grey separates rows and panels.

## Shapes

Square everywhere: 0px radius on fields, the select, buttons, checkboxes, chips, tags, the strip and every region. The round marks are drawings, not containers: the authored verdict icons (a 1.4rem outlined circle carrying a check, cross or dash, 1.75px stroke), the commit nodes on the history line (0.55rem rings, filled blue or red when cited; the date-asked node is a square ink block), and the loading ring. The chevron on the select and "Why?" is an authored 1.75px stroke and turns 180° when open.

## Components

### Buttons
- **Shape:** square (0px), 2.75rem tall, min 8.5rem wide.
- **Primary (Ask):** Timetable Blue fill, white 700 text at 0.9rem with 0.02em tracking, no icon.
- **Hover / Focus:** background shifts to Deep Timetable Blue over 120ms ease-out; focus is a 2px blue outline at 2px offset (global). Busy: Ink 3 fill with a progress cursor.
- **"Why?" control:** text-only, Detail type in blue with a chevron; underlines on hover; the chevron rotates 180° over 200ms when the evidence is open.

### Inputs / Fields
- **Style:** Paper 2 fill, 1px Rule Grey border, square, 2.75rem tall, 500 0.9rem; labels in the Label role 0.4rem above.
- **Hover / Focus:** border darkens to Ink 3; on focus a 2px blue outline inset 1px and the fill turns Paper. Disabled: dashed border on Paper, Ink 3 text.
- **As of:** a plain ISO text field (YYYY-MM-DD) with tabular figures, 0.02em tracking, and a caption hint stating the valid range; no date picker.
- **Example select:** the same field with native appearance removed and an authored chevron at the right.
- **Checkboxes:** 1rem square box, 1.5px Ink 3 border on Paper; checked fills blue with a white tick; hover darkens the border to Ink; option text sentence case 0.9rem/500.

### Validity Strip (signature)
Full-width Signal Yellow band opening the verdict: label/value pairs ("As of" with the date in Strip value and a note on where the date came from; "TRACE source"; "Plain RAG source"; "Corpus"), wrapping with a 1.8rem column gap. A stale period appears as ink in a Red Tint chip led by a red †. On phones it also states the question asked.

### Verdict Panels (signature)
Two ruled panels, TRACE and Plain RAG, each a Title heading with a condensed role tag beside it (blue "time-aware", Ink 3 "baseline, no dates"). Under it, the answer sentence in Verdict type, then one verdict line: an authored circle icon with Detail text in blue ("Source valid on …"), red ("† Cites a version not valid on …") or Ink 2 ("Declined rather than guess"), with a body sub-line in Ink 2 naming the source and its dates. TRACE adds a claims line ("2 of 2 claims supported…"). Answers and verdict lines rise 6px into place over 420ms on arrival, the second panel 90ms later.

### Citation ID
Inline tag (S1, S3) at 0.5em, 800, width 90%, raised in the answer: Blue Tint + blue, or Red Tint + red with a trailing † when the cited version was not valid on the date asked.

### Cited-by Tags
Caption-size square tags naming who cited a version ("**S1** TRACE"): Blue Tint + blue when that version was valid on the date asked, Red Tint + red when not. Used on cited versions and history rows.

### Evidence View (signature)
- **Cited versions:** a list under a 1px ink rule; each row is a button (Detail section name, caption file and dates, cited-by tags, a "Valid / Not yet written on …" status in blue or red). Hover Paper 2; selected Blue Tint. Below it the TRACE claim check: a borderless table with label heads over a 1px ink rule, verdict word in blue or red, scores right-aligned.
- **Document view:** a head line (mono caption path › section, "Cited by …" and the version's dates in 700) over a 1px ink rule, then the section text in Document type with a 2.6rem line-number gutter in Ink 3. Lines containing values from the answer are highlighted in Blue Tint with a blue 700 line number. A caption note says what the highlight means.
- **History of this section:** a merged commit log under a 1px ink rule, a 1px grey vertical line with a node per version; each row shows the date range (700), cited-by tags, any file move, and the commit id in caption mono. The current version sits on Paper 2. The "Date asked" row, in Signal Yellow with a square ink node, is placed between the versions where the asked date falls.

### Navigation
None beyond the masthead's "Source on GitHub" link (blue, 600, underline offset 3px, thicker underline on hover) and a yellow skip link to the answer.

### Streamlit Surface (older)
`ui/app.py` keeps the earlier layout on the same tokens: a yellow validity strip, a five-column comparison grid (11.75rem system | answer | 12.5rem cited source | 9.5rem status | 8rem claims, 1.4rem cell gap, ~1.05rem row padding) with the answer in the Answer step, status chips, borderless sources and claims tables, a to-scale validity timeline (Paper 2 tracks, blue or red segments drawn in over 520ms, an ink date mark with a yellow cap) and ruled expanders. Square corners there are enforced through `config.toml` and `ui/style.css`.

## Do's and Don'ts

### Do:
- **Do** keep every corner square (0px) and every region bounded by rules, not boxes.
- **Do** state the date asked in the yellow strip whenever an answer is shown, with the date first.
- **Do** use red only for a source not valid on the date asked, and pair it with text and the † mark ("Not yet written", "Cites a version not valid on…"), never color alone.
- **Do** set field labels, column and section heads in Archivo 700, 0.78rem, uppercase, width 72%, Ink 2.
- **Do** keep the verdict answer the largest text below the masthead.
- **Do** keep tabular figures on, and keep dates unwrapped.
- **Do** draw icons as authored inline SVG strokes in the signal color of their meaning.

### Don't:
- **Don't** use chat bubbles, soft cards, drop shadows, gradients or rounded corners.
- **Don't** use yellow for emphasis, warnings or buttons; it belongs to the date asked.
- **Don't** put red text directly on Signal Yellow; use ink in a Red Tint chip.
- **Don't** add tinted panels or colored section backgrounds beyond the yellow strip, the date-asked row and the chip, tag and highlight tints.
- **Don't** put a condensed uppercase label above a heading as an eyebrow; labels name fields, columns, tables and sections only.
- **Don't** set captions in capitals; uppercase belongs to labels.
- **Don't** show inline code in a framework's default color; code is ink on Paper 2 in JetBrains Mono.
