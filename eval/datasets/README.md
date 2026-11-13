# Evaluation datasets

| File | What it is |
|---|---|
| `retrieval_smoke.jsonl` | 20 hand-written retrieval checks (Week 3), used only as a development sanity check |
| `questions_candidates.jsonl` | Generated question candidates (`python -m scripts.build_questions`) |
| `review/questions_review.csv` | The same candidates as a sheet for human review |
| `questions_v1.jsonl` | The frozen, reviewed evaluation set (`python -m scripts.finalize_questions`) |

## How candidates are made

Facts are mined from the versioned chunks: documented config defaults (`**Default:**` lines) and the
Node.js requirement. Gold answers are the documentation's own text valid on the question's date; no
LLM writes them. Dates sit at least 14 days inside a value's validity period. "now" is fixed to the
corpus pin (2026-11-13) so results do not drift.

Automatic checks already applied (shown in the `flags` column):

- `verified_absent`: for unanswerable questions, no document valid on that date mentions the option.
- `gold_not_in_source` / `gold_section_not_valid_at_as_of`: the gold value is missing from its source
  (none at the moment).
- `parser_as_of=...`: the temporal parser resolves the question to a different date (none at the moment).
- `short_value`: the answer is `true`, `false`, `0`, `[]` or similar. Token matching is fragile here.
- `stale_undetectable`: the old and new values share all tokens, so a stale answer cannot be detected.
- `change_question`: answered as a normal question for now (change answers are a stretch goal).

## How to review

Open `review/questions_review.csv` in Excel or a spreadsheet tool. For each row, fill `decision`:

- `accept`: question is clear, gold answer matches the evidence, the date makes sense.
- `edit`: fix the `question`, `gold_answer`, `gold_tokens` or `stale_tokens` cells directly (tokens are
  separated by ` | `), and say what you changed in `note`.
- `reject`: write the reason in `note`, for example "ambiguous", "evidence does not support gold",
  "unnatural question".

Things to check:

1. Does the `evidence` text support `gold_answer` for that `as_of` date?
2. Would a reasonable person ask this question, and is it unambiguous?
3. For `unanswerable` rows: is it fair that the answer is "not documented then"?
4. For `short_value` rows: could a correct answer accidentally contain a stale token, or the reverse?

The `suggested` and `why` columns are a first pass by the assistant. They are not decisions: either
fill `decision` for every row, or fill it only where you disagree and finalize with
`--use-suggestions` (those rows are recorded as `suggestion_confirmed`).

Then save the CSV (keep the CSV format and the column names) and run:

```bash
python -m scripts.finalize_questions
```

It refuses to run while rows are undecided, and prints the rejection rate (report it). After
results have been computed on `questions_v1.jsonl`, do not change it: fix errors in a v2 and record
why in `docs/devlog.md`.
