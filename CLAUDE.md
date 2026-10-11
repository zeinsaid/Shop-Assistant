# CLAUDE.md

Context for Claude Code when working in this repository.

## Project

An AI receptionist for small businesses. It answers customer questions from an owner-maintained knowledge base, asks the owner when it doesn't know, and learns from approved owner answers. First deployment: The Plug Mini Market and Print Shop, a print shop in Nicosia, Cyprus, serving mostly university students.

- `README.md`: overview
- `DECISIONS.md`: every architectural choice and the reasoning behind it. Read it before proposing anything that changes the architecture, and don't contradict an `Accepted` decision without flagging it.

## Current phase

**Phase 1 (done):** knowledge base (`kb/the-plug.md`), labelled eval set (`eval/questions.jsonl`, 130 cases), decisions log.

**Phase 2 (done 2026-10-11): the brain.** In order:
1. Output schema (`brain/schema.py`): a Pydantic `BrainDecision` (see D-019, D-020). **Done.**
2. Prompt (`prompts/brain.md`). **Done.**
3. Brain (`brain/brain.py`, `kb.py`, `llm.py`): loads the KB, calls the model, parses the decision, enforces KB-dependent rules in code (D-025). **Done.** Try it with `uv run python -m brain --kb kb/the-plug.md "..."` (dry run by default).
4. Eval runner (`eval/run_eval.py`, `scoring.py`, `compare.py`, `prices.json`): runs every case, scores it (D-027), saves timestamped results; `eval.compare` puts runs side by side. See `eval/README.md`. Clients for Claude, GPT and Gemini are in `brain/llm.py`. **Done.** First live runs on 2026-10-01 (results in D-022).

**Phase 3 (next): the portfolio demo** (D-031, see "Demo direction" below). Start with a short plan for the owner to approve: server, chat page, decision panel, the demo `ask_owner` flow, spending limits, hosting. No backend, database or UI exists yet; don't scaffold anything before the plan is agreed.

**Priorities (owner, 2026-10-11, D-031):** this is a portfolio project. The bot will be a demo inside the owner's personal portfolio website (CV and other projects alongside it), where visitors click in and chat with it. Keep the demo simple; few visitors will dig deep. Going live at The Plug is possible someday but not planned. Order: finish the bot, then the demo. The interview is parked (maybe a second demo later).

**Multi-turn (D-023), built 2026-10-08:** `history` on `IncomingMessage`, transcript formatting with a 10-turn cap, a prompt section, eval support (`history`, `question_must_contain`) and cases q115-q127. GPT-6 Luna (`medium`) passes them after fixing three labels and one prompt conflict (2026-10-08). Also added: `policy-disputes-and-rudeness` (rude customers, price disputes and complaints → `handoff`). **Per-channel `no_reply` (D-024), built 2026-10-08:** `Brain(allow_no_reply=False)` for channels that always reply; prompt blocks resolved by `render_prompt()`, `no_reply` removed from the schema, `always_reply` overrides on the eval cases and `run_eval --always-reply`. GPT-6 Luna passes the website-mode cases (pasted text gets "here's how to send it", never an answer to its questions). The Plug's website chat won't accept attachments (owner, 2026-10-08). **Finishing the bot (2026-10-11):** D-029 deferred (D-031); the three interview facts added to the KB (shirt quantity discounts, stamps, sticker prices include printing) with eval cases q129-q130; full Luna regression runs in both modes (2026-10-11, about $0.15 in all). After the owner's feedback on hand-picked replies: shirt quotes give only the range and never ask for a print method (`merch-shirts-internal`, `merch-shirts-bulk`), 9+ shirts hand off, listed shirt discounts allowed by `policy-discounts`, students asking for cheaper get told about the large-format discount, in-between business-card quantities get the two neighbouring prices, warmer handoff replies for complaints and price disputes, tier tables summarised instead of listed (prompt). Last run: 127/130 WhatsApp mode, 125/130 website mode; q104 then fixed (4/4 on recheck). Remaining misses look random (q074, q121) or are set aside (q069). The KB has the shop's real prices (2026-10-05); the working model is GPT-6 Luna at effort `medium` (D-022).

**KB onboarding interview (D-030), parked:** steps 1-3 built (`prompts/interview.md`, `prompts/draft.md`, `prompts/translate_kb.md`, `onboarding/`). Baseline done 2026-10-08: the owner ran the real interview (59 turns, all topics), two drafts were compared with `kb/the-plug.md`, and both prompts were fixed (public vs internal, `ask_owner` vs `handoff` by what it takes, tier boundaries, one place per fact, no invented rules or recaps, closing questions about forgotten services). The last three draft-prompt fixes are unchecked by a redraft. Sessions and drafts are in `onboarding/sessions/` and `onboarding/drafts/` (gitignored).

## Demo direction (owner, 2026-10-11, D-031)

After the bot is finished, the next phase is a web demo for the portfolio site, kept simple:
- A chat page on The Plug's KB (always-reply, no attachments).
- A side panel explaining each decision: action, cited KB entries, reasoning.
- A demo `ask_owner` flow: the visitor can play the owner and answer, instead of only being told the question went to the owner.
- Limits that protect the API credit: per-visitor message caps, a provider spending cap, the key kept on the server.

Earlier product ideas (embeddable widget for many businesses, owner dashboard, channel connectors, owner/staff notifications) are deferred. Still keep logic in UI-agnostic classes and nothing business-specific in code, so they stay possible.

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

- **Price calculator** (D-014): if wrong totals or missed €100 limits keep showing up in the eval (`wrong_amounts`), move price lookup and arithmetic into code as a tool. The errors seen are picking the wrong quantity tier, not arithmetic (q126: 50 pages priced at the 51-100 rate). Not needed for the demo; a go-live check.
- **q069** ("can this be ready by 3pm?" with a 20-page PDF), set aside by the owner: small standard jobs are printed on the spot when the customer arrives, so "yes" is true, but staff must know about the promise. Revisit when owner/staff notifications exist; until then the bot may ask for details or `ask_owner`.
- **Final model pick** (D-022): GPT-6 Luna at `medium` is the working choice. Check Gemini's output token count against a real bill only if Gemini comes back into consideration.
- **Second demo: the interview** (D-030): a short mode (fewer topics, 5-10 minutes) on a cheap model. Also: interview file uploads (price spreadsheets, photos; cost/supplier columns must never reach public entries) and a redraft to check the last three draft-prompt fixes.
- **Business-agnostic review, part 2** (D-026): revisit whether the actions, the `no_reply` idea, the owner/staff model and the KB format fit other kinds of business, if a second business comes into view.
- **Only if it goes live** (D-031): file-drop skip (D-029); Telegram owner channel and WhatsApp/Viber/email adapters (D-009); the shop's public WhatsApp/Viber number and email in `shop-sending-files`; a data protection check (GDPR, EU data residency, DPA) for the chosen provider; more `no_reply` variety in the eval.
- **Rename** the local folder and GitHub repo from `Project` to `shop-assistant` (owner does it after ending a session).
