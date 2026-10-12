"""The web demo's server (D-031): one endpoint that runs the brain on a visitor's message.

    uv run uvicorn app.main:app --reload                                  # free: dry run
    DEMO_MODEL=gpt-6-luna uv run --env-file .env uvicorn app.main:app     # real model (costs money)

Stateless: the page sends the conversation so far with every message, so the server stores nothing.
Visitors only ever see what a customer could see, plus the public entries the bot relied on.
The model's reasoning and internal entries never leave the server (owner, 2026-10-11).
"""

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from brain.brain import Brain
from brain.kb import KnowledgeBase, load_kb
from brain.llm import make_client
from brain.schema import Action, IncomingMessage, Turn

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"  # the chat page

MAX_MESSAGE_CHARS = 500  # longer messages cost more and aren't needed to try the bot
MAX_HISTORY_TURNS = 40  # the brain only reads the last 10 (D-023); this just bounds the request size

log = logging.getLogger("demo")


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    history: list[Turn] = Field(default_factory=list, max_length=MAX_HISTORY_TURNS)


class Source(BaseModel):
    """A public knowledge-base entry the reply relied on, shown in the decision panel."""

    id: str
    text: str


class ChatResponse(BaseModel):
    action: Action
    reply: str
    question_for_owner: str | None
    sources: list[Source]
    internal_rules_used: int  # how many internal entries were cited; their IDs and text stay hidden


def create_app(brain: Brain) -> FastAPI:
    """Build the app around a brain. Tests pass one with a ScriptedClient; production uses from_env()."""
    app = FastAPI(title="Shop Assistant demo", docs_url=None, redoc_url=None)

    # A plain `def` (not `async def`): brain.decide() waits on the model's API, and FastAPI runs
    # plain functions in a thread pool, so one slow call doesn't block other visitors.
    @app.post("/api/chat")
    def chat(request: ChatRequest) -> ChatResponse:
        message = IncomingMessage(text=request.message, history=request.history)
        try:
            result = brain.decide(message)
        except Exception:
            # Provider errors propagate from the brain (D-025). Log the details, show a plain message.
            log.exception("brain.decide failed")
            raise HTTPException(503, "The assistant is unavailable right now. Please try again in a minute.")
        return to_response(result.decision, brain.kb)

    # The page calls this on load: on free hosting that sleeps, it's what wakes the server up.
    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    # Everything else is the chat page and its files. Mounted last, so the /api routes above win.
    app.mount("/", StaticFiles(directory=STATIC, html=True), name="page")

    return app


def to_response(decision, kb: KnowledgeBase) -> ChatResponse:
    """Keep only what a visitor may see: the reply, the question for the owner, and public entries."""
    public = [c for c in decision.cited_entries if kb.is_public(c)]
    return ChatResponse(
        action=decision.action,
        reply=decision.reply,
        question_for_owner=decision.question_for_owner,
        sources=[Source(id=c, text=kb.entries[c].text) for c in public],
        internal_rules_used=len(decision.cited_entries) - len(public),
    )


def from_env() -> FastAPI:
    """Settings come from environment variables, so the host's dashboard can set them.

    DEMO_MODEL defaults to dry-run: running the server locally never costs money by accident.
    """
    kb = load_kb(os.environ.get("DEMO_KB", ROOT / "kb" / "the-plug.md"))
    client = make_client(os.environ.get("DEMO_MODEL", "dry-run"), effort=os.environ.get("DEMO_EFFORT", "medium"))
    # A website chat: every message gets a reply (D-024).
    return create_app(Brain(kb, client, allow_no_reply=False))


app = from_env()
