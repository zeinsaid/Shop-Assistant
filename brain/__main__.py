"""Try the brain on one message from the command line.

    uv run python -m brain --kb kb/the-plug.md "how much for 100 b&w pages"
    uv run python -m brain --kb kb/the-plug.md --file thesis.pdf:42 ""
    uv run --env-file .env python -m brain --kb kb/the-plug.md --live "are you open now?"

Without --live nothing is sent anywhere and nothing is paid (DryRunClient).
"""

import argparse
import sys

from brain.brain import Brain, format_message
from brain.kb import load_kb
from brain.llm import DryRunClient, make_client
from brain.schema import Attachment, IncomingMessage


def parse_file(spec: str) -> Attachment:
    """'name.pdf:42' -> a pdf attachment with 42 pages; 'photo.jpg' -> an image attachment."""
    name, _, pages = spec.partition(":")
    kind = name.rsplit(".", 1)[-1].lower() if "." in name else "file"
    kind = "image" if kind in {"jpg", "jpeg", "png", "heic", "webp"} else kind
    return Attachment(type=kind, filename=name, pages=int(pages) if pages else None)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m brain", description="Run the brain on one message.")
    parser.add_argument("text", help="the customer's message (use \"\" for a file with no text)")
    parser.add_argument("--kb", required=True, help="path to the knowledge base markdown file")
    parser.add_argument("--file", action="append", default=[], metavar="NAME[:PAGES]",
                        help="an attachment (metadata only); repeat for several")
    parser.add_argument("--live", action="store_true", help="call the real model (costs money, needs a key)")
    parser.add_argument("--model", default="claude-sonnet-5")
    parser.add_argument("--effort", default="low", help="model effort: low, medium, high, xhigh or max")
    parser.add_argument("--show-input", action="store_true", help="print what the model is sent")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to a code page without Greek

    message = IncomingMessage(text=args.text, attachments=[parse_file(f) for f in args.file])
    client = make_client(args.model, args.effort) if args.live else DryRunClient()
    brain = Brain(load_kb(args.kb), client)

    if args.show_input:
        print(f"--- system prompt ({len(brain.system):,} characters) ---\n{brain.system}")
        print(f"--- customer turn ---\n{format_message(message)}\n")

    result = brain.decide(message)
    print(result.decision.model_dump_json(indent=2))
    print(f"\nmodel: {client.model} | attempts: {len(result.attempts)} | fallback: {result.fallback_used}"
          f" | tokens in/out: {result.input_tokens}/{result.output_tokens}")
    for i, attempt in enumerate(result.attempts, 1):
        for problem in attempt.problems:
            print(f"attempt {i} problem: {problem}")
    if result.dropped_citations:
        print(f"dropped unknown citations: {', '.join(result.dropped_citations)}")


if __name__ == "__main__":
    main()
