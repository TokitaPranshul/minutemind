# MinuteMind

A local, free, MVP AI meeting-notetaker. Two halves:

- **Ingestion** reads one meeting transcript and writes a grounded, citable record
  (decisions, action items, entities = facts; sentiment, urgency, etc. = inferences)
  into a company-scoped vector store, dropping anything it can't ground.
- **QnA** is a conversational chat agent that answers questions about those meetings —
  grounded with citations, inferences labeled, anything outside the meetings honestly refused.

Both pipelines are LangGraph `StateGraph`s. Facts and inferences live in **separate**
Chroma collections, and `company_id` is a hard filter on every retrieval.

## Stack (all local + free by default)

- LangGraph — orchestration
- Ollama — default LLM (`MINUTEMIND_MODEL`, default `llama3.1:8b`)
- sentence-transformers — embeddings (`all-MiniLM-L6-v2`)
- Chroma — local persistent vector store
- pydantic v2 — schema validation
- Streamlit — chat UI

Backend switch via `MINUTEMIND_BACKEND` (`ollama` default | `groq` | `gemini` | `openai`).

## How to run

### Option A — local Ollama (default, needs ~6 GB free RAM)

```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ollama pull llama3.1:8b
python run_ingest.py sample/q3_sync.json
streamlit run app.py
pytest -s
```

> Requires Python 3.11+ and a running Ollama server (`ollama serve`).

### Option B — Groq cloud LLM (recommended on low-RAM machines, e.g. 8 GB)

No large model loads locally — only the small embedding model. Get a free key at
<https://console.groq.com/keys>, then:

```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt groq
# in .env:  MINUTEMIND_BACKEND=groq  GROQ_API_KEY=gsk_...  GROQ_MODEL=llama-3.3-70b-versatile
python run_ingest.py sample/q3_sync.json
pytest -s
```

> The full acceptance suite (15 tests) was verified green this way on an 8 GB laptop.
> Note Groq's free-tier daily token cap (~100K/day on the 70B model); use
> `GROQ_MODEL=llama-3.1-8b-instant` for a higher limit.

## Configuration

Copy `.env.example` to `.env` and adjust as needed. The default Ollama path
requires no API key. See `STATUS.md` for current build status and verification notes.

## What's stubbed / deferred for this MVP

- **Audio → transcript.** `faster-whisper` is not wired in; input is a transcript
  JSON file (`{company_id, meeting_id, title, date, attendees, segments}`). Hook a
  transcription step in front of `run_ingest.py` to support raw audio.
- **Cross-session memory.** The QnA agent only carries a rolling window of the
  current conversation; nothing persists between chat sessions.
- **Cross-meeting supersession.** If a later meeting overturns an earlier decision,
  the store does not link or flag the conflict automatically — the composer can
  only surface a conflict if both meetings are retrieved together.
- **Auth / multi-tenant cloud deployment.** `company_id` is enforced as a hard
  filter throughout, but there is no authentication layer, request-level tenant
  resolution, or hosted deployment — this is a local single-user MVP.
