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
- Pleasantries ("thanks!", "bye") are not print submissions. They are answered from the KB entry `shop-greeting`, which covers greetings, thanks and goodbyes. `no_reply` is reserved for material submitted for staff.

---

## D-003 — Answers must cite the knowledge base
**Date:** 2026-09-28 · **Status:** Accepted

**Decision:** The LLM returns structured output (`action`, `reply`, `cited_entries`, `question_for_owner`; extended with `reasoning` by D-019). An `answer` is only allowed if it cites at least one knowledge-base entry; otherwise the code forces `ask_owner`.

**Why:** LLM self-reported confidence is unreliable. Requiring citations makes "does the bot know this?" checkable by code, and makes invented answers visible in evaluation.

---

## D-004 — Learning from the owner requires approval
**Date:** 2026-09-28 · **Status:** Accepted

**Decision:** After the owner answers an escalated question, the bot drafts a *general* knowledge entry and asks the owner: **Save / Edit / Just this once**.

**Why:** Owner answers mix general facts ("spiral binding is €2") with one-off quotes ("€18 for this thesis"). Saving everything blindly would fill the knowledge base with junk.

**Consequences:** Prices are stored as rules and ranges, since The Plug's pricing is flexible by job complexity. Knowledge entries carry a date so stale ones can be reviewed. Until learned entries exist (phase 3), the KB only has a file-level `last_reviewed` date; per-entry dates are added when the first learned entry is created.

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

**Decision:** Build `eval/questions.jsonl` (started at ~50 cases, now 100, each labelled with `expected_action`) before writing the bot. Sources: real messages from The Plug's WhatsApp (anonymized: names, phone numbers and emails removed) plus deliberately difficult synthetic cases (typos, Greek/English mix, pasted text containing questions, discount manipulation), tagged `"source": "synthetic"`.

**Why:** The eval set is the project's test suite; every prompt change is re-run against it. Key metric: invented answers (should be zero), followed by correct action choice.

**Consequences:** The knowledge base (`kb/the-plug.md`) deliberately leaves some gaps so `ask_owner` behaviour can be tested. Cases can also carry machine-checkable rules: `must_not_contain` (phrases that must never appear in the reply) and `expected_language` (see `eval/README.md`), so "invented answers should be zero" can be scored by code.

---

## D-012 — Deferred scope
**Date:** 2026-09-28 · **Status:** Accepted (Greek-language support superseded by D-018)

**Decision:** Not in v1: inventory and reordering, supplier price comparison, voice/phone receptionist, admin dashboard for knowledge editing, Greek-language support (English + Greek planned for a later phase).

**Why:** Ship the core loop first; each of these is only worth building on top of a working bot.

---

## D-013 — Knowledge entries are public or internal
**Date:** 2026-09-28 · **Status:** Accepted

**Decision:** Every KB entry is marked `public` (may be told to customers) or `internal` (guides behaviour, never revealed).

**Why:** Staff deliberately keep some things unsaid: free binding on larger orders is presented as a gift, and supplier details are private. (Outsourcing is not fully secret; see D-021.)

**Consequences:** Internal content never appears in replies. Eval needs cases that try to extract internal info ("do you get binding free if I spend enough?").

---

## D-014 — Pricing: totals for simple jobs, calculator later
**Date:** 2026-09-28 · **Status:** Accepted

**Decision:** The bot gives estimated totals for simple jobs (one service, known quantity, size and colour), asks for missing details when a job is underspecified, and gives ranges for custom work. Once the real price book is in, a deterministic price calculator will be built and exposed to the bot as a tool.

**Why:** Staff routinely quote simple totals, so rates-only replies would be less helpful than a human. But LLM arithmetic is unreliable across tiers and surcharges.

**Consequences:** Eval includes arithmetic cases (tiers, per-page double-sided, paper surcharges, double-sided business cards). Failures there are the evidence for when the calculator becomes a priority.

---

## D-015 — ask_owner vs handoff
**Date:** 2026-09-28 · **Status:** Accepted

**Decision:**
- `ask_owner`: the owner can resolve it with a reply (information or a decision). The bot stays in the conversation and relays the answer. The owner chooses Save / Edit / Just this once (D-004).
- `handoff`: a person needs to take over or physically do something (complaints, refunds, negotiation, checking an order or a lost item). The bot goes silent in that conversation.

**Why:** A clear test for labelling eval cases and for the brain's decision. Keeps the owner from being pulled into full conversations when one reply would do.

**Clarification (D-020):** on the `handoff` turn the bot still sends one short hand-over message. Silence applies from the next message on.

---

## D-016 — Collect details before escalating
**Date:** 2026-09-28 · **Status:** Accepted

**Decision:** For custom or bulk quotes, the bot first asks the customer for the details staff would need anyway (quantity, size, design, colours, sides, paper, deadline), then escalates with those details included.

**Why:** Staff would ask these questions before quoting anyway. Collecting them first means the owner can answer in one reply instead of a back-and-forth.

**Consequences:** Some behaviour spans several turns. The eval set needs multi-turn cases before phase 3.

---

## D-017 — Stationery stock is a separate data source
**Date:** 2026-09-28 · **Status:** Proposed

**Decision:** Stationery availability comes from a stock list exported from the shop's system, kept separate from the knowledge base. Until then, the KB lists stationery categories and the bot says "we usually stock…". Specific brands/models or exact quantities use `ask_owner`.

**Why:** Prices change occasionally; stock changes daily. Mixing them would make the KB go stale quickly.

**Consequences:** Needs a refresh process for the stock list (manual export in v1). Matching must handle loose names ("empty book" → notebook).

---

## D-018 — Reply in the customer's language
**Date:** 2026-09-28 · **Status:** Accepted

**Decision:** The bot replies in the language the customer used (English, Greek, or Greeklish → Greek or English, matching the customer's tone). The KB stays in English.

**Why:** Many customers are Greek-speaking students; modern models translate reliably, so there's no reason to force English. Keeping one KB language avoids maintaining two copies.

**Consequences:** Eval checks the reply language on the Greek and Greeklish cases. Supersedes "Greek support in a later phase" in D-012.

---

## D-019 — Decision schema: reasoning first, shape vs facts
**Date:** 2026-09-28 · **Status:** Accepted

**Decision:** The brain returns a `BrainDecision` with fields in this order: `reasoning`, `action`, `reply`, `cited_entries`, `question_for_owner`. The schema validates internal consistency (e.g. `ask_owner` requires `question_for_owner`, `no_reply` has no reply). Checks that need the KB (cited IDs exist, answers cite at least one entry) live in `brain.py`.

**Why:** Reasoning first makes the model think before choosing an action and makes failed eval cases debuggable. Keeping KB-dependent checks out of the schema keeps it business-agnostic.

**Consequences:** `reasoning` is logged but never shown to customers. Field descriptions are written as instructions to the model, since they become part of the prompt.

---

## D-020 — Schema details: replies on escalation, strictness, input model
**Date:** 2026-09-28 · **Status:** Accepted

**Decision:**
- `ask_owner` and `handoff` both carry a customer-facing `reply`: a short holding message ("let me check and get back to you") and a short hand-over message. `no_reply` has none. `question_for_owner` is required for `ask_owner` and forbidden otherwise.
- `cited_entries` is not restricted by action. An extra citation on a non-answer (for example the internal rule that triggered escalation) is not an error; the eval compares citations on `answer` cases only.
- `Action` is a `StrEnum`; blank strings for `reply` and `question_for_owner` count as null; unknown fields are rejected.
- The brain's input model (`IncomingMessage`: text plus attachment metadata) lives in `brain/schema.py`. `Attachment` has no content field, so D-010 holds by construction.

**Why:** The model writes replies in the customer's language (D-018), so code can't template holding or hand-over messages. Leaving a customer without any response on the handoff turn is worse than a short acknowledgement. Rejecting harmless extras would cost retries for no gain. Models often write `""` instead of null.

**Consequences:** Refines D-015 (see its clarification). When `brain.py` forces an uncited `answer` to `ask_owner` (D-003), it must also produce the holding reply and the question for the owner, either by re-calling the model or building them in code. To be decided in step 3.

---

## D-021 — Outsourcing may be disclosed, but isn't volunteered
**Date:** 2026-09-28 · **Status:** Accepted

**Decision:** Some items (hardcovers, DTF shirt prints) are made with an external partner. The bot never brings this up itself. If a customer asks who makes an item, or why it takes longer or can't be done the same day, it may say so. Partner names, links and prices are never shared, and the bot never claims an outsourced item is made in-house.

**Why:** Staff already explain this when a rush job needs justifying, and dodging or denying a direct question would mean misleading the customer. Volunteering it adds nothing. Alternatives rejected: keeping it fully secret (forces evasive or false answers) and disclosing it freely (noise, and it invites questions about suppliers).

**Consequences:** The KB splits this into a `public` entry stating the fact (`outsourcing`) and `internal` entries telling the bot when it may be said (`hardcover-sourcing`, `merch-shirts-sourcing`). D-013 stays intact: internal entries are still never revealed. Eval covers both directions: `must_not_contain` on unasked cases (q015, q028, q045), and disclosure allowed when asked (q055, q096, q097).

---

## Template

```
## D-XXX — Title
**Date:** YYYY-MM-DD · **Status:** Proposed | Accepted | Superseded by D-XXX

**Decision:** What we're doing.

**Why:** The reasoning, including alternatives rejected.

**Consequences:** What this affects or commits us to.
```
