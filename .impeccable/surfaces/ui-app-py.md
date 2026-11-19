---
version: 1
slug: "ui-app-py"
primary_target: "ui/app.py"
related_targets: ["ui/style.css"]
---

# TRACE demo (ui/app.py)

Scope: the Streamlit demo page. Mode: operate. Audience: recruiters and HR first, engineers second.
Task: see TRACE answer a date-dependent question correctly next to plain RAG, then ask their own.
Constraints: stays on Streamlit; same features and API calls; one finished cached example on load.

## Direction contract

THESIS: Answers are a timetable page: a header states the period the answer is valid for, and the
systems are rows in one grid. Refuses the AI-search default of chat bubbles and soft cards.

OWN-WORLD: White ground, black ink, timetable blue #003082 for the masthead rule and actions, signal
yellow #FFC917 for the validity strip and the date asked, red #C8102E only for stale/invalid. Archivo
throughout, tabular figures, condensed width for column heads; square corners, ruled 1px grid.

STORY: The visitor sees "Asked for 2022-01-01" and two rows: TRACE says 5000 with a source valid
that day; plain RAG says 4173 from a source written later, marked red. They understand time matters,
then ask their own question.

FIRST VIEWPORT: Masthead (TRACE, expansion, one-line description) over a blue rule; yellow validity
strip; the ask row (question, date, system, Ask); the comparison grid with the answer value set large.

FORM: Timetable, pick (list position 1, not the roll). seed:caae368e5af44175

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Adaptations (decided during the build)

- The large element in each grid row is the answer sentence, not a separate value column: the API
  returns free prose, and a "value" column (the sketch's "Port") only fits one question.
- At 760px and below the comparison grid renders above the form, so a phone's first screen shows
  both answers; above that width it sits under the ask row as in FIRST VIEWPORT.
- Per-system detail (sources table, validity timeline, claim check, source text and history)
  follows the grid, without an eyebrow label.
