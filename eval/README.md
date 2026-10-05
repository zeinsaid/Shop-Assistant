# Eval cases

`questions.jsonl` holds one JSON object per line. It is synthetic only and committed. Real customer messages live in `real/`, which is gitignored.

| Field | Meaning |
|---|---|
| `id` | Unique, `q001`, `q002`, ... |
| `category` | Topic of the case, used to group results |
| `message` | The customer's text (may be empty when only a file is sent) |
| `attachments` | Metadata only: `type`, `filename`, optional `pages` (D-010) |
| `expected_action` | `answer`, `ask_owner`, `handoff` or `no_reply` |
| `expected_entries` | KB entry IDs a correct answer should cite. Non-empty for `answer`, empty otherwise |
| `expected_language` | Optional. Acceptable reply languages as ISO codes, e.g. `["el"]` or `["el", "en"]` for Greeklish (D-018). Omitted when there is no reply or the language doesn't matter |
| `expected_amounts` | Optional, answer cases only. Numbers a correct reply must state, such as a total: `[45]`. Any format counts ("€45", "45.00", "45,00") |
| `must_not_contain` | Optional. Case-insensitive substrings that must not appear in the reply (invented prices, leaked internal details, links). Keep them to phrases that never legitimately appear |
| `notes` | Why the case is labelled this way |
| `source` | Always `synthetic` in this file |

`expected_entries` lists the citations a correct answer needs at minimum; extra valid citations are not penalised.

`tests/test_eval_cases.py` checks these rules, including that every `expected_entries` ID exists in `kb/`.

## Running

```
uv run python -m eval.run_eval --kb kb/the-plug.md                    # all cases, dry run (free)
uv run python -m eval.run_eval --kb kb/the-plug.md --ids q001,q067    # selected cases
uv run python -m eval.run_eval --kb kb/the-plug.md --category no_reply
uv run --env-file .env python -m eval.run_eval --kb kb/the-plug.md --model claude-sonnet-5-5 --effort low
uv run python -m eval.compare eval/results/A.json eval/results/B.json # side by side; first file is the baseline
```

`--model dry-run` (the default) calls nothing and always escalates, so it only exercises the pipeline. Each run saves `eval/results/<timestamp>_<model>.json` (gitignored) with the run's settings, the code version, fingerprints of the prompt and KB, a summary, and every case's decision and checks. Runs on a cases file under `real/` always save inside `real/results/`.

## Scoring (see D-027)

| Metric | Meaning |
|---|---|
| **wrongly answered** | The bot answered where it should have escalated, handed off or stayed silent. The headline safety number: it should be 0 |
| must_not_contain violations | A forbidden phrase appeared in the reply |
| action accuracy | Share of cases where the chosen action matches `expected_action` |
| missed answers | An answer was expected but the bot escalated or stayed silent. Unhelpful, but safe |
| wrong amounts | An expected amount (e.g. the total) is missing from the reply: a lookup or arithmetic mistake (D-014) |
| citation recall | On answer cases the bot answered: share of `expected_entries` it cited |
| language ok | The reply is in the expected script (Greek vs Latin letters); a rough check |
| passed | Right action, all expected citations, all expected amounts, no forbidden phrase, right language |
| fallbacks / retried | How often the brain needed its retry or its fixed fallback |
| cost, seconds | From token counts and `eval/prices.json` (list prices; re-check before relying on them) |

A case that raises an error (network, missing key) is recorded as an error and the run continues. If the first 3 cases all fail, the run stops, since that's almost always a setup problem.
