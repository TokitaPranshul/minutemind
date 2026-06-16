#!/usr/bin/env python3
"""Trace a single MinuteMind run and emit 3 learning documents.

Usage:
    python trace_run.py <transcript.json> ["question 1" "question 2" ...]

For each run it writes, into runs/<meeting_id>/ :
    1-input-transcript.md      the raw meeting that went in
    2-output.md                what got stored (facts / inferences / chunks)
    3-agentic-dataflow.md      every node's REAL input/output, with a deep dive
                               on how chunking and retrieval actually work

The run uses an isolated vector store (runs/<meeting_id>/_chroma) so the
documents are reproducible and reflect only this meeting.
"""
import io
import json
import math
import sys
from contextlib import redirect_stdout
from pathlib import Path

import config  # noqa: F401  (loads .env)
import llm
from ingest.graph import build_graph
from ingest.nodes import _chunk_segments, _format_transcript
from qna.graph import build_qna_graph
from store import Store

BASE = Path(__file__).parent


# ---------------------------------------------------------------------------
# small display helpers
# ---------------------------------------------------------------------------
def vec_summary(v, n=8):
    norm = math.sqrt(sum(x * x for x in v))
    head = ", ".join(f"{x:+.3f}" for x in v[:n])
    return f"dim={len(v)}, L2norm={norm:.3f}, first{n}=[{head}, ...]"


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def code(s):
    return f"```\n{s}\n```"


def jcode(obj):
    return f"```json\n{json.dumps(obj, indent=2, ensure_ascii=False)}\n```"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print("Usage: python trace_run.py <transcript.json> [\"question\" ...]")
        sys.exit(1)

    transcript_path = sys.argv[1]
    data = json.loads(Path(transcript_path).read_text())
    questions = sys.argv[2:] or [
        "What did we decide about the database?",
        "What does Marcus owe?",
        "Did finance approve the budget?",
    ]

    company_id = data["company_id"]
    meeting_id = data["meeting_id"]
    segments = data["segments"]

    run_dir = BASE / "runs" / meeting_id
    run_dir.mkdir(parents=True, exist_ok=True)
    chroma_path = str(run_dir / "_chroma")
    import shutil

    shutil.rmtree(chroma_path, ignore_errors=True)

    model_note = config.MINUTEMIND_BACKEND + " / " + (
        __import__("os").getenv("GROQ_MODEL")
        or __import__("os").getenv("GEMINI_MODEL")
        or config.MINUTEMIND_MODEL
    )

    # =======================================================================
    # 1. INGEST (capture the live node trace)
    # =======================================================================
    ingest_log = io.StringIO()
    with redirect_stdout(ingest_log):
        ingest_state = build_graph().invoke(
            {"raw_input": data, "halt": False, "chroma_path": chroma_path}
        )
    ingest_trace = ingest_log.getvalue()
    grounding_report = ingest_state.get("grounding_report", {})
    counts = ingest_state.get("indexed_counts", {})

    # Re-derive chunks + embeddings to SHOW chunking concretely
    chunks = _chunk_segments(segments)
    chunk_embs = llm.embed([c["text"] for c in chunks]) if chunks else []

    # Read back what was stored
    store = Store(chroma_path)
    stored_facts = store.get_all_facts(company_id)
    stored_infs = store.get_inferences(company_id)
    stored_chunks_raw = store.chunks.get(where={"company_id": company_id})

    # =======================================================================
    # 2. QnA (capture live trace + final state per question)
    # =======================================================================
    qna_graph = build_qna_graph()
    qruns = []
    for q in questions:
        qlog = io.StringIO()
        with redirect_stdout(qlog):
            st = qna_graph.invoke(
                {
                    "company_id": company_id,
                    "chat_history": [],
                    "latest_turn": q,
                    "retry_count": 0,
                    "chroma_path": chroma_path,
                }
            )
        # embed the standalone question to show the query vector used for retrieval
        sq = st.get("standalone_question") or q
        qvec = llm.embed([sq])[0]
        qruns.append({"q": q, "state": st, "trace": qlog.getvalue(), "qvec": qvec})

    # =======================================================================
    # DOC 1 — INPUT TRANSCRIPT
    # =======================================================================
    doc1 = [f"# 1 · Input Transcript — `{meeting_id}`", ""]
    doc1 += [
        f"- **Title:** {data.get('title','')}",
        f"- **Date:** {data.get('date','')}",
        f"- **Company (tenant):** `{company_id}`",
        f"- **Attendees:** {', '.join(data.get('attendees', []))}",
        f"- **Segments:** {len(segments)}",
        "",
        "This is exactly what enters the pipeline — already-transcribed, speaker-",
        "labelled, timestamped text. (Audio capture + transcription is upstream and",
        "out of scope; see README.)",
        "",
        "## Conversation",
        "",
        "| # | time | speaker | text |",
        "|---|------|---------|------|",
    ]
    for i, s in enumerate(segments):
        txt = s.get("text", "").replace("|", "\\|")
        doc1.append(f"| {i} | {s.get('t','')} | {s.get('speaker','')} | {txt} |")
    doc1 += ["", "## Raw JSON (what `run_ingest.py` reads)", "", jcode(data)]
    (run_dir / "1-input-transcript.md").write_text("\n".join(doc1))

    # =======================================================================
    # DOC 2 — OUTPUT (what got stored)
    # =======================================================================
    doc2 = [f"# 2 · Output — what `{meeting_id}` became", ""]
    doc2 += [
        f"Backend: **{model_note}**",
        "",
        "Ingestion turns the transcript into three kinds of stored records, each in",
        "its own Chroma collection. **Facts** and **inferences** are kept separate on",
        "purpose; `company_id` is stamped on every record.",
        "",
        f"**Indexed counts:** `{counts}`",
        "",
        "## Grounding report (what passed / was dropped)",
        "",
        "Every decision & action item must clear the grounding gate (verbatim-quote",
        "code check, then an LLM judge). Ungrounded claims are dropped, not stored.",
        "",
        jcode(grounding_report),
        "",
        "## FACTS collection",
        "",
    ]
    if stored_facts:
        for f in stored_facts:
            m = f["metadata"]
            doc2 += [
                f"### `{f['id']}`  ({m.get('type')})",
                f"- **text:** {f['text']}",
                f"- **owner / due:** {m.get('owner','—')} / {m.get('due','—')}",
                f"- **evidence:** {m.get('evidence_speaker')} @ {m.get('evidence_t')} — "
                f"\"{m.get('evidence_quote')}\"",
                f"- **confidence:** {m.get('confidence')}",
                "",
            ]
    else:
        doc2 += ["_(no facts stored)_", ""]

    doc2 += ["## INFERENCES collection", "",
             "Soft reads (sentiment, urgency, firmness…). These **skip** the grounding",
             "gate and are always labelled as inferences downstream — never stated as fact.",
             ""]
    if stored_infs:
        doc2 += ["| id | type | label | confidence |", "|----|------|-------|------------|"]
        for inf in stored_infs:
            m = inf["metadata"]
            label = inf["text"].replace("|", "\\|")
            doc2.append(
                f"| `{inf['id']}` | {m.get('type')} | {label} | {m.get('confidence')} |"
            )
        doc2.append("")
    else:
        doc2 += ["_(no inferences stored)_", ""]

    doc2 += ["## CHUNKS collection", "",
             "Raw transcript, sliced into windows for semantic search (see Doc 3 for the",
             "chunking deep-dive).", "",
             "| id | t_start–t_end | speakers | preview |",
             "|----|---------------|----------|---------|"]
    cids = stored_chunks_raw.get("ids", [])
    cdocs = stored_chunks_raw.get("documents", [])
    cmetas = stored_chunks_raw.get("metadatas", [])
    for i in range(len(cids)):
        m = cmetas[i]
        preview = cdocs[i][:70].replace("\n", " ").replace("|", "\\|")
        doc2.append(
            f"| `{cids[i]}` | {m.get('t_start')}–{m.get('t_end')} | {m.get('speaker')} | {preview}… |"
        )
    doc2.append("")
    (run_dir / "2-output.md").write_text("\n".join(doc2))

    # =======================================================================
    # DOC 3 — AGENTIC DATA FLOW (real in/out + chunking & retrieval deep dive)
    # =======================================================================
    d = [f"# 3 · Agentic Data Flow — `{meeting_id}`", "",
         f"Backend: **{model_note}**.  Every value below is captured from a real run.", "",
         "```",
         "AUDIO (out of scope)",
         "   -> TRANSCRIPT JSON  (Doc 1)",
         "        -> INGEST GRAPH:  intake -> validate -> speaker_resolution",
         "                          -> analyzer -> grounding_gate -> indexer   (Doc 2)",
         "             -> QnA GRAPH: classifier -> [rewrite -> router -> retrieve",
         "                           -> compose -> answer_gate] -> answer/bail",
         "```", ""]

    # --- Ingestion live trace
    d += ["## A. Ingestion — live node trace", "",
          "Each node logs its input and output. This is the actual stdout:", "",
          code(ingest_trace.strip()), ""]

    # --- CHUNKING deep dive
    d += ["## B. Chunking — how the transcript is sliced & vectorised", "",
          "Code: `ingest/nodes.py::_chunk_segments(segments, size=4)`.", "",
          f"- **Window size:** 4 segments per chunk, **no overlap**.",
          f"- {len(segments)} segments -> **{len(chunks)} chunks** "
          f"(4 + 4 + {len(segments) - 8 if len(segments) > 8 else len(segments)%4 or 4}…).",
          "- Each chunk's text is embedded with `all-MiniLM-L6-v2` into a **384-dim**",
          "  unit vector (L2-normalised), then stored in the `chunks` collection.",
          "- A chunk keeps `t_start`, `t_end`, and the set of speakers it spans.",
          "",
          "Why chunk at all? Facts are short and precise; chunks preserve the raw",
          "back-and-forth so semantic search can find context that no extracted fact",
          "captured (\"what did Dana worry about?\").", ""]
    for i, c in enumerate(chunks):
        seg_lo = i * 4
        seg_hi = min(seg_lo + 4, len(segments)) - 1
        d += [f"### chunk {i}  (segments {seg_lo}–{seg_hi}, {c['t_start']}–{c['t_end']}, speakers: {c['speaker']})",
              code(c["text"]),
              f"**embedding:** `{vec_summary(chunk_embs[i])}`", ""]

    # --- RETRIEVAL deep dive (per question)
    d += ["## C. Retrieval — how a question finds evidence", "",
          "For every task question the QnA graph: **classifies** -> **rewrites** to a",
          "standalone question -> **routes** (picks a retrieval mode) -> **retrieves**",
          "-> **composes** a grounded answer -> **gates** it (PASS / RETRY / BAIL).", "",
          "Two retrieval modes:",
          "- **semantic** — embed the question, return the top-k nearest vectors",
          "  (cosine distance) from `facts`/`chunks`. Good for fuzzy recall.",
          "- **structured_filter** — ignore vectors, pull the COMPLETE set from `facts`",
          "  by metadata (e.g. all of one person's action items). Good for list/aggregate.",
          "",
          "`company_id` is a hard filter on **every** query — cross-tenant leakage is",
          "impossible at the store layer.", ""]

    for run in qruns:
        st = run["state"]
        route = st.get("route") or {}
        retrieved = st.get("retrieved") or []
        d += [f"### Q: \"{run['q']}\"", "",
              "**Live node trace:**", "", code(run["trace"].strip()), "",
              "**Step-by-step (real values):**", "",
              f"1. **classifier** -> `turn_type = {st.get('turn_type')!r}`",
              f"2. **rewrite** -> standalone question: `{st.get('standalone_question')!r}`",
              f"3. **router** -> mode=`{route.get('retrieval_mode')}`, "
              f"namespace=`{route.get('namespace')}`, filters=`{route.get('filters')}`",
              f"4. **retrieve** -> query vector: `{vec_summary(run['qvec'])}`", ""]
        if retrieved:
            d += [f"   Retrieved **{len(retrieved)}** items"
                  + (" (semantic shows cosine distance; lower = closer):"
                     if route.get("retrieval_mode") != "structured_filter"
                     else " (structured_filter: complete set, no distance):"),
                  "",
                  "   | # | namespace | distance | cos(q,doc) | text |",
                  "   |---|-----------|----------|------------|------|"]
            for j, r in enumerate(retrieved):
                dist = r.get("distance")
                dist_s = f"{dist:.3f}" if isinstance(dist, (int, float)) else "—"
                # cosine vs the query (recompute for intuition where we have the doc text)
                try:
                    cosv = f"{cosine(run['qvec'], llm.embed([r.get('text','')])[0]):.3f}"
                except Exception:
                    cosv = "—"
                txt = (r.get("text", "") or "")[:55].replace("\n", " ").replace("|", "\\|")
                d.append(f"   | {j} | {r.get('namespace')} | {dist_s} | {cosv} | {txt}… |")
            d.append("")
        else:
            d += ["   _(nothing retrieved)_", ""]
        d += [f"5. **compose** -> draft: {st.get('draft_answer','')!r}",
              f"6. **answer_gate** -> verdict=`{st.get('gate_verdict')}`",
              f"7. **final answer:**",
              "",
              f"> {st.get('final_answer','')}",
              "", "---", ""]

    d += ["## D. Takeaways", "",
          "- **Chunking** = fixed 4-segment windows -> 384-dim vectors. Simple, but",
          "  enough for semantic recall of raw dialogue.",
          "- **Retrieval** = either nearest-neighbour vectors (semantic) or a metadata",
          "  pull of the whole set (structured_filter); the router decides which.",
          "- **Grounding** happens twice: at ingest (drop unprovable facts) and at",
          "  answer time (the gate bails rather than guess).",
          "- **Isolation** = `company_id` filter on every read; nothing else can leak in.",
          ""]
    (run_dir / "3-agentic-dataflow.md").write_text("\n".join(d))

    print(f"Wrote 3 documents to {run_dir}/")
    print("  1-input-transcript.md")
    print("  2-output.md")
    print("  3-agentic-dataflow.md")


if __name__ == "__main__":
    main()
