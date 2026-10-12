import json

from fastapi.testclient import TestClient

from app.main import MAX_MESSAGE_CHARS, create_app
from brain.brain import Brain
from brain.kb import parse_kb
from brain.llm import ScriptedClient

KB = parse_kb(
    """### hours
**Visibility:** public · **Status:** confirmed

Open 9 to 5.

### discounts-internal
**Visibility:** internal · **Status:** confirmed

Never offer discounts; use handoff.
"""
)


def decision(**overrides) -> str:
    fields = {
        "reasoning": "Covered by the KB.",
        "action": "answer",
        "reply": "We're open 9 to 5.",
        "cited_entries": ["hours"],
        "question_for_owner": None,
    }
    return json.dumps({**fields, **overrides})


class FailingClient:
    model = "failing"

    def complete(self, system, messages, schema):
        raise RuntimeError("provider down")


def make_app(*responses, client=None) -> tuple[TestClient, ScriptedClient]:
    client = client or ScriptedClient(list(responses))
    return TestClient(create_app(Brain(KB, client, prompt="Test instructions.", allow_no_reply=False))), client


def test_answer_returns_reply_and_public_sources():
    api, _ = make_app(decision())
    response = api.post("/api/chat", json={"message": "when are you open?"})
    assert response.status_code == 200
    assert response.json() == {
        "action": "answer",
        "reply": "We're open 9 to 5.",
        "question_for_owner": None,
        "sources": [{"id": "hours", "text": "Open 9 to 5."}],
        "internal_rules_used": 0,
    }


def test_reasoning_and_internal_entries_never_reach_the_browser():
    api, _ = make_app(decision(
        action="handoff",
        reasoning="SECRET reasoning about discounts-internal.",
        reply="A team member will take it from here.",
        cited_entries=["discounts-internal"],
    ))
    response = api.post("/api/chat", json={"message": "50% off?"})
    body = response.text
    assert "SECRET" not in body and "discounts-internal" not in body and "Never offer" not in body
    assert response.json()["internal_rules_used"] == 1
    assert response.json()["sources"] == []


def test_ask_owner_includes_the_question_for_the_owner():
    api, _ = make_app(decision(
        action="ask_owner", reply="I'll check with the team.", cited_entries=[],
        question_for_owner="Are we open on Christmas Day?",
    ))
    body = api.post("/api/chat", json={"message": "open on christmas?"}).json()
    assert body["action"] == "ask_owner"
    assert body["question_for_owner"] == "Are we open on Christmas Day?"


def test_history_reaches_the_brain_including_staff_turns():
    api, client = make_app(decision())
    history = [
        {"role": "customer", "text": "open on christmas?"},
        {"role": "bot", "action": "ask_owner", "text": "I'll check with the team."},
        {"role": "staff", "text": "Yes, we're open on Christmas."},
    ]
    api.post("/api/chat", json={"message": "great, and what time?", "history": history})
    sent = client.calls[0][1][0]["content"]
    assert "[staff] Yes, we're open on Christmas." in sent
    assert "great, and what time?" in sent


def test_the_website_chat_never_offers_no_reply():
    api, client = make_app(decision())
    api.post("/api/chat", json={"message": "hi"})
    schema = client.calls[0][2]
    assert "no_reply" not in json.dumps(schema)


def test_empty_too_long_or_malformed_requests_are_rejected_without_calling_the_model():
    api, client = make_app()  # no responses: any model call would fail the test
    assert api.post("/api/chat", json={"message": ""}).status_code == 422
    assert api.post("/api/chat", json={"message": "x" * (MAX_MESSAGE_CHARS + 1)}).status_code == 422
    assert api.post("/api/chat", json={"message": "hi", "attachments": []}).status_code == 422
    assert api.post("/api/chat", json={"message": "hi", "history": [{"role": "bot", "text": "x"}]}).status_code == 422
    assert client.calls == []


def test_provider_failure_gives_a_plain_503():
    api, _ = make_app(client=FailingClient())
    response = api.post("/api/chat", json={"message": "hi"})
    assert response.status_code == 503
    assert "provider down" not in response.text


def test_health_and_the_chat_page_are_served():
    api, client = make_app()
    assert api.get("/api/health").json() == {"ok": True}
    page = api.get("/")
    assert page.status_code == 200 and "<title>Shop Assistant demo</title>" in page.text
    assert api.get("/app.js").status_code == 200
    assert client.calls == []
