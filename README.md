# Shop Assistant

An AI receptionist for small businesses. It answers customer questions from a knowledge base the owner maintains, asks the owner when it doesn't know something, and learns from the owner's answers so it doesn't have to ask twice.

The first deployment is The Plug Business Center, a print shop next to the University of Nicosia, Cyprus. Most of its customers are students asking about small print jobs over chat. The core is business-agnostic: everything print-specific lives in the knowledge base and config, not in code.

> **Status:** Early development. Architecture and evaluation set in progress; no runnable code yet.

---

## How it works

Every incoming customer message gets exactly one of four actions:

| Action | When | What happens |
|---|---|---|
| `answer` | The knowledge base covers it | The bot replies, citing the knowledge entries it used |
| `ask_owner` | The bot doesn't know, but the owner would | The owner is asked, the answer is relayed to the customer, and the owner can save it as new knowledge |
| `handoff` | Needs a human (complaints, refunds, negotiation) | The conversation is transferred to staff and the bot stays silent |
| `no_reply` | The message is a print submission (a file or pasted text), not a question | Logged for staff; the bot doesn't respond |

Three rules keep this reliable:

- **Answers must cite the knowledge base.** If the model can't point to an entry supporting its answer, the code forces `ask_owner` instead. The bot is never trusted to judge its own confidence.
- **Learning requires owner approval.** After answering an escalated question, the owner chooses to save it as a general entry, edit it first, or treat it as a one-off. This keeps one-off quotes out of the knowledge base.
- **File contents never reach the model.** For attachments the bot sees only metadata (type, filename, page count). Customers send private documents; the bot doesn't need to read them to decide what to do.

## Roadmap

1. **Evaluation set:** ~50 labelled customer messages (real, anonymized, plus hard synthetic cases) to measure the bot against.
2. **The brain:** knowledge base + prompt + structured output, tested against the evaluation set. No UI.
3. **The loop:** backend, database, conversation states, and the owner channel (Telegram), including approve-and-save learning.
4. **Ship it:** web chat widget live on The Plug's website.
5. **Grow it:** knowledge-base admin page, WhatsApp / Viber / email, English + Greek, support for other businesses.

## Planned stack

Python · FastAPI · Postgres · Telegram Bot API (owner channel) · web chat widget (customer channel) · Railway or Render for hosting

## Repository layout (planned)

```
├── DECISIONS.md      # Log of architecture decisions and the reasoning behind them
├── kb/               # Business knowledge bases (markdown)
├── eval/             # Evaluation cases and scoring scripts
└── app/              # Backend (coming in phase 3)
```

## Design decisions

Every significant choice, and why it was made, is recorded in [DECISIONS.md](DECISIONS.md).

## Data and privacy

Real customer messages are anonymized (names, phone numbers and emails removed) and are not committed to this repository. Committed evaluation cases are synthetic or fully rewritten.