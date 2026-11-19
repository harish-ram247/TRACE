---
version: 1
slug: "web-index-html"
primary_target: "web/index.html"
related_targets: ["web/style.css","web/app.js"]
---

# TRACE web demo (web/index.html)

Scope: the custom web front end that replaces the Streamlit demo. Mode: operate. Audience: recruiters
and HR first, engineers second. Task: see in two seconds that TRACE is right for the date where plain
RAG is not, then open the evidence. Constraints: plain HTML/CSS/JS, no build step; calls the existing
API (/ask, /chunks, /lineages); example answers are precomputed so the first screen never waits on
the API; inherits the Timetable visual system recorded in DESIGN.md.

## Direction contract

THESIS: A then-vs-now verdict first, evidence second. Two side-by-side verdict panels answer "was it
right for that date?" before anything else; "Why?" opens the cited line inside the real document with
its git history. Refuses chat transcripts and generic answer cards.

OWN-WORLD: The Timetable system from DESIGN.md: white paper, ink, timetable blue #003082 for structure,
actions and "valid", signal yellow #FFC917 for the date asked, red #C8102E only for "not valid on that
date"; Archivo with tabular figures, condensed uppercase column heads, square corners, ruled hairlines,
JetBrains Mono only for real code and document text.

STORY: The visitor reads "As of 2022-01-01", sees TRACE: "port 5000", source valid that day (blue check)
and plain RAG: "4173", source not yet written (red cross). One click on Why? shows the doc section with
the "Default: 5000" line highlighted and the commit timeline of that section, the cited version marked.

FIRST VIEWPORT: Masthead (TRACE, expansion, one line) over the blue rule; the question bar (question,
examples, date, Ask) as one ruled row; the two verdict panels side by side with the answer sentence
large and a one-line verdict under each; the Why? control beneath them.

FORM: seed: none (pinned) — "Go with direction B, the then vs now verdict" and "Go with direction C,
the git history view", on the Timetable world already recorded in DESIGN.md.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
