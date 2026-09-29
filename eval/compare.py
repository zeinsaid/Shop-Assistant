"""Compare eval result files side by side: headline numbers, then what changed case by case.

    uv run python -m eval.compare eval/results/A.json eval/results/B.json [more.json ...]

The first file is the baseline; case changes are reported relative to it.
"""

import json
import sys
from pathlib import Path

ROWS = [  # (label, how to read it from a summary)
    ("passed", lambda s: f"{s['passed']}/{s['cases'] - len(s['errors'])}"),
    ("action accuracy", lambda s: s["action_accuracy"]),
    ("wrongly answered", lambda s: len(s["wrongly_answered"])),
    ("must_not_contain", lambda s: len(s["must_not_contain_violations"])),
    ("missed answers", lambda s: len(s["missed_answers"])),
    ("citation recall", lambda s: s["citation_recall"]),
    ("language ok", lambda s: s["language_ok"]),
    ("fallbacks", lambda s: len(s["fallbacks"])),
    ("retried", lambda s: len(s["retried"])),
    ("errors", lambda s: len(s["errors"])),
    ("cost per case $", lambda s: s["cost_per_case_usd"]),
    ("seconds per case", lambda s: s["mean_seconds"]),
]


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def label(result: dict) -> str:
    run = result["run"]
    return f"{run['model']} ({run['effort']}) {run['started_at'][5:16]}"


def compare(results: list[dict]) -> str:
    lines = []
    width = max(len(label(r)) for r in results) + 2
    lines.append(" " * 18 + "".join(label(r).ljust(width) for r in results))
    for name, read in ROWS:
        lines.append(name.ljust(18) + "".join(str(read(r["summary"])).ljust(width) for r in results))

    base = {c["id"]: c for c in results[0]["cases"]}
    for other in results[1:]:
        fixed, broke, changed = [], [], []
        for case in other["cases"]:
            before = base.get(case["id"])
            if before is None:
                continue
            if case["passed"] and not before["passed"]:
                fixed.append(case["id"])
            elif before["passed"] and not case["passed"]:
                broke.append(case["id"])
            if case.get("action") != before.get("action"):
                changed.append(f"{case['id']} {before.get('action', 'error')} -> {case.get('action', 'error')}")
        lines.append(f"\n{label(other)} vs baseline:")
        lines.append(f"  now passing ({len(fixed)}): {', '.join(fixed) or '-'}")
        lines.append(f"  now failing ({len(broke)}): {', '.join(broke) or '-'}")
        lines.append(f"  action changed ({len(changed)}): {'; '.join(changed) or '-'}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    paths = argv if argv is not None else sys.argv[1:]
    if len(paths) < 2:
        raise SystemExit("usage: python -m eval.compare BASELINE.json OTHER.json [...]")
    sys.stdout.reconfigure(encoding="utf-8")
    print(compare([load(p) for p in paths]))


if __name__ == "__main__":
    main()
