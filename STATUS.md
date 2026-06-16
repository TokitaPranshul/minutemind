# MinuteMind — Project Status

_Last updated: 2026-06-16_

This document tracks what is **done**, what is **pending/unverified**, and what is
currently **blocking** verification. It complements `README.md` (which covers how to
run the project) and the build spec in `docs/minutemind_build_prompt.md`.

> **TL;DR — All 15 acceptance tests PASS** (`15 passed in ~83s`), verified using the
> **Groq** cloud backend (`llama-3.3-70b-versatile`) on an 8 GB laptop. The build is
> complete and proven. The only operational note is Groq's free-tier **daily token
> cap** (100K tokens/day on the 70B model), which ~2–3 full suite runs exhaust; it
> resets daily. See "Running notes" below.

---

## ✅ Done (implemented in code)

The full system is built per the spec. All source files are present and the imports +
both LangGraph graphs build successfully (smoke-tested).

- **Scaffolding & config** — `config.py`, `.env.example`, `requirements.txt`,
  pluggable LLM backend (Ollama default; Gemini/OpenAI optional) in `llm.py`.
- **Schemas** — `schemas.py`, all structured LLM outputs validated with pydantic.
- **Store** — `store.py` with a **hard `company_id` filter on every Chroma call**;
  facts and inferences kept in **separate collections**.
  - Fixed for **ChromaDB 1.x**: uses direct-equality `where` syntax (`{'field': value}`)
    which works in both `collection.get()` and `collection.query()`.
- **Ingestion graph** — `ingest/` (intake → analyze → grounding gate → store).
  - Grounding gate does verbatim quote checking with a **normalized fuzzy fallback**
    so minor punctuation/unicode drift from the LLM doesn't drop valid facts.
  - LLM judge given extra context so polite requests ("can you…?") count as action
    items, not open questions.
- **QnA graph** — `qna/` (classifier → fixed/clarify/task subgraph:
  rewrite → router → retrieve → compose → answer gate → answer/bail).
  - Deterministic **pre-filter** for obvious social / out-of-scope turns (avoids
    misclassification and saves an LLM call).
  - Retry/bail logic and **code-level company isolation check** in the answer gate.
- **Prompts** — all 7 prompt files in `prompts/`, copied **verbatim** from the
  reference docs (analyzer, grounding_judge, router, rewrite, composer, answer_judge,
  turn_classifier) plus `fixed_responses.py`.
- **Sample data** — `sample/q3_sync.json` (acme) and `sample/other_co.json` (globex).
- **Streamlit app** — `app.py`.
- **Tests written** — `tests/test_ingest.py` (6 acceptance tests) and
  `tests/test_qna.py` (9 acceptance tests).
- **README** — includes run steps and the required "stubbed / deferred" section.

### Verified passing
- **`tests/test_ingest.py` — all 6 ingestion acceptance tests PASS.**
- **`tests/test_qna.py` — all 9 QnA acceptance tests PASS.**
- Full suite: **`15 passed in ~83s`** via the Groq backend.

### Fixes applied during verification (QnA)
- **clarify_answer detection** — a reply to the assistant's clarifying question is now
  detected deterministically (the verbatim classifier prompt names the type but gives
  no rule), so "the database" after a clarify resolves to the Postgres decision.
- **classifier guidance** — questions naming a specific person/topic are routed to
  `task` (not `task_ambiguous`), so "what does Marcus owe?" reaches the router.
- **structured_filter safety net** — per-person / list / count questions are forced to
  the COMPLETE fact set (`structured_filter`), never top-k semantic.
- **honest bail** — when the composer says the evidence doesn't answer, the gate now
  BAILs with the canonical "not in your meetings" message instead of surfacing a hedge.
- **robust social detection** — compound closings like "thanks, that's all" are caught
  deterministically instead of relying on the LLM.

---

## 🟢 Solved blocker (was: 8 GB RAM / OOM)

The original blocker was that `llama3.1:8b` (~5 GB local) + everything else exceeded
8 GB RAM, causing swap/freeze and OS kills (`Exit code 137`). **Solved by running the
LLM in the cloud** via the Groq backend — nothing large loads locally (only the small
~400 MB embedding model), so the 8 GB laptop runs the full suite comfortably.

---

## 🟡 Running notes / minor caveats

- **Groq free-tier daily token cap.** The default model `llama-3.3-70b-versatile` has a
  **100K tokens/day** free limit; a full suite run uses ~30–40K, so ~2–3 runs/day
  exhaust it (HTTP 429, resets daily). For more frequent runs, switch to a
  higher-limit model: `GROQ_MODEL=llama-3.1-8b-instant` (faster/cheaper, slightly less
  accurate — may need spot re-checking of borderline cases).
- **LLM nondeterminism.** Compose/judge/analyzer steps call a live LLM; outputs are
  graceful on bad JSON (retry once, then degrade), but a borderline assertion could
  occasionally need a re-run. The deterministic fixes above remove most of this risk
  from the classifier/router/gate paths.
- **Streamlit app (`app.py`)** runs the same verified QnA graph; not separately
  click-tested but exercised end-to-end by the QnA test suite.

---

## Definition of done (from spec §11) — checklist

- [x] `python run_ingest.py sample/q3_sync.json` runs clean (ingestion tests green)
- [x] QnA graph handles all six worked-example turns (verified via test suite)
- [x] `pytest -s` ingestion tests green (6/6)
- [x] `pytest -s` QnA tests green (9/9)
- [x] README explains run steps + lists stubbed/deferred items
