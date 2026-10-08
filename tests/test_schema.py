import pytest
from pydantic import ValidationError

from brain.schema import Action, Attachment, BrainDecision, IncomingMessage, Role, Turn


def decision(**overrides) -> dict:
    """A valid 'answer' decision, with fields overridden per test."""
    base = {
        "reasoning": "The KB covers this.",
        "action": "answer",
        "reply": "We're open 24/7.",
        "cited_entries": ["shop-hours"],
        "question_for_owner": None,
    }
    return {**base, **overrides}


# --- valid decisions, one per action -------------------------------------------------------


def test_valid_answer():
    d = BrainDecision(**decision())
    assert d.action is Action.ANSWER
    assert d.cited_entries == ["shop-hours"]
    assert d.question_for_owner is None


def test_valid_ask_owner_has_holding_reply_and_question():
    d = BrainDecision(
        **decision(
            action="ask_owner",
            reply="Let me check with the team and get back to you.",
            cited_entries=[],
            question_for_owner="Customer asks about X. Details so far: Y.",
        )
    )
    assert d.action is Action.ASK_OWNER


def test_valid_handoff_has_reply_but_no_question():
    d = BrainDecision(
        **decision(action="handoff", reply="A team member will take over.", cited_entries=[])
    )
    assert d.question_for_owner is None


def test_valid_no_reply_has_nothing_to_send():
    d = BrainDecision(**decision(action="no_reply", reply=None, cited_entries=[]))
    assert d.reply is None and d.question_for_owner is None and d.cited_entries == []


@pytest.mark.parametrize("missing", ["reply", "cited_entries", "question_for_owner"])
def test_every_field_must_be_present_even_when_empty(missing):
    # D-020: the model always writes all five keys, using null or [] when a field doesn't apply.
    fields = decision(action="no_reply", reply=None, cited_entries=[])
    del fields[missing]
    with pytest.raises(ValidationError):
        BrainDecision(**fields)


# --- rules between fields ------------------------------------------------------------------


@pytest.mark.parametrize(
    "fields",
    [
        {"action": "answer", "reply": None},  # answer needs a reply
        {"action": "ask_owner", "reply": "Checking.", "question_for_owner": None},  # needs question
        {"action": "ask_owner", "reply": None, "question_for_owner": "Q?"},  # needs holding reply
        {"action": "handoff", "reply": None},  # handoff needs a hand-over message
        {"action": "handoff", "reply": "Passing you on.", "question_for_owner": "Q?"},  # no question
        {"action": "no_reply", "reply": "Hello", "cited_entries": []},  # no_reply has no reply
        {"action": "no_reply", "reply": None, "question_for_owner": "Q?"},  # ...or question
        {"action": "answer", "question_for_owner": "Q?"},  # question only with ask_owner
    ],
)
def test_inconsistent_combinations_are_rejected(fields):
    with pytest.raises(ValidationError):
        BrainDecision(**decision(**fields))


def test_blank_strings_count_as_missing():
    d = BrainDecision(
        **decision(action="no_reply", reply="  ", cited_entries=[], question_for_owner="")
    )
    assert d.reply is None and d.question_for_owner is None
    with pytest.raises(ValidationError):  # a blank reply is no reply, so 'answer' fails
        BrainDecision(**decision(reply="   "))


# --- per-field checks ----------------------------------------------------------------------


@pytest.mark.parametrize("reasoning", ["", "   "])
def test_reasoning_must_not_be_blank(reasoning):
    with pytest.raises(ValidationError):
        BrainDecision(**decision(reasoning=reasoning))


def test_unknown_action_is_rejected():
    with pytest.raises(ValidationError):
        BrainDecision(**decision(action="escalate"))


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        BrainDecision(**decision(confidence=0.9))


def test_cited_entries_are_stripped_and_not_restricted_by_action():
    d = BrainDecision(
        reasoning="Internal rule applies.",
        action="ask_owner",
        reply="Checking.",
        question_for_owner="Q?",
        cited_entries=[" policy-discounts "],
    )
    assert d.cited_entries == ["policy-discounts"]


def test_answer_without_citations_passes_the_schema():
    # D-019: "must cite at least one existing entry" is enforced in brain.py, not here.
    assert BrainDecision(**decision(cited_entries=[])).cited_entries == []


# --- JSON in and out -----------------------------------------------------------------------


def test_json_round_trip():
    original = BrainDecision(**decision())
    assert BrainDecision.model_validate_json(original.model_dump_json()) == original


def test_action_serialises_as_plain_string():
    assert '"action":"answer"' in BrainDecision(**decision()).model_dump_json()


def test_json_schema_keeps_field_order_and_describes_every_field():
    # The order is what makes "reasoning first" work (D-019); descriptions are prompt content.
    schema = BrainDecision.model_json_schema()
    properties = schema["properties"]
    assert list(properties) == ["reasoning", "action", "reply", "cited_entries", "question_for_owner"]
    assert all(p.get("description") for p in properties.values())
    assert schema["required"] == list(properties)  # every field required (D-020)


# --- input models --------------------------------------------------------------------------


def test_incoming_message_defaults():
    m = IncomingMessage(text="hi")
    assert m.attachments == []
    assert IncomingMessage().text == ""


def test_attachment_from_eval_style_dicts():
    m = IncomingMessage(
        text="2 copies colour pls",
        attachments=[{"type": "pdf", "filename": "lab_report.pdf", "pages": 8}, {"type": "image", "filename": "a.jpg"}],
    )
    assert m.attachments[0].pages == 8 and m.attachments[1].pages is None


def test_attachment_has_no_way_to_carry_file_contents():
    with pytest.raises(ValidationError):  # D-010: metadata only
        Attachment(type="pdf", filename="thesis.pdf", content="the whole thesis")


def test_attachment_rejects_zero_pages():
    with pytest.raises(ValidationError):
        Attachment(type="pdf", filename="a.pdf", pages=0)


# --- conversation history (D-023) --------------------------------------------------------------


def test_history_turns_from_eval_style_dicts():
    m = IncomingMessage(
        text="yes colour pls",
        history=[
            {"role": "customer", "text": "how much for 10 pages?"},
            {"role": "bot", "action": "answer", "text": "Colour or black & white?"},
            {"role": "staff", "text": "Hi, I'm at the counter if you need anything."},
            {"role": "customer", "attachments": [{"type": "pdf", "filename": "notes.pdf", "pages": 10}]},
        ],
    )
    assert [t.role for t in m.history] == [Role.CUSTOMER, Role.BOT, Role.STAFF, Role.CUSTOMER]
    assert m.history[1].action is Action.ANSWER
    assert IncomingMessage().history == []


@pytest.mark.parametrize(
    "turn",
    [
        {"role": "bot", "text": "Hi!"},  # a bot turn must say which action sent it
        {"role": "bot", "action": "no_reply", "text": "x"},  # no_reply sends nothing to show
        {"role": "customer", "action": "answer", "text": "hi"},  # only bot turns have an action
        {"role": "staff", "text": "here", "attachments": [{"type": "pdf", "filename": "a.pdf"}]},
        {"role": "customer", "text": "  "},  # nothing at all
        {"role": "owner", "text": "€18"},  # the owner's raw answers never go in (D-023)
        {"role": "bot", "action": "answer", "text": "Hi", "reasoning": "internal"},  # no extra fields
    ],
)
def test_invalid_turns_are_rejected(turn):
    with pytest.raises(ValidationError):
        Turn(**turn)
