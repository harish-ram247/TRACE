---
version: 1
slug: "web-index-html"
primary_target: "web/index.html"
related_targets: ["web/style.css","web/app.js"]
---

# TRACE web demo (web/index.html)

Scope: the custom web front end (served at /demo). Mode: operate, with a short branded intro. Audience:
recruiters and HR first, engineers second. Task: after a brief intro, see TRACE's claims laid out as a
structured dataset (question, TRACE answer, plain RAG answer, evaluation), open any row for the
then-vs-now verdict and git-history evidence, and ask their own question. Constraints: plain
HTML/CSS/JS; same API; precomputed examples so nothing waits; the intro plays once per session, can be
skipped, and is skipped under reduced motion.

## Direction contract

THESIS: A dark circuit-board world where TRACE is literal: signals run along traces to the claim they
support. A one-time intro (traces draw in, an emblem draws itself, an outlined TRACE scans in with its
full form beneath), then a hero whose headline morphs between taglines with a venetian-blind scan-line
wipe, then the claims as a structured dataset table. Refuses light SaaS cards and chat transcripts.

OWN-WORLD: Pinned by the user's reference video ("reframe the colour palette and design according to
the intro video's theme"): near-black slate ground (#0b0f12) inside a deep-magenta circuit board
(#1c0614, traces #4a1239 / #7a1f5e, glowing magenta #ff3da5), white tall condensed capitals (League Gothic) for
display, Archivo for UI text, JetBrains Mono for JSON and documents, one electric-blue action colour
(#2f5bff). Glassmorphism on panels (translucent slate, backdrop blur, 1px hairline borders);
minimal hover (border brightens, 2px lift). Valid = mint #5fe3b3, not valid on the date = coral #ff6b4a (always with a dagger).

STORY: The intro says what TRACE is in two seconds; the hero tagline "Know what was true, and when."
says why; the dataset shows six claims where TRACE cites a source valid on the date and plain RAG
cites a later version; opening a row shows the verdict and the commit history with the date asked.

FIRST VIEWPORT: After the intro: top bar (TRACE mark, section links, blue "Ask a question"); left, the
rotating headline in tall condensed capitals with the full form, a one-line description and the
"01 —— 03" counter; right, a rotating circular text badge around the TRACE emblem over a glowing
version-timeline node; below the fold line, the claims dataset begins.

FORM: seed: none (pinned) — the user pinned the world and motion to their reference video ("Copy the
intro animation from the video", "Reframe the overall color palette and its design according the intro
video's theme", "Add a minimalistic hover effects and glass morphisms") and the claim layout to their
dataset-table screenshot. This replaces the Timetable world on this surface.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
