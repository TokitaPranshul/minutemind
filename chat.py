#!/usr/bin/env python3
"""Terminal chat for MinuteMind — ask questions about ingested meetings.

Usage:
    python chat.py                       # company defaults to acme_internal
    python chat.py --company globex_inc  # pick a tenant
    python chat.py --verbose             # also show each node's live trace

Type a question and press Enter. Type 'exit', 'quit', or press Ctrl-D to leave.
Conversation history is kept, so follow-ups and clarify answers work
(e.g. ask "what did we decide?" then answer "the database").

Requires a populated store first:
    python run_ingest.py sample/q3_sync.json
"""
import argparse
import io
import sys
from contextlib import redirect_stdout

import config  # noqa: F401  (loads .env)
from qna.graph import build_qna_graph


def main():
    ap = argparse.ArgumentParser(description="MinuteMind terminal chat")
    ap.add_argument("--company", default="acme_internal", help="company_id (tenant)")
    ap.add_argument("--verbose", action="store_true", help="show each node's trace")
    args = ap.parse_args()

    print("Loading MinuteMind…", flush=True)
    graph = build_qna_graph()

    backend = config.MINUTEMIND_BACKEND
    model = (
        __import__("os").getenv("GROQ_MODEL")
        or __import__("os").getenv("GEMINI_MODEL")
        or config.MINUTEMIND_MODEL
    )
    print(f"\nMinuteMind chat — company: {args.company}  |  backend: {backend} / {model}")
    print("Ask about your meetings. Type 'exit' or Ctrl-D to quit.\n")

    chat_history = []
    while True:
        try:
            user = input("you ▸ ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye 👋")
            break
        if not user:
            continue
        if user.lower() in ("exit", "quit", ":q"):
            print("bye 👋")
            break

        state_in = {
            "company_id": args.company,
            "chat_history": list(chat_history),  # history WITHOUT the current turn
            "latest_turn": user,
            "retry_count": 0,
        }

        # node logging is noisy; hide it unless --verbose
        if args.verbose:
            result = graph.invoke(state_in)
        else:
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = graph.invoke(state_in)

        answer = result.get("final_answer", "(no answer)")
        print(f"\nbot ▸ {answer}\n")

        chat_history.append({"role": "user", "content": user})
        chat_history.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
