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
  answer:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "1.22rem"
    fontWeight: 500
    lineHeight: 1.42
  title:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "1.05rem"
    fontWeight: 800
    lineHeight: 1.2
  body:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "0.9rem"
    fontWeight: 400
    lineHeight: 1.4
    fontFeature: "'tnum' 1"
  label:
    fontFamily: "Archivo, Arial, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 700
    letterSpacing: "0.04em"
    fontVariation: "'wdth' 72"
  code:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: "0.86em"
    fontWeight: 400
rounded:
  none: "0px"
spacing:
  cell-gap: "1.4rem"
  row-y: "1.05rem"
  page-x: "2.5rem"
  page-x-sm: "1rem"
  section: "2rem"
  section-lg: "3rem"
components:
  button-primary:
    backgroundColor: "{colors.timetable-blue}"
    textColor: "{colors.paper}"
    rounded: "{rounded.none}"
    height: "2.75rem"
    width: "8.5rem"
  button-primary-hover:
    backgroundColor: "{colors.timetable-blue-deep}"
  validity-strip:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "0.75rem 1.1rem"
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
  citation-id:
    backgroundColor: "{colors.blue-tint}"
    textColor: "{colors.timetable-blue}"
    rounded: "{rounded.none}"
    padding: "0 0.32em"
  input:
    backgroundColor: "{colors.paper-2}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
---

# Design System: TRACE

## Overview

**Creative North Star: "The Timetable Page"**

TRACE's answers are set like a printed railway timetable: a heavy masthead over a thick blue rule, a yellow header stating the period the answer is valid for, and every system as a row in one ruled grid under a single set of column heads. The page reads as a public information document, not a chat product. Nothing floats; everything sits on a rule.

Density is that of a working timetable: tabular figures throughout, condensed uppercase column heads, compact cells, and one deliberately large element per row (the answer sentence). Color is functional signage with three fixed meanings: blue for structure and action, yellow for "the date you asked", red for "not valid on that date". White paper and black ink carry everything else.

The world refuses the AI-search defaults of chat bubbles, soft cards, gradients and drop shadows. Depth is never simulated; hierarchy comes from rule weight (5px, 3px, 1px), type weight and width, and the three signal colors.

**Key Characteristics:**
- White paper, black ink, square corners everywhere (0px radius, including Streamlit widgets).
- Rules, not containers: a 5px blue masthead rule, 3px ink rules opening each grid or section, 1px ink under column heads, 1px grey between rows.
- Archivo throughout at variable width: expanded (112%) for the masthead, condensed (72%) for column heads and labels.
- Tabular figures on the whole page; dates are the primary data.
- Three signal colors, each with exactly one meaning.

## Colors

A public-transport palette: paper and ink, one institutional blue, one signal yellow, one alarm red.

### Primary
- **Timetable Blue** (timetable-blue): the masthead rule, primary action (Ask), focus outlines, caret, links, "valid" status text, the TRACE row's role label, citation ids, and valid segments on the validity timeline. Also the Streamlit `primaryColor`, so toggles, checked radios, checkboxes and the slider track inherit it.
- **Deep Timetable Blue** (timetable-blue-deep): hover state of the primary button only.
- **Blue Tint** (blue-tint): background of "valid" status chips and citation ids.

### Secondary
- **Signal Yellow** (signal-yellow): the validity strip under the masthead, the slider's date-value tag, the date-asked marker cap on the timeline, and text selection. It always means "the date being asked about / the period this answer holds for".

### Tertiary
- **Stale Red** (stale-red): only for sources not valid on the asked date: red date ranges, "Not yet written"/"Superseded" chips, the dagger footnote and its note, invalid timeline segments.
- **Red Tint** (red-tint): background of invalid status chips.

### Neutral
- **Ink** (ink): body text, row names, heavy 3px section rules and 1px column-head rules, the timeline's date mark.
- **Ink 2** (ink-2): column heads, field labels, secondary prose (description, "when" lines, timeline key).
- **Ink 3** (ink-3): muted text (file paths, "not checked", footer, axis years), the baseline row's role label and its 3px column rule, unselected radio rings (meets 3:1 on white).
- **Rule Grey** (rule): 1px rules between rows, under expanders and above the footer; Streamlit `borderColor`.
- **Paper** (paper): page ground.
- **Paper 2** (paper-2): input fields, inline code, neutral status chips, empty timeline tracks; Streamlit `secondaryBackgroundColor`.

### Named Rules
**The One Meaning Rule.** Each signal color has a single meaning across the page: blue = structure/action/valid, yellow = the date asked, red = not valid on that date. Red never decorates, yellow never highlights anything except the date or validity period.

**The Paper and Ink Rule.** Surfaces are white or Paper 2. There are no tinted panels, gradients, or colored section backgrounds other than the yellow validity strip.

## Typography

**Display Font:** Archivo (with Arial, sans-serif), variable width 62–125, weights 400–800
**Body Font:** Archivo (same family)
**Label/Mono Font:** JetBrains Mono (with ui-monospace) for inline code only

**Character:** One grotesque used at different widths does all the work, the way transit signage does: wide and black for the name, condensed and capitalized for column heads, regular for reading. Mono appears only where the docs themselves quote code.

### Hierarchy
- **Display** (800, 4.25rem; 3.2rem at ≤760px, 2.6rem at ≤480px; line-height 0.82; width 112%): the TRACE masthead only.
- **Answer** (500, 1.22rem / 1.42; 1.32rem with a 38rem measure in the per-system detail; 1.1rem ≤760px, 1.04rem ≤480px): the answer sentence, the one large element in each grid row.
- **Title** (800, 1.05rem / 1.2): system names in the grid. Detail-column heads sit one step below (700, 0.98rem); the section-history head steps up to 1.3rem.
- **Body** (400, 0.86–0.95rem / 1.4): cells, table text, description, "when" lines. The masthead expansion is 500 at 1.05rem with its initial letters in blue 800.
- **Label** (700, 0.78rem, 0.04em tracking, uppercase, width 72%, Ink 2): column heads, field labels, validity-strip keys, table section labels ("Cited sources", "Claim check"), and the role tag beside a system name (blue for TRACE, Ink 3 for the baseline).

### Named Rules
**The Tabular Figures Rule.** `font-variant-numeric: tabular-nums` is set on the root; dates and scores must align in columns.

**The Width-Not-Size Rule.** Labels are distinguished by condensed width, weight and capitals, not by shrinking further. Option text (toggle, checkbox) is sentence case at 0.9rem/500 and is never styled as a label.

## Layout

A single 1280px-max column with 2.5rem side padding (1rem at ≤760px). The page runs top to bottom as one document: masthead (name | expansion + description | source link, aligned to the baseline, closed by the blue rule), yellow validity strip, the ask form as a ruled row (1px ink top rule, no card), the comparison grid, per-system detail in two columns, "How it works" table, footer.

The comparison grid is a five-column CSS grid (11.75rem system | flexible answer | 12.5rem cited source | 9.5rem status | 8rem claims) with 1.4rem column gap and rows padded ~1.05rem/1.15rem. Rows align to start.

Responsive behavior:
- **≤1080px:** the column-head row hides; each row puts system and answer across the full width with the three facts in three columns beneath, each fact carrying its own condensed label. The two detail columns stack; the Ask button wraps to its own line.
- **≤760px:** the comparison grid moves above the form so the first screen shows both answers; facts sit in two columns; the masthead stacks; secondary table columns (section name, file path) hide.
- **≤480px:** the masthead description hides and the masthead and strip tighten so both answer rows fit the first screen.

Vertical rhythm: 1.4rem between strip and form, ~2.2rem before the detail, 2rem before section history and footer, 3rem before "How it works".

## Elevation & Depth

Flat. No box shadows anywhere. Depth and grouping come from rule weight and from the yellow strip as the only filled band.

### Named Rules
**The Rule-Weight Rule.** Hierarchy of separation is expressed in line weight: 5px Timetable Blue closes the masthead; 3px Ink opens a grid or section (Ink 3 for the baseline's detail column); 1px Ink sits under column heads and above the form and "How it works"; 1px Rule Grey separates rows.

## Shapes

Square everywhere: 0px radius on inputs, selects, buttons, alerts, expanders, code, chips and the form, enforced through both `config.toml` (`baseRadius`, `buttonRadius`) and stylesheet overrides. The only non-rectangular marks are the native radio and toggle controls. The validity timeline is drawn to scale from flat bars (0.5rem tracks), a 3px ink date mark capped by a small yellow tab outlined in ink, and an axis with tick marks.

## Components

### Buttons
- **Shape:** square (0px), 2.75rem tall, min 8.5rem wide.
- **Primary (Ask):** Timetable Blue fill, white 700 text with 0.02em tracking, search icon from Streamlit's icon set.
- **Hover / Focus:** background shifts to Deep Timetable Blue over 120ms ease-out; focus is a 2px blue outline at 2px offset (global).
- **Secondary:** square, 600 weight, Streamlit's bordered secondary style.

### Chips (status)
- **Style:** inline block, 700 at 0.78rem, 0.1rem 0.4rem padding, no radius, tint background with matching text: Valid/Supported (Blue Tint + blue), Not yet written/Superseded/Outdated source/Unsupported (Red Tint + red), no date or unknown verdict (Paper 2 + Ink 2).

### Citation ID
- Inline tag (S1, S3) at 0.68em, 800, width 90%, Blue Tint + blue, set slightly raised in the answer text; in the source cell it leads the date range.

### Cards / Containers
- None. The form, grid, detail columns and history are ruled regions, not cards: no background, no border box, no radius, no shadow.

### Inputs / Fields
- **Style:** Paper 2 fill, square, Streamlit's widget border in Rule Grey; labels in the Label role above.
- **Focus:** blue border/outline from `primaryColor` plus the global 2px blue focus ring; caret blue.
- **Slider:** blue track and thumb; the value tag is Signal Yellow with ink 700 text (the date asked).
- **Radio:** unselected ring 1.5px Ink 3; selected filled blue.

### Navigation
- None beyond the masthead's "Source on GitHub" link: blue, 600, underline offset 3px, thicker underline on hover.

### Validity Strip (signature)
Full-width Signal Yellow band directly under the masthead rule: label/value pairs ("Asked for", "Source valid", "Corpus") with condensed uppercase keys and 800 values, wrapping with 2.6rem column gap. `role="status"`.

### Timetable Grid (signature)
Column-head row between a 3px ink rule and a 1px ink rule; each system is one row: name (Title) with role tag, answer sentence (Answer), cited source dates (red and bold when invalid), status chip, claims summary. Invalid citations get a red dagger in the answer and a red footnote line under it.

### Sources and Claims Tables
Borderless tables with condensed uppercase heads over a 1px ink rule and 1px grey row rules; ids in 800; file paths as a muted second line; dates never wrap.

### Validity Timeline
Per-source rows on a 2.2rem label column: Paper 2 track, blue or red segment drawn to scale (scaleX in over 520ms, cubic-bezier(0.16, 1, 0.3, 1); no animation under reduced motion), ink date mark with yellow cap, ruled year axis and a small key.

### Expanders
Rows of the timetable: no box, 1px grey bottom rule, 600 summary at 0.88rem that turns blue on hover.

## Do's and Don'ts

### Do:
- **Do** keep every corner square (0px) and every region bounded by rules, not boxes.
- **Do** state the validity period in the yellow strip whenever an answer is shown, with the date asked first.
- **Do** use red only for a source not valid on the date asked, and pair it with text ("Not yet written", a dated footnote), never color alone.
- **Do** set column heads and field labels in Archivo 700, 0.78rem, uppercase, width 72%, Ink 2.
- **Do** keep the answer sentence the largest text in each grid row.
- **Do** keep tabular figures on, and keep dates unwrapped.

### Don't:
- **Don't** use chat bubbles, soft cards, drop shadows, gradients or rounded corners.
- **Don't** use yellow for emphasis, warnings or buttons; it belongs to the date asked and the validity strip.
- **Don't** add tinted panels or colored section backgrounds beyond the validity strip and status/citation tints.
- **Don't** put a condensed uppercase label above a heading as an eyebrow; labels name columns, fields, and tables only.
- **Don't** show inline code in Streamlit's default green; code is ink on Paper 2 in JetBrains Mono.
