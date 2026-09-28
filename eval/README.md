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
| `must_not_contain` | Optional. Case-insensitive substrings that must not appear in the reply (invented prices, leaked internal details, links). Keep them to phrases that never legitimately appear |
| `notes` | Why the case is labelled this way |
| `source` | Always `synthetic` in this file |

`expected_entries` lists the citations a correct answer needs at minimum; extra valid citations are not penalised.

`tests/test_eval_cases.py` checks these rules, including that every `expected_entries` ID exists in `kb/`.

## Results

Run outputs go in `eval/results/` (gitignored). Results of runs on real cases go inside `real/`.
