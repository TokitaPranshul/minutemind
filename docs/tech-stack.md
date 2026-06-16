# MinuteMind — Tools & Technology Choices (with the *why*)

This doc explains **what** each tool does in MinuteMind and **why** it was chosen.
It's meant as a learning reference, so each section also notes the trade-offs and the
alternatives that were considered.

---

## At a glance

| Layer | Tool | Role | Where in code |
|---|---|---|---|
| Orchestration | **LangGraph** | Stateful agent graphs (ingest + QnA) | `ingest/graph.py`, `qna/graph.py` |
| Reasoning (LLM) | **Groq / Ollama / Gemini / OpenAI** | All natural-language reasoning steps | `llm.py` |
| Embeddings | **sentence-transformers** (`all-MiniLM-L6-v2`) | Turn text into 384-dim vectors | `llm.py::embed` |
| Vector storage | **ChromaDB** | Persistent vector DB + metadata filtering | `store.py` |
| Validation | **pydantic v2** | Validate every structured LLM output | `schemas.py` |
| UI | **Streamlit** | Chat front-end | `app.py` |
| Config | **python-dotenv** | `.env` backend/key switching | `config.py` |
| Tests | **pytest** | 15 acceptance tests | `tests/` |

The whole stack is **local + free by default** (Ollama + Chroma + MiniLM all run on your
machine). Cloud LLM backends are optional and used here only to dodge a RAM limit.

---

## 1. Vector storage — ChromaDB

**What it does.** Chroma is the database that stores every record as a *vector* (a list
of numbers) plus *metadata*. MinuteMind keeps **three separate collections**
(`store.py`):

- `chunks` — raw transcript windows (for fuzzy semantic recall)
- `facts` — grounded decisions & action items
- `inferences` — soft reads (sentiment, urgency, firmness…)

**Why a vector DB at all?** Meetings are messy natural language. You can't answer
"what did we decide about the database?" with a `WHERE text = '...'` SQL query — the
words in the question rarely match the words in the transcript. A vector DB lets you
search by **meaning** (nearest vectors) instead of exact text.

**Why Chroma specifically?**
- **Local, free, zero-infra.** `PersistentClient(path=...)` is a folder on disk — no
  server, no account, no Docker. Perfect for an MVP.
- **Metadata filtering built in.** Every query carries a `where` clause. This is how
  the hard **`company_id` isolation** is enforced on *every* read (`store.py::_and`) —
  cross-tenant leakage is impossible at the storage layer.
- **Two access patterns in one store:** `collection.query()` for top-k nearest-neighbour
  (semantic) and `collection.get(where=...)` for the *complete* set by metadata
  (structured filter / aggregate). MinuteMind uses both (`qna/nodes.py::retrieve_node`).
- **Separate collections** keep facts and inferences from ever mixing — a core
  requirement (an inference must never be served as a fact).

**Alternatives considered.** FAISS (fast but no metadata/persistence layer — you'd build
the `company_id` filtering yourself), pgvector/Postgres (needs a running DB), Pinecone/
Weaviate (hosted, paid, overkill for a local MVP).

---

## 2. Embeddings — sentence-transformers (`all-MiniLM-L6-v2`)

**What it does.** An *embedding model* converts a piece of text into a fixed-length
vector so that similar meanings land near each other in vector space. MinuteMind embeds
every chunk, fact, and inference at ingest, and embeds the user's question at query time
(`llm.py::embed`). Search = "find the stored vectors closest to the question vector."

**Why this model?**
- **Small & fast.** `all-MiniLM-L6-v2` produces **384-dim** vectors and runs on CPU in
  ~hundreds of MB of RAM — it does **not** need a GPU. On an 8 GB laptop this is the one
  heavy-ish component that still fits comfortably.
- **Normalized vectors.** We embed with `normalize_embeddings=True`, so vectors are unit
  length and similarity is a clean cosine comparison (see the real values in any
  `runs/<id>/3-agentic-dataflow.md`).
- **Good quality-for-size.** It's the de-facto default for lightweight RAG; accurate
  enough for short meeting text without the cost of a large embedding model.

**Key point — embeddings ≠ the LLM.** The embedding model only measures *similarity*; it
does not read, reason, or generate. That's a deliberate split: cheap local embeddings do
the *search*, the LLM does the *thinking*.

**Alternatives considered.** OpenAI/Cohere embedding APIs (better recall, but a paid
network call per chunk and a key requirement), larger local models like `bge-large`
(more accurate, far more RAM).

---

## 3. The LLM — why a language model does the "reasoning"

Several steps in MinuteMind are **judgment calls that can't be written as rules**, which
is exactly what LLMs are for. Each is a separate, narrow LLM call with a strict prompt:

| Step | Node | Why an LLM (not code) |
|---|---|---|
| **Extraction** | `ingest/nodes.py::analyzer` | Pulling decisions/action items/owners/due-dates out of free-form dialogue is open-ended language understanding. |
| **Grounding judge** | `ingest/nodes.py::grounding_gate` | Deciding whether a quote *actually supports* a claim (vs a negation or hypothetical) needs semantic judgment. |
| **Turn classification** | `qna/nodes.py::classifier_node` | "Is this a task, a greeting, out-of-scope, or a clarify answer?" — fuzzy intent. |
| **Query rewrite** | `rewrite_node` | Resolving "the database" → "what did we decide about the database" using prior turns. |
| **Routing** | `router_node` | Choosing semantic vs structured retrieval from the phrasing of the question. |
| **Composition** | `compose_node` | Writing a grounded, cited, natural answer from evidence. |
| **Answer judge** | `answer_gate_node` | Checking the draft is fully supported before it's shown. |

**Why not just rules/regex?** Because language is infinite. You can't enumerate every way
someone phrases "what does Marcus owe?". The LLM generalizes.

**But — LLMs are used *on a leash*:**
- Every LLM output is **validated by pydantic** and retried once on bad JSON; on repeat
  failure the pipeline **degrades gracefully** (drops the claim / bails) instead of
  crashing.
- Where a decision *can* be made deterministically and reliably, we **don't** spend an
  LLM call — e.g. social/out-of-scope pre-filters, clarify-answer detection, and the
  `structured_filter` safety net are plain Python (`qna/nodes.py`). This makes the agent
  cheaper and more predictable.
- The LLM is told to use **only retrieved evidence** (prompt rule A2) and to treat
  retrieved text as *data, not instructions* (A5, prompt-injection defense).

So the pattern is: **LLM for the fuzzy parts, code for the guarantees.**

---

## 4. LLM backend — Groq (and why it's pluggable)

`llm.py` supports four interchangeable backends via `MINUTEMIND_BACKEND`:
`ollama` (default) · `groq` · `gemini` · `openai`.

**Why pluggable?** The "brain" should be swappable without touching the agent logic.
Different environments want different trade-offs: privacy/offline (Ollama), zero local
RAM (cloud), cost, or speed.

**Why Groq is the one we actually run here.**
- **The RAM problem.** This project was built/tested on an **8 GB MacBook Air**. The
  spec's default model `llama3.1:8b` needs ~5 GB locally; with the OS + editor + Python
  it exceeds physical RAM, swaps, and the OS kills the process (the `Exit code 137`
  freeze). Running the LLM in the cloud moves that 5 GB off the machine entirely — only
  the small embedding model stays local.
- **Free + fast.** Groq's free tier is generous and its inference is extremely fast
  (custom hardware). Signup needs no cloud project (unlike Gemini, which was blocked for
  this account).
- **Drop-in.** Groq's API is OpenAI-style, so the backend is ~15 lines
  (`llm.py::_chat_groq`) and supports JSON-mode responses.
- **Trade-off noted.** Free tier has a **~100K tokens/day** cap on `llama-3.3-70b-versatile`;
  switch to `llama-3.1-8b-instant` for a higher limit (faster, slightly less accurate).

**Why keep Ollama as the documented default?** It's the truly local, free, no-key path
the spec mandates — ideal on a machine with enough RAM (≥16 GB) or for offline/private use.

---

## 5. Orchestration — LangGraph

**What it does.** Both pipelines are LangGraph `StateGraph`s: named **nodes** (functions)
connected by **edges**, passing a shared **state** dict. Crucially it supports
**conditional edges** — the graph branches on runtime values.

**Why LangGraph (not a plain function chain)?**
- **Branching & loops are first-class.** The QnA gate routes PASS→answer, RETRY→retrieve
  (a real loop), BAIL→bail (`qna/graph.py::_gate_route`). Ingest halts early on bad input
  (`ingest/graph.py::_halt_or`). That control flow is awkward as nested if/else but clean
  as a graph.
- **Observability.** Each node logs its input/output — that's exactly what makes the
  `runs/<id>/3-agentic-dataflow.md` traces possible.
- **Separation of concerns.** Retrieval, composition, and gating are independent,
  testable nodes.

**Alternatives considered.** LangChain chains (less natural for cyclic retry/bail),
hand-rolled functions (works, but you re-implement state passing, branching, and tracing).

---

## 6. Schema validation — pydantic v2

**What it does.** Every structured LLM output has a pydantic model (`schemas.py`:
`AnalyzerOutput`, `RouterOutput`, `ComposerOutput`, `GroundingVerdict`, …). The raw JSON
from the model is parsed and validated against it.

**Why it matters.** LLMs return *probable* JSON, not *guaranteed* JSON. Validation turns
"the model returned something weird" into a caught, handled event: retry once, then
degrade. It's the seatbelt that lets us trust LLM output downstream.

---

## 7. UI — Streamlit  ·  Config — python-dotenv  ·  Tests — pytest

- **Streamlit** (`app.py`) — a chat UI in ~40 lines of pure Python; no JS/HTML/CSS. Right
  level of effort for an MVP demo. It drives the exact same verified QnA graph.
- **python-dotenv** (`config.py`) — reads `.env` so backend/model/keys are swappable
  without code changes (and `.env` stays out of git).
- **pytest** (`tests/`) — the 15 acceptance tests *are* the definition of done; they
  encode the spec's worked examples (grounding drops, isolation, injection, bail).

---

## How the pieces fit (one sentence each)

1. **Transcript JSON** comes in (audio→text is upstream/out of scope).
2. **LangGraph** runs ingest; the **LLM** extracts + grounds; **sentence-transformers**
   embeds; **Chroma** stores facts/inferences/chunks with `company_id`.
3. At query time **LangGraph** runs QnA; the **LLM** classifies/rewrites/routes;
   **Chroma** retrieves by vector or metadata; the **LLM** composes a cited answer; a
   final **LLM** judge gates it; **pydantic** guards every step.

> See `docs/minutemind_*_reference.md` for the prompt-level spec, `STATUS.md` for current
> build status, and any `runs/<meeting_id>/` folder for a real end-to-end trace.
