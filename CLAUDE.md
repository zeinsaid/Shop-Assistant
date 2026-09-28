# CLAUDE.md

Context for Claude Code when working in this repository.

## Project

An AI receptionist for small businesses. It answers customer questions from an owner-maintained knowledge base, asks the owner when it doesn't know, and learns from approved owner answers. First deployment: The Plug Business Center, a print shop in Nicosia serving mostly students.

Read `README.md` for the overview and `DECISIONS.md` for every architectural choice and the reasoning behind it. Check `DECISIONS.md` before proposing anything that changes the architecture.

## Current phase

Phase 1–2: building the evaluation set and the "brain" (knowledge base + prompt + structured output), tested against `eval/`. There is no backend, database or UI yet. Don't scaffold them unless asked.

## Core rules (don't break these)

- Every message gets exactly one action: `answer`, `ask_owner`, `handoff`, `no_reply`.
- An `answer` must cite knowledge-base entries; if it can't, the code forces `ask_owner`. Never rely on the model's self-reported confidence.
- Attachments: the brain sees metadata only (type, filename, page count), never file contents.
- Nothing print-specific in code; it belongs in `kb/` or config.
- Every future database table carries a `business_id`.

## Data rules

- Never read, modify, copy or commit anything in `eval/real/`. It contains real customer messages and is gitignored.
- Never commit `.env` or put API keys in code.

## Layout

- `kb/`: business knowledge bases (markdown)
- `prompts/`: LLM prompts, kept as files so changes show up in git diffs
- `eval/`: evaluation cases (`questions.jsonl`, synthetic only) and scoring scripts

## How to work with me

I'm building this to learn, not just to ship. So:
- Explain what you're about to do and why before making non-trivial changes.
- Prefer small, reviewable changes over large generated files.
- When there are real design trade-offs, tell me the options and your recommendation instead of silently picking one.
- If a change amounts to a new architectural decision, draft a `DECISIONS.md` entry for it.

## Stack

Python, managed with `uv`. Planned later: FastAPI, Postgres, Telegram Bot API.
