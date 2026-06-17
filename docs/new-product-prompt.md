# Starter prompt for a NEW product (referencing MinuteMind)

Open a **new Claude Code chat in your new product's folder**, then paste the template
below. The `@` paths pull MinuteMind's docs/code straight into the new chat's context —
no copy-paste of file contents needed.

> Tip: type `@` in Claude Code and it autocompletes file paths. Absolute paths
> (`/Users/pranshulp/minutemind/...`) work from any folder.

---

## ▶︎ Copy-paste template (fill in the squares)

```
I'm building a new product. Before writing any code, read these references from a
project I built, and reuse its architecture and engineering patterns:

  @/Users/pranshulp/minutemind/docs/tech-stack.md
  @/Users/pranshulp/minutemind/docs/chat-flow.md
  @/Users/pranshulp/minutemind/README.md

(Full source if you need it: https://github.com/TokitaPranshul/minutemind )

WHAT I'M BUILDING:
  [one or two sentences: what the product does and for whom]

REUSE FROM MINUTEMIND:
  - LangGraph StateGraph with small, logged nodes + conditional edges
  - Pluggable LLM backend (Groq/Ollama/Gemini/OpenAI) via an .env switch — see its llm.py
  - Pydantic validation on every structured LLM output, retry once, degrade gracefully
  - "LLM for the fuzzy parts, deterministic code for the guarantees" (pre-filters/nudges)
  - ChromaDB vector store with a hard tenant/scope filter on every query (if relevant)
  - Tests as the definition of done

WHAT'S DIFFERENT THIS TIME:
  [how the new product differs — different domain, no multi-tenant, web API instead of
   Streamlit, different data source, etc.]

CONSTRAINTS:
  - I'm on an 8GB MacBook Air — prefer a cloud LLM backend (Groq free tier) over large
    local models. Keep heavy things off local RAM.
  - [budget / language / framework / deadline, if any]

FIRST STEP:
  Don't start coding yet. Ask me any clarifying questions, then propose a short plan
  (file layout + the node/graph design) for my approval.
```

---

## ▶︎ Filled-in example

```
I'm building a new product. Before writing any code, read these references from a
project I built, and reuse its architecture and engineering patterns:

  @/Users/pranshulp/minutemind/docs/tech-stack.md
  @/Users/pranshulp/minutemind/docs/chat-flow.md

WHAT I'M BUILDING:
  A support-ticket assistant: it ingests past resolved tickets and answers new
  questions with grounded, cited suggestions from those tickets.

REUSE FROM MINUTEMIND:
  - The ingest -> ground -> store -> retrieve -> compose -> gate pattern in LangGraph
  - Pluggable Groq backend + pydantic-validated outputs
  - ChromaDB with a hard filter (here: team_id instead of company_id)
  - Honest "I don't have that" bail instead of guessing

WHAT'S DIFFERENT THIS TIME:
  - Data source is a CSV export of tickets, not meeting transcripts
  - Expose a FastAPI endpoint instead of a Streamlit UI
  - No sentiment/inference layer needed — facts only

CONSTRAINTS:
  - 8GB laptop -> use Groq (llama-3.1-8b-instant), keep models off local RAM
  - Python, keep it MVP-simple

FIRST STEP:
  Ask clarifying questions, then propose a file layout + graph design before coding.
```

---

## Which references to attach for which goal

| Your new product is… | Attach (`@`) |
|---|---|
| Architecturally similar (RAG / agent over docs) | `tech-stack.md`, `chat-flow.md`, plus `llm.py`, `store.py` for code-level reuse |
| Just borrowing the LLM-backend pattern | `/Users/pranshulp/minutemind/llm.py`, `config.py`, `.env.example` |
| Borrowing the grounded-answer / gate idea | `chat-flow.md`, `qna/nodes.py` |
| Totally different, just want the engineering discipline | `tech-stack.md` (the "LLM on a leash" section) |

## Two reminders
- **MinuteMind's saved memories are folder-scoped** — a new folder won't auto-load them.
  `@`-mention what you want, or run `/init` in the new folder for its own `CLAUDE.md`.
- **Keep MinuteMind on disk** (don't delete `~/minutemind`) so the `@` paths resolve.
  The GitHub URL is the fallback if you move machines.
