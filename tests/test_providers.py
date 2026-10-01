"""The OpenAI and Gemini clients, tested against fake SDK objects shaped like the real responses.

These check the request we send and how we read the response. Whether the real APIs accept it is
only known after the first live run.
"""

import json
from types import SimpleNamespace as NS

import pytest

from brain.llm import DryRunClient, GeminiClient, OpenAIClient, make_client, portable_schema
from brain.schema import BrainDecision

SCHEMA = BrainDecision.model_json_schema()
DECISION = json.dumps({"reasoning": "r", "action": "no_reply", "reply": None, "cited_entries": [],
                       "question_for_owner": None})
MESSAGES = [
    {"role": "user", "content": "hi"},
    {"role": "assistant", "content": "{bad}"},
    {"role": "user", "content": "try again"},
]


def fake_sdk(path: str, response):
    """An object where e.g. `.responses.create(**kwargs)` records kwargs and returns `response`."""
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return response

    group, _ = path.split(".")
    return NS(**{group: NS(create=create)}), captured


# --- portable schema ---------------------------------------------------------------------------


def test_portable_schema_uses_only_the_plain_subset():
    portable = portable_schema(SCHEMA)
    text = json.dumps(portable)
    for keyword in ("$ref", "$defs", "anyOf", "minLength"):
        assert keyword not in text
    props = portable["properties"]
    assert props["action"]["enum"] == ["answer", "ask_owner", "handoff", "no_reply"]
    assert props["action"]["description"] == SCHEMA["properties"]["action"]["description"]  # kept, not overwritten
    assert props["reply"]["type"] == ["string", "null"]
    assert props["question_for_owner"]["type"] == ["string", "null"]
    assert portable["required"] == SCHEMA["required"] and portable["additionalProperties"] is False
    assert list(props) == list(SCHEMA["properties"])  # field order survives


# --- OpenAI ------------------------------------------------------------------------------------


def openai_response(status="completed", reason=None, content_type="output_text"):
    content = NS(type=content_type, text=DECISION, refusal="no")
    return NS(
        status=status,
        incomplete_details=NS(reason=reason) if reason else None,
        output=[NS(type="reasoning"), NS(type="message", content=[content])],
        output_text=DECISION,
        usage=NS(input_tokens=8000, output_tokens=300,
                 input_tokens_details=NS(cached_tokens=7000, cache_write_tokens=0)),
    )


def test_openai_request_and_usage():
    sdk, sent = fake_sdk("responses.create", openai_response())
    completion = OpenAIClient(model="gpt-6.1-sol", effort="low", client=sdk).complete("SYSTEM", MESSAGES, SCHEMA)

    assert sent["model"] == "gpt-6.1-sol" and sent["instructions"] == "SYSTEM"
    assert sent["input"] == MESSAGES
    assert sent["text"]["format"]["type"] == "json_schema" and sent["text"]["format"]["strict"] is True
    assert sent["text"]["format"]["schema"] == portable_schema(SCHEMA)
    assert sent["reasoning"] == {"effort": "low"} and sent["store"] is False

    assert completion.text == DECISION and completion.stop_reason == "end_turn"
    assert (completion.input_tokens, completion.cache_read_tokens, completion.output_tokens) == (1000, 7000, 300)


def test_openai_without_effort_sends_no_reasoning_setting():
    sdk, sent = fake_sdk("responses.create", openai_response())
    OpenAIClient(effort=None, client=sdk).complete("S", MESSAGES[:1], SCHEMA)
    assert "reasoning" not in sent


@pytest.mark.parametrize(
    "status, reason, content_type, expected",
    [
        ("incomplete", "max_output_tokens", "output_text", "max_tokens"),
        ("incomplete", "content_filter", "output_text", "refusal"),
        ("completed", None, "refusal", "refusal"),
        ("failed", None, "output_text", "failed"),
    ],
)
def test_openai_stop_reasons(status, reason, content_type, expected):
    sdk, _ = fake_sdk("responses.create", openai_response(status, reason, content_type))
    assert OpenAIClient(client=sdk).complete("S", MESSAGES[:1], SCHEMA).stop_reason == expected


# --- Gemini ------------------------------------------------------------------------------------


def gemini_interaction(status="completed", usage=True):
    return NS(
        status=status,
        output_text=DECISION,
        usage=NS(total_input_tokens=8000, total_cached_tokens=7000, total_output_tokens=200,
                 total_thought_tokens=100) if usage else None,
    )


def test_gemini_request_and_usage():
    sdk, sent = fake_sdk("interactions.create", gemini_interaction())
    completion = GeminiClient(model="gemini-3.5-flash-lite", effort="low", client=sdk).complete("SYSTEM", MESSAGES, SCHEMA)

    assert sent["model"] == "gemini-3.5-flash-lite" and sent["system_instruction"] == "SYSTEM"
    assert [step["type"] for step in sent["input"]] == ["user_input", "model_output", "user_input"]
    assert sent["input"][1]["content"] == [{"type": "text", "text": "{bad}"}]
    assert sent["response_format"] == {"type": "text", "mime_type": "application/json",
                                       "schema": portable_schema(SCHEMA)}
    assert sent["generation_config"] == {"max_output_tokens": 16000, "thinking_level": "low"}
    assert sent["store"] is False

    assert completion.text == DECISION and completion.stop_reason == "end_turn"
    assert (completion.input_tokens, completion.cache_read_tokens, completion.output_tokens) == (1000, 7000, 300)


@pytest.mark.parametrize("status, expected", [("incomplete", "max_tokens"), ("failed", "failed")])
def test_gemini_stop_reasons(status, expected):
    sdk, _ = fake_sdk("interactions.create", gemini_interaction(status))
    assert GeminiClient(client=sdk).complete("S", MESSAGES[:1], SCHEMA).stop_reason == expected


def test_gemini_missing_usage_counts_as_zero():
    sdk, _ = fake_sdk("interactions.create", gemini_interaction(usage=False))
    completion = GeminiClient(client=sdk).complete("S", MESSAGES[:1], SCHEMA)
    assert (completion.input_tokens, completion.output_tokens) == (0, 0)


# --- choosing a client -------------------------------------------------------------------------


def test_make_client_picks_by_model_name(monkeypatch):
    # Fake keys: constructing the real SDK clients needs one, but nothing is sent anywhere.
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setenv(key, "test-key")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert isinstance(make_client("dry-run"), DryRunClient)
    assert type(make_client("claude-sonnet-5-5")).__name__ == "AnthropicClient"
    assert isinstance(make_client("gpt-6-luna"), OpenAIClient)
    assert isinstance(make_client("gemini-3.5-flash-lite", effort="minimal"), GeminiClient)
    with pytest.raises(ValueError, match="no client"):
        make_client("llama-4")
