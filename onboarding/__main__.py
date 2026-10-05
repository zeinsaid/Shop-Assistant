"""Interview a business owner in the terminal to build their knowledge base (D-030).

    uv run --env-file .env python -m onboarding --session my-shop --model claude-sonnet-5-5

The session is saved to onboarding/sessions/<name>.json after every turn (gitignored: it holds
business information). Run the same command again to resume. Type /quit to stop.
"""

import argparse
import sys
from pathlib import Path

from brain.llm import make_client
from onboarding.interview import Interview
from onboarding.schema import Topic

SESSIONS = Path(__file__).resolve().parent / "sessions"


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m onboarding", description=__doc__.split("\n")[0])
    parser.add_argument("--session", required=True, help="a name for this interview, e.g. the business")
    parser.add_argument("--model", required=True, help="e.g. claude-sonnet-5-5, gpt-6.1-sol, gpt-6-luna")
    parser.add_argument("--effort", default="medium")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # the owner may write Greek; Windows consoles aren't UTF-8
    sys.stdin.reconfigure(encoding="utf-8")

    path = SESSIONS / f"{args.session}.json"
    client = make_client(args.model, args.effort)
    interview = Interview.load(path, client) if path.exists() else Interview(client)
    if interview.done:
        print(f"This interview is already finished ({path}).")
        return

    print(f"{'Resuming' if path.exists() else 'Starting'} interview '{args.session}'. Type /quit to stop.\n")
    message = interview.start()
    interview.save(path)
    while True:
        print(f"\n{message}\n")
        if interview.done:
            print(f"Interview finished. Saved to {path}")
            return
        print(f"[{len(interview.covered)}/{len(Topic)} topics covered]")
        owner = input("> ").strip()
        if owner == "/quit":
            print(f"Stopped. Resume with the same command. Saved to {path}")
            return
        if not owner:
            continue
        message = interview.reply(owner)
        interview.save(path)


if __name__ == "__main__":
    main()
