# Labelling claims (Week 8)

File: `claims_labeling.csv` (112 rows). These labels are the ground truth used to measure the entailment
model, so they must be your own judgement. The sheet deliberately shows no model scores.

## The question for each row

> If you only had the `source_text`, would you agree the `claim` is **true according to it**?

Fill `supported` with:

| Value | Use when | Example |
|---|---|---|
| `yes` | The source states the claim, or says something that clearly means it | Source "**Default:** `5173`" + claim "The default of `server.port` is 5173." |
| `no` | The source says something different, or does not say it at all | Same source + claim "The default port is 3000." / "Vite was created by Evan You." |
| `unclear` | You genuinely cannot decide (e.g. the claim is too vague to check) | "It is fast." |

## Rules of thumb

- Judge only against the `source_text` shown, not your own knowledge of Vite, and not whether the claim is
  true today.
- The section heading counts as part of the source: under `server.port`, "**Default:** `5173`" means "the
  default of `server.port` is 5173".
- Formatting does not matter: `` `'modules'` ``, `'modules'` and modules are the same value.
- A claim with several parts is `yes` only if every part is supported.
- Paraphrase is fine ("runs in the main thread" = "does not create any workers").
- Claims that are not self-contained ("Default is true") are judged with the section heading as context.
- Use `note` for anything odd; it helps the error analysis.

## Time

About 20 to 30 seconds per row, 40 to 50 minutes in total. You can stop and continue later; save as CSV
(keep the format and column names) and close Excel before telling me it is done.
