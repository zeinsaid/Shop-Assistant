"""Run the brain on every eval case, score it, and save a timestamped result file.

    uv run python -m eval.run_eval --kb kb/the-plug.md                        # dry run, free
    uv run python -m eval.run_eval --kb kb/the-plug.md --ids q001,q067        # a few cases
    uv run --env-file .env python -m eval.run_eval --kb kb/the-plug.md --model claude-sonnet-5

Results go to eval/results/ (gitignored). Runs on real cases (a file under eval/real/) always
write their results inside eval/real/, so real messages never end up anywhere committed.
Compare runs with `python -m eval.compare`.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from brain.brain import PROMPT_PATH, Brain
from brain.kb import load_kb
from brain.llm import make_client
from brain.schema import IncomingMessage
from eval.scoring import score_case, summarise

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CASES = ROOT / "eval" / "questions.jsonl"
DEFAULT_PRICES = ROOT / "eval" / "prices.json"
REAL_DIR = ROOT / "eval" / "real"

ABORT_AFTER = 3  # if the first N cases all fail, stop: it's almost certainly setup (key, model name)


def load_cases(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def select(cases: list[dict], ids: str | None = None, category: str | None = None,
           limit: int | None = None) -> list[dict]:
    if ids:
        wanted = {i.strip() for i in ids.split(",")}
        unknown = wanted - {c["id"] for c in cases}
        if unknown:
            raise SystemExit(f"unknown case IDs: {', '.join(sorted(unknown))}")
        cases = [c for c in cases if c["id"] in wanted]
    if category:
        cases = [c for c in cases if c["category"] == category]
    return cases[:limit] if limit else cases


def results_dir(cases_path: Path, out_dir: Path | None) -> Path:
    """Where results go. Real cases keep their results inside eval/real/, no matter what."""
    is_real = cases_path.resolve().is_relative_to(REAL_DIR.resolve())
    if out_dir is None:
        return REAL_DIR / "results" if is_real else ROOT / "eval" / "results"
    if is_real and not out_dir.resolve().is_relative_to(REAL_DIR.resolve()):
        raise SystemExit("results of real cases must stay inside eval/real/")
    return out_dir


def run(cases: list[dict], brain: Brain, price: dict | None, log=print) -> tuple[list[dict], str | None]:
    """Run every case. Returns the scored records and, if the run was aborted, why."""
    records = []
    for n, case in enumerate(cases, 1):
        message = IncomingMessage(text=case["message"], attachments=case["attachments"])
        start = time.perf_counter()
        try:
            result = brain.decide(message)
            record = score_case(case, result, price=price, seconds=time.perf_counter() - start)
        except Exception as e:  # noqa: BLE001 - any failure is recorded against the case (D-025)
            record = score_case(case, None, error=f"{type(e).__name__}: {e}",
                                seconds=time.perf_counter() - start)
        records.append(record)
        log(_progress_line(n, len(cases), record))

        if n == ABORT_AFTER and all(r["status"] == "error" for r in records):
            return records, f"the first {ABORT_AFTER} cases all failed: {records[-1]['error']}"
    return records, None


def _progress_line(n: int, total: int, r: dict) -> str:
    head = f"[{n:>3}/{total}] {r['id']:<5}"
    if r["status"] == "error":
        return f"{head} ERROR {r['error']}"
    mark = "ok  " if r["passed"] else "FAIL"
    extra = " (fallback)" if r["fallback_used"] else " (retried)" if r["attempts"] > 1 else ""
    return f"{head} {mark} expected {r['expected_action']:<9} got {r['action']}{extra}"


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def git_version() -> str | None:
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        return f"{commit}{'+uncommitted' if dirty else ''}"
    except (OSError, subprocess.CalledProcessError):
        return None


def print_summary(s: dict, log=print) -> None:
    ok_cases = s["cases"] - len(s["errors"])
    if not ok_cases:
        log(f"\nno case completed ({len(s['errors'])} errors)")
        return
    log(f"\ncases {s['cases']} | passed {s['passed']}/{ok_cases} | action accuracy {s['action_accuracy']}")
    log(f"wrongly answered: {len(s['wrongly_answered'])} {s['wrongly_answered'] or ''}")
    log(f"must_not_contain violations: {len(s['must_not_contain_violations'])} {s['must_not_contain_violations'] or ''}")
    log(f"missed answers: {len(s['missed_answers'])} | citation recall {s['citation_recall']} | language {s['language_ok']}")
    log(f"fallbacks {len(s['fallbacks'])} | retried {len(s['retried'])} | dropped citations {s['dropped_citations']}"
        f" | errors {len(s['errors'])}")
    log(f"cost ${s['cost_usd']} (${s['cost_per_case_usd']}/case) | mean {s['mean_seconds']}s/case | tokens {s['tokens']}")
    log("expected -> chosen: " + "; ".join(
        f"{exp}: {', '.join(f'{got} {n}' for got, n in chosen.items())}" for exp, chosen in s["confusion"].items()))


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(prog="python -m eval.run_eval", description=__doc__.split("\n")[0])
    parser.add_argument("--kb", required=True, type=Path, help="knowledge base markdown file")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--model", default="dry-run", help="dry-run (free) or a model name, e.g. claude-sonnet-5")
    parser.add_argument("--effort", default="low")
    parser.add_argument("--ids", help="comma-separated case IDs to run")
    parser.add_argument("--category", help="only run cases in this category")
    parser.add_argument("--limit", type=int, help="only run the first N cases")
    parser.add_argument("--prices", type=Path, default=DEFAULT_PRICES)
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # replies may be Greek; Windows consoles aren't UTF-8

    cases = select(load_cases(args.cases), args.ids, args.category, args.limit)
    if not cases:
        raise SystemExit("no cases selected")
    out_dir = results_dir(args.cases, args.out_dir)
    price = json.loads(args.prices.read_text(encoding="utf-8")).get(args.model)
    brain = Brain(load_kb(args.kb), make_client(args.model, args.effort))

    started = datetime.now()
    print(f"running {len(cases)} cases on {args.model} (effort {args.effort})"
          f"{'' if price else ' - no price known, cost not reported'}")
    records, aborted = run(cases, brain, price)
    summary = summarise(records)
    print_summary(summary)

    output = {
        "run": {
            "started_at": started.isoformat(timespec="seconds"),
            "model": args.model,
            "effort": args.effort,
            "kb": str(args.kb),
            "kb_fingerprint": fingerprint(args.kb),
            "prompt_fingerprint": fingerprint(PROMPT_PATH),
            "cases_file": str(args.cases),
            "filters": {"ids": args.ids, "category": args.category, "limit": args.limit},
            "code_version": git_version(),
            "price_per_million_tokens": price,
            "aborted": aborted,
        },
        "summary": summary,
        "cases": records,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{started:%Y%m%d-%H%M%S}_{args.model}.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{'ABORTED: ' + aborted + chr(10) if aborted else ''}saved {path}")
    return path


if __name__ == "__main__":
    main()
