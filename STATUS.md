# MinuteMind — Project Status

_Last updated: 2026-06-16_

This document tracks what is **done**, what is **pending/unverified**, and what is
currently **blocking** verification. It complements `README.md` (which covers how to
run the project) and the build spec in `minutemind_build_prompt.md`.

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
- **`tests/test_ingest.py` — all 6 ingestion acceptance tests PASS** (confirmed in a
  prior run, after the ChromaDB and grounding-gate fixes above).

---

## 🟡 Pending / unverified

These are believed correct from code inspection but have **not been confirmed by a
green test run** because the run was interrupted (see Blocking).

- **`tests/test_qna.py` — 9 QnA acceptance tests not yet confirmed green.**
  The last attempt was killed by the OS (out of memory, exit code 137) before
  completing. Code fixes for the one observed failure (social turn "hey" being
  misclassified) are in place but unverified end-to-end.
- **Streamlit app (`app.py`) not manually exercised** against the six worked-example
  chat turns.
- **`run_ingest.py` PASS/DROP report** not re-confirmed since latest fixes (the
  underlying ingestion tests pass, so this is expected to work).

---

## 🔴 Blocking

- **Hardware: 8 GB RAM is too small to run the full suite with `llama3.1:8b`.**
  The model needs ~5 GB; with macOS + editor + Python (sentence-transformers +
  ChromaDB) the machine exceeds physical RAM, swaps hard, and the OS kills the test
  process (the `Exit code 137` / laptop freeze). Free RAM was measured at ~111 MB.

### Options to unblock verification
1. **Use a smaller model for local testing** — e.g. `llama3.2:3b` (~2 GB):
   `MINUTEMIND_MODEL=llama3.2:3b pytest -s` (after `ollama pull llama3.2:3b`).
2. **Run a cloud backend** (no large local model): set `MINUTEMIND_BACKEND=gemini`
   or `openai` with an API key — already supported in `llm.py`.
3. **Run on a machine with ≥16 GB RAM** to use `llama3.1:8b` as the spec specifies.
4. Run tests **one at a time** and close other apps to reduce peak memory.

---

## Definition of done (from spec §11) — checklist

- [ ] `python run_ingest.py sample/q3_sync.json` runs clean, logs PASS/DROP report
      (ingestion tests pass; report re-confirmation pending)
- [ ] `streamlit run app.py` handles all six worked-example turns (pending)
- [x] `pytest -s` ingestion tests green
- [ ] `pytest -s` QnA tests green (blocked by RAM)
- [x] README explains run steps + lists stubbed/deferred items
