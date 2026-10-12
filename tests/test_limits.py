from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.limits import HOUR, RateLimiter
from app.main import create_app
from brain.brain import Brain
from brain.llm import ScriptedClient
from tests.test_app import KB, decision

NOON = datetime(2026, 10, 12, 12, tzinfo=timezone.utc).timestamp()


class Clock:
    def __init__(self, now: float = NOON):
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_visitor_limit_is_a_sliding_window():
    clock = Clock()
    limiter = RateLimiter(per_visitor=2, per_day=100, clock=clock)
    assert limiter.check("a") is None
    clock.now += 600
    assert limiter.check("a") is None
    assert "try again in about 50 minutes" in limiter.check("a")
    assert limiter.check("b") is None  # other visitors aren't affected
    clock.now = NOON + HOUR  # the first message has left the window
    assert limiter.check("a") is None


def test_daily_cap_covers_everyone_and_resets_the_next_day():
    clock = Clock()
    limiter = RateLimiter(per_visitor=10, per_day=2, clock=clock)
    assert limiter.check("a") is None
    assert limiter.check("b") is None
    assert "daily limit" in limiter.check("c")
    clock.now += 24 * HOUR
    assert limiter.check("c") is None


def test_refused_messages_dont_count():
    limiter = RateLimiter(per_visitor=1, per_day=1, clock=Clock())
    assert limiter.check("a") is None
    assert limiter.check("a") is not None
    assert limiter.check("a") is not None
    assert limiter._today == 1


def test_api_returns_429_without_calling_the_model():
    client = ScriptedClient([decision()])
    limiter = RateLimiter(per_visitor=1, per_day=100, clock=Clock())
    api = TestClient(create_app(Brain(KB, client, prompt="Test.", allow_no_reply=False), limiter))
    assert api.post("/api/chat", json={"message": "hi"}).status_code == 200
    response = api.post("/api/chat", json={"message": "hi again"})
    assert response.status_code == 429
    assert "try again" in response.json()["detail"]
    assert len(client.calls) == 1


def test_invalid_requests_dont_use_up_the_limit():
    client = ScriptedClient([decision()])
    limiter = RateLimiter(per_visitor=1, per_day=100, clock=Clock())
    api = TestClient(create_app(Brain(KB, client, prompt="Test.", allow_no_reply=False), limiter))
    assert api.post("/api/chat", json={"message": ""}).status_code == 422
    assert api.post("/api/chat", json={"message": "hi"}).status_code == 200
