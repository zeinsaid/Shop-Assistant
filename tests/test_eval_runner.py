import json
from pathlib import Path

import pytest

from brain.brain import Attempt, Brain, BrainResult
from brain.kb import load_kb, parse_kb
from brain.llm import Completion, DryRunClient, ScriptedClient
from brain.schema import BrainDecision
from eval import compare, run_eval
from eval.scoring import amounts_in, cost_usd, dominant_script, score_case, summarise

ROOT = Path(__file__).resolve().parent.parent
KB_PATH = ROOT / "kb" / "the-plug.md"


def case(**overrides) -> dict:
    base = {
        "id": "t1", "category": "test", "message": "hi", "attachments": [],
        "expected_action": "answer", "expected_entries": ["a", "b"], "notes": "", "source": "synthetic",
    }
    return {**base, **overrides}


def result(action="answer", reply="Hello", cited=("a", "b"), question=None, tokens=(100, 50, 7000, 0),
           attempts=1, fallback=False) -> BrainResult:
    decision = BrainDecision(reasoning="r", action=action, reply=reply, cited_entries=list(cited),
                             question_for_owner=question)
    # Token usage sits on the first attempt; every attempt but the last had a problem.
    runs = [
        Attempt(Completion("{}", "end_turn", *tokens) if i == 0 else Completion("{}"), ["x"] if i < attempts - 1 else [])
        for i in range(attempts)
    ]
    return BrainResult(decision, fallback, runs)


# --- scoring one case --------------------------------------------------------------------------


def test_correct_answer_passes():
    r = score_case(case(), result())
    assert r["passed"] and r["checks"]["action_correct"] and r["checks"]["citation_recall"] == 1


def test_missing_citation_fails_but_extra_citation_is_fine():
    partial = score_case(case(), result(cited=["a"]))
    assert not partial["passed"]
    assert partial["checks"]["citation_recall"] == 0.5 and partial["checks"]["missing_citations"] == ["b"]
    assert score_case(case(), result(cited=["a", "b", "c"]))["passed"]


def test_alternative_citations_accept_either_entry():
    either = case(expected_entries=["a|b"])
    assert score_case(either, result(cited=["b"]))["passed"]
    assert score_case(either, result(cited=["c"]))["checks"]["missing_citations"] == ["a|b"]


def test_answering_when_escalation_was_expected_is_flagged():
    r = score_case(case(expected_action="ask_owner", expected_entries=[]), result())
    assert r["checks"]["wrongly_answered"] and not r["passed"]
    assert r["checks"]["citation_recall"] is None


def test_escalating_when_an_answer_was_expected_is_a_missed_answer():
    r = score_case(case(), result(action="ask_owner", cited=[], question="Q?"))
    assert r["checks"]["missed_answer"] and not r["checks"]["wrongly_answered"]


def test_amounts_are_read_in_common_formats():
    assert amounts_in("€45, or 2,50 € each, 1,000 pages at €0.17") == [45, 2.5, 1000, 0.17]


def test_expected_amount_must_appear_in_the_reply():
    good = score_case(case(expected_amounts=[45]), result(reply="3 prints are €45.00 in total."))
    assert good["passed"] and good["checks"]["missing_amounts"] == []
    wrong = score_case(case(expected_amounts=[45]), result(reply="3 prints are €60."))
    assert not wrong["passed"] and wrong["checks"]["missing_amounts"] == [45]
    assert summarise([wrong])["wrong_amounts"] == ["t1"]


def test_amounts_are_not_checked_when_the_bot_escalated():
    r = score_case(case(expected_amounts=[45]), result(action="ask_owner", cited=[], question="Q?"))
    assert r["checks"]["missing_amounts"] == []


def test_must_not_contain_is_case_insensitive():
    r = score_case(case(must_not_contain=["outsourc"]), result(reply="It's Outsourced to a partner."))
    assert r["checks"]["must_not_contain_hits"] == ["outsourc"] and not r["passed"]


@pytest.mark.parametrize(
    "reply, expected_language, ok",
    [
        ("Είμαστε ανοιχτοί 24/7.", ["el"], True),
        ("We're open 24/7.", ["el"], False),
        ("We're open 24/7.", ["el", "en"], True),
    ],
)
def test_reply_language_is_checked_by_script(reply, expected_language, ok):
    r = score_case(case(expected_language=expected_language), result(reply=reply))
    assert r["checks"]["language_ok"] is ok


def test_language_check_skipped_for_unknown_codes_and_no_reply():
    assert score_case(case(expected_language=["xx"]), result())["checks"]["language_ok"] is None
    silent = result(action="no_reply", reply=None, cited=[])
    assert score_case(case(expected_action="no_reply", expected_entries=[], expected_language=["el"]),
                      silent)["checks"]["language_ok"] is None


def test_dominant_script():
    assert dominant_script("Γεια σας, hi") == "GREEK"
    assert dominant_script("hello") == "LATIN"
    assert dominant_script("123 !") is None


def test_error_record():
    r = score_case(case(), None, error="APIConnectionError: boom")
    assert r["status"] == "error" and not r["passed"] and r["error"].startswith("APIConnectionError")


def test_cost():
    price = {"input": 2.0, "output": 10.0, "cache_read": 0.2, "cache_write": 2.5}
    tokens = {"input": 1_000_000, "output": 100_000, "cache_read": 1_000_000, "cache_write": 0}
    assert cost_usd(tokens, price) == pytest.approx(2.0 + 1.0 + 0.2)
    assert cost_usd(tokens, None) is None


# --- summarising a run -------------------------------------------------------------------------


def test_summary_counts():
    price = {"input": 1, "output": 1, "cache_read": 1, "cache_write": 1}
    records = [
        score_case(case(id="a1"), result(), price=price),
        score_case(case(id="a2", expected_action="handoff", expected_entries=[]), result(), price=price),
        score_case(case(id="a3"), result(action="ask_owner", cited=[], question="Q?", attempts=2, fallback=True), price=price),
        score_case(case(id="a4"), None, error="boom"),
    ]
    s = summarise(records)
    assert s["cases"] == 4 and s["errors"] == ["a4"] and s["passed"] == 1
    assert s["action_accuracy"] == pytest.approx(1 / 3, abs=0.001)
    assert s["wrongly_answered"] == ["a2"] and s["missed_answers"] == ["a3"]
    assert s["fallbacks"] == ["a3"] and s["retried"] == ["a3"]
    assert s["confusion"] == {"answer": {"answer": 1, "ask_owner": 1}, "handoff": {"answer": 1}}
    assert s["cost_usd"] is not None


def test_summary_hides_cost_when_a_price_is_unknown():
    s = summarise([score_case(case(), result(), price=None)])
    assert s["cost_usd"] is None and s["cost_per_case_usd"] is None


# --- running -----------------------------------------------------------------------------------


def test_dry_run_over_the_real_eval_set():
    cases = run_eval.load_cases(run_eval.DEFAULT_CASES)
    brain = Brain(load_kb(KB_PATH), DryRunClient())
    records, aborted = run_eval.run(cases, brain, price=None, log=lambda _: None)
    assert aborted is None and len(records) == len(cases)
    # The dry-run client always escalates, so exactly the ask_owner cases are right, except those
    # that check the owner question for details: its placeholder question has none.
    expected_right = sum(c["expected_action"] == "ask_owner" and "question_must_contain" not in c for c in cases)
    assert summarise(records)["passed"] == expected_right


def test_errors_are_recorded_and_the_run_continues():
    class Flaky:
        model = "flaky"
        calls = 0

        def complete(self, system, messages, schema):
            self.calls += 1
            if self.calls == 2:
                raise ConnectionError("network down")
            return DryRunClient().complete(system, messages, schema)

    brain = Brain(parse_kb("### a\n**Visibility:** public · **Status:** confirmed\n\nA."), Flaky(), prompt="x")
    records, aborted = run_eval.run([case(id=f"c{i}") for i in range(4)], brain, None, log=lambda _: None)
    assert aborted is None
    assert [r["status"] for r in records] == ["ok", "error", "ok", "ok"]
    assert records[1]["error"] == "ConnectionError: network down"


def test_run_aborts_when_the_first_cases_all_fail():
    class Broken:
        model = "broken"

        def complete(self, system, messages, schema):
            raise PermissionError("no API key")

    brain = Brain(parse_kb("### a\n**Visibility:** public · **Status:** confirmed\n\nA."), Broken(), prompt="x")
    records, aborted = run_eval.run([case(id=f"c{i}") for i in range(10)], brain, None, log=lambda _: None)
    assert len(records) == run_eval.ABORT_AFTER and "no API key" in aborted


def test_select_filters():
    cases = [case(id="q1", category="x"), case(id="q2", category="y"), case(id="q3", category="y")]
    assert [c["id"] for c in run_eval.select(cases, ids="q1,q3")] == ["q1", "q3"]
    assert [c["id"] for c in run_eval.select(cases, category="y", limit=1)] == ["q2"]
    with pytest.raises(SystemExit):
        run_eval.select(cases, ids="nope")


def test_real_case_results_stay_inside_eval_real(tmp_path):
    real_cases = run_eval.REAL_DIR / "questions.jsonl"  # the path only; nothing is read
    assert run_eval.results_dir(real_cases, None) == run_eval.REAL_DIR / "results"
    with pytest.raises(SystemExit):
        run_eval.results_dir(real_cases, tmp_path)
    assert run_eval.results_dir(run_eval.DEFAULT_CASES, None) == ROOT / "eval" / "results"


def test_main_writes_a_result_file_and_compare_reads_it(tmp_path, capsys):
    first = run_eval.main(["--kb", str(KB_PATH), "--ids", "q001,q007", "--out-dir", str(tmp_path)])
    saved = json.loads(first.read_text(encoding="utf-8"))
    assert saved["run"]["model"] == "dry-run" and saved["run"]["prompt_fingerprint"]
    assert saved["summary"]["cases"] == 2 and saved["summary"]["cost_usd"] == 0
    assert {c["id"] for c in saved["cases"]} == {"q001", "q007"}

    # A second run, then compare: q007 (ask_owner) passes in both, q001 (answer) fails in both.
    second = tmp_path / "second.json"
    saved["run"]["started_at"] = "2026-09-29T12:00:00"
    saved["cases"][0]["passed"] = not saved["cases"][0]["passed"]
    second.write_text(json.dumps(saved), encoding="utf-8")
    capsys.readouterr()
    compare.main([str(first), str(second)])
    out = capsys.readouterr().out
    assert "wrongly answered" in out and "vs baseline" in out and ("now passing (1)" in out or "now failing (1)" in out)


# --- multi-turn cases (D-023) ------------------------------------------------------------------


def test_owner_question_must_carry_the_collected_details():
    c = case(expected_action="ask_owner", expected_entries=[], question_must_contain=["Outdoor", "friday"])
    good = score_case(c, result("ask_owner", "Let me check.", (), "Banner 2x1 m, outdoor, by Friday."))
    bad = score_case(c, result("ask_owner", "Let me check.", (), "Customer wants a banner."))
    assert good["passed"] and good["checks"]["missing_in_question"] == []
    assert not bad["passed"] and bad["checks"]["missing_in_question"] == ["Outdoor", "friday"]
    assert summarise([good, bad])["incomplete_questions"] == ["t1"]


def test_history_reaches_the_brain_and_the_record():
    history = [{"role": "customer", "text": "how much for posters?"},
               {"role": "bot", "action": "answer", "text": "Which size?"}]
    client = ScriptedClient([json.dumps({"reasoning": "r", "action": "answer", "reply": "A1 is €5.",
                                         "cited_entries": ["a"], "question_for_owner": None})])
    brain = Brain(parse_kb("### a\n**Visibility:** public · **Status:** confirmed\n\nA."), client, prompt="x")
    records, _ = run_eval.run([case(message="A1", expected_entries=["a"], history=history)], brain, None,
                              log=lambda _: None)
    assert "[bot, answer] Which size?" in client.calls[0][1][0]["content"]
    assert records[0]["history"] == history and records[0]["passed"]


def test_always_reply_overrides_apply_only_in_that_setting():
    c = case(expected_action="no_reply", expected_entries=[],
             always_reply={"expected_action": "answer", "expected_entries": ["a"]})
    assert run_eval.for_setting(c, False)["expected_action"] == "no_reply"
    merged = run_eval.for_setting(c, True)
    assert merged["expected_action"] == "answer" and merged["expected_entries"] == ["a"]
    assert "always_reply" not in merged
