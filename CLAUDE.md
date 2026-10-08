# CLAUDE.md

Context for Claude Code when working in this repository.

## Project

An AI receptionist for small businesses. It answers customer questions from an owner-maintained knowledge base, asks the owner when it doesn't know, and learns from approved owner answers. First deployment: The Plug Mini Market and Print Shop, a print shop in Nicosia, Cyprus, serving mostly university students.

- `README.md`: overview
- `DECISIONS.md`: every architectural choice and the reasoning behind it. Read it before proposing anything that changes the architecture, and don't contradict an `Accepted` decision without flagging it.

## Current phase

**Phase 1 (done):** knowledge base (`kb/the-plug.md`), labelled eval set (`eval/questions.jsonl`, 114 cases), decisions log.

**Phase 2 (now): the brain.** In order:
1. Output schema (`brain/schema.py`): a Pydantic `BrainDecision` (see D-019, D-020). **Done.**
2. Prompt (`prompts/brain.md`). **Done.**
3. Brain (`brain/brain.py`, `kb.py`, `llm.py`): loads the KB, calls the model, parses the decision, enforces KB-dependent rules in code (D-025). **Done.** Try it with `uv run python -m brain --kb kb/the-plug.md "..."` (dry run by default).
4. Eval runner (`eval/run_eval.py`, `scoring.py`, `compare.py`, `prices.json`): runs every case, scores it (D-027), saves timestamped results; `eval.compare` puts runs side by side. See `eval/README.md`. Clients for Claude, GPT and Gemini are in `brain/llm.py`. **Done.** First live runs on 2026-10-01 (results in D-022).

No backend, database or UI yet. Don't scaffold them unless asked.

**Now:** the KB onboarding interview (D-030). Steps 1-3 are done (`prompts/interview.md`, `onboarding/` with the interview loop and drafting step, `prompts/draft.md`, `prompts/translate_kb.md`). **Baseline done (2026-10-08):** the owner ran the real interview (59 turns, all topics) and two drafts were compared with `kb/the-plug.md`. Fixes went into both prompts: public vs internal (answers need a public entry), `ask_owner` vs `handoff` chosen by what it takes rather than who receives it, keeping tier boundaries, one place per fact, no invented rules or recaps, and closing questions about forgotten services. The last three draft-prompt fixes haven't been checked with a redraft yet; the owner chose not to, since it doesn't have to be perfect. Session and drafts are in `onboarding/sessions/` and `onboarding/drafts/` (gitignored). KB answers from the comparison were applied (name, same-day printing, polite no to discount requests, unusual requests → `handoff`). Not yet in the KB, from the interview: shirt quantity discounts, stamps (€35), sticker prices include printing, annoyed-at-large-format-price → `handoff`. **Priorities (owner, 2026-10-08):** the main bot matters most. It may go live only at The Plug, otherwise it's a portfolio project. For now the owner builds the KBs by hand (doing the interview with any new business personally), so the interview is a nice-to-have and is parked. **Next:** multi-turn (D-023), then per-channel `no_reply` (D-024) and the file-drop skip (D-029). The KB has the shop's real prices (2026-10-05); the working model is GPT-6 Luna at effort `medium` (D-022).

## Product direction (owner, 2026-10-05)

Possibly a product for other small businesses, not only The Plug. Keep design choices compatible with that:
- **Customer side:** an embeddable chat widget or a hosted page per business; channel connectors (WhatsApp, Viber, Telegram) as adapters (D-009).
- **Owner side:** no command lines. A simple backend/dashboard for the KB, the onboarding interview and connectors. CLIs are dev harnesses only, so keep logic in UI-agnostic classes (e.g. `Interview`). This changes D-012 ("no admin dashboard in v1"): propose an update when the backend is designed.
- **Owner and staff notifications:** `ask_owner` and `handoff` don't reach anyone yet. To decide with the backend: likely the owner gets questions on an app they already use (D-009 proposes Telegram) and can reply there, with the dashboard as home base; handoffs land in a shared inbox for staff.

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

- Python, managed with `uv`. Dependencies: `pydantic`, `anthropic`, `openai`, `google-genai`; dev: `pytest`. Run tests with `uv run pytest`.
- Development model: Claude Sonnet 5.5 (`claude-sonnet-5-5`) as the reference. The final model is chosen by the eval among a shortlist from several providers (D-022), so keep the LLM call behind a thin interface.
- Model calls default to `effort="low"`; model and effort are settings to compare in the eval (D-022, D-025).
- Keys for all three providers are in `.env` (about $5 of credit each). **Every live API run needs the owner's OK first**; keep spend low (prefer `--ids` or GPT-6 Luna for rechecks). Everything must still run without a key: `DryRunClient` (free, always escalates) and `ScriptedClient` (prepared responses, for tests) in `brain/llm.py`.

## Layout

- `kb/`: business knowledge bases (markdown, entries with IDs, visibility and status)
- `prompts/`: LLM prompts, kept as files so changes show up in git diffs
- `brain/`: `schema.py` (input and output models), `kb.py` (KB parser), `llm.py` (provider seam and clients), `brain.py` (decision flow), `__main__.py` (CLI)
- `tests/`: pytest tests (schema, KB parser, brain flow, prompt, and sanity checks on the eval file)
- `eval/`: `questions.jsonl` (synthetic, committed), `run_eval.py` (runner), `scoring.py` (checks and summary), `compare.py` (runs side by side), `prices.json` (model prices), and `eval/README.md` (case format, commands, metrics)
- `eval/results/`: run outputs, gitignored because they echo message text. Results of runs on real cases go inside `eval/real/`, never anywhere committed.

## Parked for later

Things agreed but deliberately not done yet. Check this list before starting a new phase.

- **Multi-turn conversations** (D-023, Proposed): add `history` to `IncomingMessage` and write multi-turn eval cases at the start of phase 3.
- **Per-channel `no_reply`** (D-024, Proposed): needed before the website chat goes live.
- **File-drop skip** (D-029, Proposed): build with D-023 and D-024.
- **Price calculator** (D-014): if wrong totals or missed €100 limits keep showing up in the eval (`wrong_amounts`), move price lookup and arithmetic into code as a tool.
- **Final model pick** (D-022): GPT-6 Luna at `medium` is the working choice. Before going live, read a sample of replies by hand (tone, Greek). Check Gemini's output token count against a real bill only if Gemini comes back into consideration.
- **Data protection check** (GDPR, EU data residency, DPA) for the chosen provider, before going live on the website.
- **Go-live KB check:** before going live, add the shop's public WhatsApp/Viber number (one number) and email to `shop-sending-files` (the owner will provide them), and do a final pass over the KB.
- **More `no_reply` variety in the eval**, since most real WhatsApp traffic is file drops (see D-011 update).
- **Business-agnostic review, part 2** (D-026): once there's a working prototype, or a second business in view, revisit whether the actions, the `no_reply` idea, the owner/staff model and the KB format fit other kinds of business.
- **Interview file uploads** (D-030 later option): price spreadsheets and photos in the interview; cost/supplier columns must never reach public entries. Also: check the last three draft-prompt fixes with a redraft.
- **Rename** the local folder and GitHub repo from `Project` to `shop-assistant` (owner does it after ending a session).
