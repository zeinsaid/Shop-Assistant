# Decisions Log

A running record of the significant choices made on this project: what was decided, why, and what it means going forward. New entries go at the bottom. Entries are never deleted; if a decision changes, add a new entry that supersedes the old one and update the old one's status.

**Status values:** `Accepted` (in effect) · `Proposed` (planned, not yet built/tested) · `Superseded by D-XXX`

---

## D-001 — Pilot on The Plug, generic under the hood
**Date:** 2026-09-28 · **Status:** Accepted

**Decision:** Build the assistant for The Plug Business Center (print shop, Nicosia) first, but keep the core business-agnostic so it can later serve any business.

**Why:** A real shop with real customer messages gives honest test data and a live demo. The Plug's traffic is mostly students with small, repeatable jobs, which suits a bot better than large negotiated orders.

**Consequences:** Anything print-specific lives in the knowledge base and config, not in code.

---

## D-002 — Four actions per message
**Date:** 2026-09-28 · **Status:** Accepted

**Decision:** For every incoming message, the brain chooses exactly one action:
- `answer`: reply using the knowledge base
- `ask_owner`: the bot doesn't know, but the owner would; ask them, relay the answer
- `handoff`: needs a human (complaints, refunds, negotiation, anything the owner can't resolve through the bot)
- `no_reply`: the message is a print submission (file or pasted text), not a message to us

**Why:** Keeps the core loop simple, testable and measurable. `no_reply` exists because customers send documents and text to print via WhatsApp, Viber and email.

**Consequences:**
- The brain must first decide whether the customer is talking *to us* or sending *content to print*. Pasted text that contains questions must not be answered.
- Mixed messages (file + question) → answer the question, ignore the file.
- `no_reply` messages are still logged for staff. An optional auto-acknowledgement ("Got it, the team will confirm shortly") will be an owner setting, not hardcoded.

---

## D-003 — Answers must cite the knowledge base
**Date:** 2026-09-28 · **Status:** Accepted

**Decision:** The LLM returns structured output (`action`, `reply`, `cited_entries`, `question_for_owner`). An `answer` is only allowed if it cites at least one knowledge-base entry; otherwise the code forces `ask_owner`.

**Why:** LLM self-reported confidence is unreliable. Requiring citations makes "does the bot know this?" checkable by code, and makes invented answers visible in evaluation.

---

## D-004 — Learning from the owner requires approval
**Date:** 2026-09-28 · **Status:** Accepted

**Decision:** After the owner answers an escalated question, the bot drafts a *general* knowledge entry and asks the owner: **Save / Edit / Just this once**.

**Why:** Owner answers mix general facts ("spiral binding is €2") with one-off quotes ("€18 for this thesis"). Saving everything blindly would fill the knowledge base with junk.

**Consequences:** Prices are stored as rules and ranges, since The Plug's pricing is flexible by job complexity. Knowledge entries carry a date so stale ones can be reviewed.

---

## D-005 — Conversations have explicit states
**Date:** 2026-09-28 · **Status:** Proposed

**Decision:** Each conversation is in one state: `bot_active`, `waiting_on_owner`, `human_handoff`, `closed`. `waiting_on_owner` has a timeout after which the customer is told the bot will follow up when the owner replies.

**Why:** Asking the owner is asynchronous; the owner may take minutes or hours. Without states, the bot can't know whether to speak, wait or stay silent.

---

## D-006 — Multi-business ready in the data model only
**Date:** 2026-09-28 · **Status:** Accepted

**Decision:** Every table has a `business_id` from day one. No other multi-tenant features (accounts, billing, onboarding) until later.

**Why:** Costs nothing now; retrofitting it later is a painful migration.

---

## D-007 — No vector search in v1
**Date:** 2026-09-28 · **Status:** Accepted

**Decision:** The full knowledge base is included in the prompt. Retrieval (embeddings, pgvector) is added only when the knowledge base becomes too large for that.

**Why:** A single shop's knowledge base is small. Building RAG before it's needed adds complexity and new failure modes for no gain.

---

## D-008 — Stack
**Date:** 2026-09-28 · **Status:** Proposed

**Decision:** Python + FastAPI backend, Postgres database, deployed on Railway or Render.

**Why:** Familiar Python AI ecosystem; Postgres covers conversations, messages, escalations and knowledge entries, and supports pgvector later (see D-007).

---

## D-009 — Channels: web chat + Telegram first, one internal message format
**Date:** 2026-09-28 · **Status:** Proposed

**Decision:**
- Customer channel v1: web chat widget on The Plug's website (also serves as the public demo).
- Owner channel v1: Telegram bot.
- WhatsApp, Viber and email come later as separate adapters.
- All channels convert to one internal shape: `channel, sender, text, attachments[]`.

**Why:** Telegram's bot API is free and quick to set up; WhatsApp Business API needs Meta verification and has messaging-window rules. A single internal format means the brain never cares where a message came from.

---

## D-010 — File contents never go to the LLM
**Date:** 2026-09-28 · **Status:** Accepted

**Decision:** For attachments, the brain sees metadata only (type, filename, page count), never the file contents.

**Why:** Customers send theses, CVs and ID copies. Metadata is enough to decide the action; sending contents would cost more and push private documents through a third-party API and into storage.

---

## D-011 — Evaluation set before code
**Date:** 2026-09-28 · **Status:** Accepted

**Decision:** Build `eval/questions.jsonl` (~50 cases, each labelled with `expected_action`) before writing the bot. Sources: real messages from The Plug's WhatsApp (anonymized: names, phone numbers and emails removed) plus deliberately difficult synthetic cases (typos, Greek/English mix, pasted text containing questions, discount manipulation), tagged `"source": "synthetic"`.

**Why:** The eval set is the project's test suite; every prompt change is re-run against it. Key metric: invented answers (should be zero), followed by correct action choice.

**Consequences:** The knowledge base (`kb/the-plug.md`) deliberately leaves some gaps so `ask_owner` behaviour can be tested.

---

## D-012 — Deferred scope
**Date:** 2026-09-28 · **Status:** Accepted

**Decision:** Not in v1: inventory and reordering, supplier price comparison, voice/phone receptionist, admin dashboard for knowledge editing, Greek-language support (English + Greek planned for a later phase).

**Why:** Ship the core loop first; each of these is only worth building on top of a working bot.

---

## Template

```
## D-XXX — Title
**Date:** YYYY-MM-DD · **Status:** Proposed | Accepted | Superseded by D-XXX

**Decision:** What we're doing.

**Why:** The reasoning, including alternatives rejected.

**Consequences:** What this affects or commits us to.
```