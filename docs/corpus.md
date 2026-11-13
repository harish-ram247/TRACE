# Corpus

**Status: chosen: Vite documentation** (decided 2026-11-13, plan open decision O1). Details in
[Chosen corpus](#chosen-corpus).

## Selection criteria

- Permissive license that allows copying, modifying and displaying the text (verify before use).
- Long first-parent history with frequent factual changes (limits, defaults, version numbers, names).
- Mostly markdown, with a manageable number of files.
- Public, so results can be reproduced.

## Candidates measured (2026-11-13)

All four were cloned without checkout and ingested with `python -m app.ingest --path <docs path>`.
Metadata is from the GitHub API at that date. "Numeric change" means two consecutive versions of a
section whose sets of numbers differ: a rough proxy for a factual change that also counts some noise.

| | vitejs/vite | prometheus/docs | fastapi/fastapi | traefik/traefik |
|---|---|---|---|---|
| License (repo) | MIT | Apache-2.0 | MIT | MIT |
| Docs path ingested | `docs/` | `docs/` | `docs/en/docs/` | `docs/content/` |
| Clone size | ~80 MB | ~43 MB | ~55 MB | not measured |
| Ingest status | complete | complete | **partial** (1046 of 4576 commits) | **partial** (194 of 555 commits) |
| Ingest time | ~6 min | ~1.5 min | stopped after ~25 min | stopped after ~25 min |
| History covered | 2020-12 to 2026-11 | 2025-05 to 2026-11 | 2020-03 to 2022-09 | 2019-02 to 2021-06 |
| Documents | 60 | 72 | 105 | 143 |
| Chunk versions | 3368 | 2303 | 3025 | 4271 |
| Lineages with 2+ versions | 656 | 742 | 652 | 897 |
| Lineages with a numeric change | 173 | 92 | 335 | 206 |
| Lineages with 2+ numeric changes | 72 | 17 | 178 | 68 |
| Numeric transitions | 330 | 126 | 1113 | 438 |
| Quality of sampled changes | Mostly factual: Node version requirements, defaults, config values | Mostly factual but short history | Noisy: dominated by the Release Notes page (PR numbers, versions) | Noisy: timestamps, shifting `[part N]` chunks |

## Observations

- Numbers from the two partial ingests are lower bounds for their full history, and are not directly
  comparable with the complete ones.
- Prometheus docs history only starts in 2025-05, which is a short span for "as of" questions.
- FastAPI's raw counts are inflated by `release-notes.md`; excluding that file would make it a
  stronger candidate, but that was not re-run.
- Large sections are slow: the similarity pass in `lineage.py` is the likely cost (about 5 commits
  per second on vite versus roughly 1 per second on the large traefik and fastapi files, with two
  ingests running in parallel).

## Chosen corpus

| Field | Value |
|---|---|
| Repository URL | https://github.com/vitejs/vite (`repo_id` in the database is this URL) |
| License | MIT, from the repository's root `LICENSE` ("Copyright (c) 2019-present, VoidZero Inc. and Vite contributors"). No separate license file under `docs/`. Keep the attribution in the README |
| Pinned commit | `4db98449a802abd67a6975fb4fdf260fa8f82979` (2026-11-13) |
| Commit range | Full first-parent history up to the pinned commit |
| Paths | `docs/` excluding `docs/blog/` (blog posts are dated announcements, not living documentation) |
| Size | 1688 commits touching those paths (1329 with markdown changes); 3142 chunk versions |
| Local clone | `data/corpus/vite` (git-ignored, cloned with `--no-checkout`) |
| Why chosen | Longest complete history of the candidates (2020-12 to 2026-11), changes are mostly factual (defaults, ports, Node requirements, minifiers), English only, permissive license |

Ingest exactly this state with:

```bash
git clone --no-checkout https://github.com/vitejs/vite.git data/corpus/vite
python -m app.ingest --repo data/corpus/vite --repo-id https://github.com/vitejs/vite \
  --until 4db98449a802abd67a6975fb4fdf260fa8f82979 --path docs/ --path ":(exclude)docs/blog/" --check
python -m app.retrieval.backfill --repo-id https://github.com/vitejs/vite
```

Known quirk: in 2022 the single `docs/config/index.md` was split into one file per option group, so a
config option's history is split across two lineages (old file and new file). Gold labels therefore
name the file and section valid at the as-of date.

## Reproducing the measurements

```bash
git clone --no-checkout https://github.com/vitejs/vite.git
python -m app.ingest --repo vite --repo-id cand/vitejs/vite --path docs/ --check
python -m scripts.corpus_stats cand/vitejs/vite
```

Candidate data is stored under `repo_url` values starting with `cand/`; delete it with
`DELETE FROM documents WHERE repo_url LIKE 'cand/%'` once a corpus is chosen.
