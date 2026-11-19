# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: recruiters and HR reviewers who open the demo from the author's resume or portfolio. They
are not RAG specialists, give the page about a minute, and must understand what TRACE does and see it
work without reading documentation. Secondary: engineers interviewing the author, who open sources,
validity dates, claim checks and section history to probe the system.

## Product Purpose

TRACE (Temporal Retrieval with Attributed Claim Evidence) answers questions about documentation as it
was on a given date. It retrieves only the version of each section that was valid then, cites it with
its validity interval, and checks every claim against the cited source. Success for the demo: a
reviewer sees, within seconds, that TRACE gives the right answer for a past date where plain RAG gives
a stale or mixed one.

## Positioning

Ordinary RAG searches every version of a document at once and can mix old and new facts. TRACE models
time explicitly: every section version carries a validity interval taken from git history, retrieval
is filtered to the date asked, and claims are verified against sources valid on that date.

## Operating Context

A public Streamlit demo (ui/app.py) in front of a FastAPI backend (/ask, /chunks, /lineages) on
PostgreSQL + pgvector. Answers come from a free-tier Gemini model, so live answers can take seconds
and occasionally fail; responses are cached. Visitors arrive cold from a link, often on a laptop,
sometimes on a phone.

## Capabilities and Constraints

- Corpus: the official Vite documentation (`docs/` of github.com/vitejs/vite, blog excluded), full
  main-branch history Dec 2020 to the pinned commit of 2026-11-13. Answers only from these docs;
  NOT_FOUND when they do not say.
- Date comes from a slider or from the question ("before Vite 3", "in March 2022").
- Variants: TRACE, TRACE + claim verification, plain RAG baseline for comparison.
- Each answer shows cited sources with validity intervals, claim verdicts (supported on that date,
  supported only by an outdated source, unsupported) and a section's full version history.
- Front end stays on Streamlit (decided 2026-11-18); restyling only, same features and API calls.
- On load the page shows one finished example answer (cached) so the comparison is visible before
  the visitor types (decided 2026-11-18).

## Brand Commitments

Name: TRACE, always with its expansion "Temporal Retrieval with Attributed Claim Evidence". Corpus
attribution required: Vite documentation, MIT License, © VoidZero Inc. and Vite contributors.

## Evidence on Hand

Dev-split evaluation (docs/devlog.md, results/): temporal accuracy 0.76 for TRACE vs 0.38 for plain
RAG; faithful-but-stale claims 0.57 for plain RAG vs 0.00 for TRACE. The held-out test split has not
been run; no test-split numbers may be shown. No users, testimonials or deployment metrics exist.

## Product Principles

- Show the mechanism working before explaining it.
- Every answer is traceable: source, validity dates, and claim verdict are always one step away.
- Refuse rather than guess; NOT_FOUND is a correct outcome, not an error.
- Honest numbers only, with their scope (dev split) stated.
