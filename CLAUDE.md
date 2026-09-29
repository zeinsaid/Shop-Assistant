# CLAUDE.md

Context for Claude Code when working in this repository.

## Project

An AI receptionist for small businesses. It answers customer questions from an owner-maintained knowledge base, asks the owner when it doesn't know, and learns from approved owner answers. First deployment: The Plug Business Center, a print shop in Nicosia, Cyprus, serving mostly university students.

- `README.md`: overview
- `DECISIONS.md`: every architectural choice and the reasoning behind it. Read it before proposing anything that changes the architecture, and don't contradict an `Accepted` decision without flagging it.

## Current phase

**Phase 1 (done):** knowledge base (`kb/the-plug.md`), labelled eval set (`eval/questions.jsonl`, 103 cases), decisions log.

**Phase 2 (now): the brain.** In order:
1. Output schema (`brain/schema.py`): a Pydantic `BrainDecision` (see D-019, D-020). **Done.**
2. Prompt (`prompts/brain.md`). **Done.**
3. Brain (`brain/brain.py`, `kb.py`, `llm.py`): loads the KB, calls the model, parses the decision, enforces KB-dependent rules in code (D-025). **Done.** Try it with `uv run python -m brain --kb kb/the-plug.md "..."` (dry run by default).
4. Eval runner (`eval/run_eval.py`): runs every case, scores action accuracy and citation overlap, saves timestamped results for comparing runs

No backend, database or UI yet. Don't scaffold them unless asked.

## Core rules (don't break these)

- Every message gets exactly one action: `answer`, `ask_owner`, `handoff`, `no_reply` (D-002, D-015).
- An `answer` must cite at least one existing KB entry; otherwise code forces `ask_owner`. Never rely on the model's self-reported confidence (D-003).
- KB entries are `public` or `internal`. Internal content guides behaviour but must never appear in a customer reply (D-013).
- Attachments: the brain sees metadata only (type, filename, page count), never file contents (D-010).
- Pasted text meant for printing must not be answered, even if it contains questions (D-002).
- Reply in the customer's language; the KB stays in English (D-018).
- Nothing business-specific in code or `prompts/`; it belongs in `kb/` (entries, or front matter for settings) or config (D-001, D-026). `tests/test_prompt.py` checks the prompt.
- Every future database table carries a `business_id` (D-006).

## Data rules

- Never read, modify, copy or commit anything in `eval/real/`. It contains real customer messages and is gitignored.
- Never commit `.env` or put API keys in code. `.env.example` lists required variables with empty values and is committed.

## Project files: propose first, then change

You may suggest changes to `kb/`, `eval/questions.jsonl`, `DECISIONS.md` and `README.md` whenever you see a reason (a vague KB entry, a mislabelled or missing eval case, a new decision). **Always ask me before editing them.** Show the exact proposed change and why.

- For `DECISIONS.md`, write the full entry ready to paste, using the template at the bottom of the file and the next free number.
- KB and eval labels are linked: when a KB change would flip an eval case's expected action (e.g. `ask_owner` → `answer`), propose both changes together.

## How to work with me

I don't write the code myself; you do. But I want to understand every concept and every line, so:
- Before a step: explain the plan, the concepts involved, and why this approach over the alternatives.
- After writing code: walk me through the important parts. Point out anything worth learning properly (patterns, library features, pitfalls).
- Work one step at a time, in small reviewable changes. Wait for my OK before moving to the next step.
- When there's a real trade-off, give me your recommendation and the reasoning; don't silently pick one.

## Stack

- Python, managed with `uv`. Dependencies: `anthropic`, `pydantic`; dev: `pytest`. Run tests with `uv run pytest`.
- Development model: Claude Sonnet 5 (`claude-sonnet-5`) as the reference. The final model is chosen by the eval among a shortlist from several providers (D-022), so keep the LLM call behind a thin interface.
- Model calls default to `effort="low"`; model and effort are settings to compare in the eval (D-022, D-025).
- The API key isn't set up yet, and won't be until everything can be tested at once. Keep everything runnable without it: `DryRunClient` (free, always escalates) and `ScriptedClient` (prepared responses, for tests) in `brain/llm.py`.

## Layout

- `kb/`: business knowledge bases (markdown, entries with IDs, visibility and status)
- `prompts/`: LLM prompts, kept as files so changes show up in git diffs
- `brain/`: `schema.py` (input and output models), `kb.py` (KB parser), `llm.py` (provider seam and clients), `brain.py` (decision flow), `__main__.py` (CLI)
- `tests/`: pytest tests (schema, KB parser, brain flow, prompt, and sanity checks on the eval file)
- `eval/`: `questions.jsonl` (synthetic, committed), scoring scripts, and `eval/README.md` (case format)
- `eval/results/`: run outputs, gitignored because they echo message text. Results of runs on real cases go inside `eval/real/`, never anywhere committed.

## Parked for later

Things agreed but deliberately not done yet. Check this list before starting a new phase.

- **Fill the KB placeholders** (17+ entries with `Status: placeholder`, including all `details-*` entries): real prices, lamination and passport-photo prices, contact details in `shop-sending-files`, and a banners entry. Then re-check the expected values of the eval cases that depend on them. The owner will do this much later.
- **Multi-turn conversations** (D-023, Proposed): add `history` to `IncomingMessage` and write multi-turn eval cases at the start of phase 3.
- **Per-channel `no_reply`** (D-024, Proposed): needed before the website chat goes live.
- **Model bake-off** (D-022): needs API keys for each shortlisted provider; add `openai` and `google-genai` at step 4.
- **Data protection check** (GDPR, EU data residency, DPA) for the chosen provider, before going live on the website.
- **More `no_reply` variety in the eval**, since most real WhatsApp traffic is file drops (see D-011 update).
- **API key:** the owner adds it to `.env` when it's needed; nothing before step 3 requires it.
- **Business-agnostic review, part 2** (D-026): once there's a working prototype, or a second business in view, revisit whether the actions, the `no_reply` idea, the owner/staff model and the KB format fit other kinds of business.
- **Pending proposal:** add `fallback_reply:` (English + Greek) to the KB front matter. Until then the fallback reply is English only (D-026).
- **Rename** the local folder and GitHub repo from `Project` to `shop-assistant` (owner does it after ending a session).
