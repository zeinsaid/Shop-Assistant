"""The onboarding interview (D-030), tested with scripted model responses: no API key needed."""

import json
import re

import pytest

from brain.llm import ScriptedClient
from onboarding.interview import OPENING, PROMPT_PATH, Interview, InterviewError
from onboarding.schema import InterviewTurn, Topic


def turn(message="Tell me about your business.", covered=(), done=False) -> str:
    return json.dumps({"message": message, "covered": list(covered), "done": done})


def test_opening_question_comes_from_the_model():
    client = ScriptedClient([turn("Hi! What does your business do?")])
    interview = Interview(client)
    assert interview.start() == "Hi! What does your business do?"
    _, messages, schema = client.calls[0]
    assert messages == [{"role": "user", "content": OPENING}]
    assert schema == InterviewTurn.model_json_schema()


def test_transcript_alternates_owner_and_interviewer():
    client = ScriptedClient([turn("Q1"), turn("Q2")])
    interview = Interview(client)
    interview.start()
    interview.reply("We run a bakery.")
    _, messages, _ = client.calls[1]
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert messages[-1]["content"] == "We run a bakery."
    assert [t["role"] for t in interview.transcript] == ["interviewer", "owner", "interviewer"]


def test_coverage_only_grows():
    client = ScriptedClient([turn(covered=["basics", "hours"]), turn(covered=["prices"])])
    interview = Interview(client)
    interview.start()
    interview.reply("answer")
    assert interview.covered == {Topic.BASICS, Topic.HOURS, Topic.PRICES}
    assert Topic.STYLE in interview.remaining


def test_done_ends_the_interview():
    client = ScriptedClient([turn("Summary... is that right?"), turn("Thanks!", covered=list(Topic), done=True)])
    interview = Interview(client)
    interview.start()
    interview.reply("Yes, that's right.")
    assert interview.done
    with pytest.raises(InterviewError):
        interview.reply("one more thing")


def test_invalid_turn_gets_one_corrective_retry():
    client = ScriptedClient(["not json", turn("Q1")])
    assert Interview(client).start() == "Q1"
    _, retry_messages, _ = client.calls[1]
    assert retry_messages[-1]["role"] == "user" and "not accepted" in retry_messages[-1]["content"]


def test_two_invalid_turns_raise():
    client = ScriptedClient(["not json", json.dumps({"message": "", "covered": [], "done": False})])
    with pytest.raises(InterviewError):
        Interview(client).start()


def test_unknown_topic_is_rejected():
    client = ScriptedClient([turn(covered=["weather"]), turn(covered=["basics"])])
    interview = Interview(client)
    interview.start()
    assert interview.covered == {Topic.BASICS}


def test_save_and_resume(tmp_path):
    path = tmp_path / "session.json"
    first = Interview(ScriptedClient([turn("Q1", covered=["basics"]), turn("Q2")]))
    first.start()
    first.reply("We sell flowers.")
    first.save(path)

    client = ScriptedClient([turn("Q3")])
    resumed = Interview.load(path, client)
    assert resumed.start() == "Q2"  # resuming repeats the last question without a model call
    assert client.calls == []
    assert resumed.covered == {Topic.BASICS}
    resumed.reply("Open 9 to 5.")
    _, messages, _ = client.calls[0]
    assert messages[-1]["content"] == "Open 9 to 5." and len(messages) == 5


# --- the prompt --------------------------------------------------------------------------------

PROMPT = PROMPT_PATH.read_text(encoding="utf-8")


def test_prompt_lists_exactly_the_schema_topics():
    section = PROMPT.split("# Topics to cover", 1)[1].split("\n# ", 1)[0]
    listed = re.findall(r"^- `(\w+)`:", section, flags=re.MULTILINE)
    assert listed == [t.value for t in Topic]


def test_prompt_is_business_agnostic():
    # D-001, D-026: nothing about a particular business or trade in the interviewer's prompt.
    for word in ("plug", "print", "nicosia", "cyprus", "student", "shirt", "€"):
        assert word not in PROMPT.lower(), word
