# 3 · Agentic Data Flow — `acme_q3_sync_0615`

Backend: **groq / llama-3.1-8b-instant**.  Every value below is captured from a real run.

```
AUDIO (out of scope)
   -> TRANSCRIPT JSON  (Doc 1)
        -> INGEST GRAPH:  intake -> validate -> speaker_resolution
                          -> analyzer -> grounding_gate -> indexer   (Doc 2)
             -> QnA GRAPH: classifier -> [rewrite -> router -> retrieve
                           -> compose -> answer_gate] -> answer/bail
```

## A. Ingestion — live node trace

Each node logs its input and output. This is the actual stdout:

```
=== [intake] received ===
  keys: ['company_id', 'meeting_id', 'title', 'date', 'attendees', 'segments']
  company_id=acme_internal meeting_id=acme_q3_sync_0615 segments=10

=== [validate] ===
  segments=10 diarization_coverage=100% well_formed=10
  PASS

=== [speaker_resolution] ===
  resolved 10 segments (names already present -> pass-through)

=== [analyzer] ===
  extracted: 1 decisions, 2 action_items, 2 entities
  summary: Team decided to use Postgres for the new analytics service database; Marcus will write the migration plan by Friday; Dan

=== [grounding_gate] ===
  PASS [decision] 'Use Postgres for the new analytics service database' -> Marcus explicitly states his commitment to Postgres for the new analytics service database.
  PASS [action_item:Marcus] 'Write the migration plan for Postgres' -> Priya's request to Marcus to write the migration plan is a direct assignment of the action item.
  PASS [action_item:Dana] 'Send the final dashboard mockups' -> Polite request from Priya to Dana to send final dashboard mockups by Wednesday
  grounding done: 3 passed, 0 dropped (inferences skip the gate)

=== [indexer] ===
  indexed: {'facts': 3, 'inferences': 4, 'chunks': 3}
```

## B. Chunking — how the transcript is sliced & vectorised

Code: `ingest/nodes.py::_chunk_segments(segments, size=4)`.

- **Window size:** 4 segments per chunk, **no overlap**.
- 10 segments -> **3 chunks** (4 + 4 + 2…).
- Each chunk's text is embedded with `all-MiniLM-L6-v2` into a **384-dim**
  unit vector (L2-normalised), then stored in the `chunks` collection.
- A chunk keeps `t_start`, `t_end`, and the set of speakers it spans.

Why chunk at all? Facts are short and precise; chunks preserve the raw
back-and-forth so semantic search can find context that no extracted fact
captured ("what did Dana worry about?").

### chunk 0  (segments 0–3, 00:12–01:10, speakers: Dana,Marcus,Priya)
```
[00:12] Marcus: Main thing today — we still haven't picked the database for the new analytics service. We're three weeks from the Acme launch and this is blocking me.
[00:31] Priya: Right. Last sync we were torn between Postgres and Mongo. Where did we land?
[00:44] Marcus: I spent the week testing both. Postgres handles our query patterns way better. I want to commit to Postgres.
[01:10] Dana: Any impact on the dashboard work? I don't want to redo the charts.
```
**embedding:** `dim=384, L2norm=1.000, first8=[-0.015, -0.058, -0.024, +0.052, +0.049, -0.022, -0.025, -0.048, ...]`

### chunk 1  (segments 4–7, 01:18–01:52, speakers: Marcus,Priya)
```
[01:18] Marcus: No, the API stays the same. You're fine.
[01:25] Priya: Okay, let's lock it — Postgres it is. Marcus, can you write up the migration plan? I'd like it by Friday so we're not scrambling.
[01:40] Marcus: Friday's tight but doable. I'll have a draft.
[01:52] Priya: And Dana, send me the final dashboard mockups by Wednesday?
```
**embedding:** `dim=384, L2norm=1.000, first8=[-0.075, -0.043, -0.035, -0.045, +0.064, -0.043, -0.049, -0.036, ...]`

### chunk 2  (segments 8–9, 01:58–02:05, speakers: Dana,Priya)
```
[01:58] Dana: Yep, Wednesday works.
[02:05] Priya: Great. The Acme launch is the priority — everything else can slip.
```
**embedding:** `dim=384, L2norm=1.000, first8=[-0.064, -0.052, -0.019, +0.007, +0.051, +0.048, -0.014, +0.018, ...]`

## C. Retrieval — how a question finds evidence

For every task question the QnA graph: **classifies** -> **rewrites** to a
standalone question -> **routes** (picks a retrieval mode) -> **retrieves**
-> **composes** a grounded answer -> **gates** it (PASS / RETRY / BAIL).

Two retrieval modes:
- **semantic** — embed the question, return the top-k nearest vectors
  (cosine distance) from `facts`/`chunks`. Good for fuzzy recall.
- **structured_filter** — ignore vectors, pull the COMPLETE set from `facts`
  by metadata (e.g. all of one person's action items). Good for list/aggregate.

`company_id` is a hard filter on **every** query — cross-tenant leakage is
impossible at the store layer.

### Q: "What did we decide about the database?"

**Live node trace:**

```
=== [classifier] ===
  latest_turn: 'What did we decide about the database?'
  turn_type=task

=== [rewrite] ===
  standalone_question: 'What did we decide about the database?'

=== [router] ===
  route: {'intent': 'factual_recall', 'retrieval_mode': 'semantic', 'namespace': ['facts', 'chunks'], 'filters': {'owner': None, 'type': None, 'date_range': None, 'meeting_id': None}, 'note': 'Decision about the database'}

=== [retrieve] ===
  company_id=acme_internal mode=semantic namespaces={'chunks', 'facts'} filters={'owner': None, 'type': None, 'date_range': None, 'meeting_id': None} k=5 retry=0
  retrieved 6 items
    [facts] Use Postgres for the new analytics service database
    [facts] Write the migration plan for Postgres
    [facts] Send the final dashboard mockups
    [chunks] [00:12] Marcus: Main thing today — we still haven't picked the databas
    [chunks] [01:18] Marcus: No, the API stays the same. You're fine.
[01:25] Priya
    [chunks] [01:58] Dana: Yep, Wednesday works.
[02:05] Priya: Great. The Acme lau

=== [compose] ===
  draft: We decided to use Postgres for the new analytics service database [0 · Marcus · 00:44].

=== [answer_gate] ===
  judge verdict=PASS note=

=== [answer] ===
  final_answer: We decided to use Postgres for the new analytics service database [0 · Marcus · 00:44].
```

**Step-by-step (real values):**

1. **classifier** -> `turn_type = 'task'`
2. **rewrite** -> standalone question: `'What did we decide about the database?'`
3. **router** -> mode=`semantic`, namespace=`['facts', 'chunks']`, filters=`{'owner': None, 'type': None, 'date_range': None, 'meeting_id': None}`
4. **retrieve** -> query vector: `dim=384, L2norm=1.000, first8=[-0.020, +0.001, -0.078, +0.013, -0.025, +0.005, -0.011, +0.032, ...]`

   Retrieved **6** items (semantic shows cosine distance; lower = closer):

   | # | namespace | distance | cos(q,doc) | text |
   |---|-----------|----------|------------|------|
   | 0 | facts | 1.358 | 0.321 | Use Postgres for the new analytics service database… |
   | 1 | facts | 1.611 | 0.194 | Write the migration plan for Postgres… |
   | 2 | facts | 2.078 | -0.039 | Send the final dashboard mockups… |
   | 3 | chunks | 1.344 | 0.328 | [00:12] Marcus: Main thing today — we still haven't pic… |
   | 4 | chunks | 1.686 | 0.157 | [01:18] Marcus: No, the API stays the same. You're fine… |
   | 5 | chunks | 1.873 | 0.063 | [01:58] Dana: Yep, Wednesday works. [02:05] Priya: Grea… |

5. **compose** -> draft: 'We decided to use Postgres for the new analytics service database [0 · Marcus · 00:44].'
6. **answer_gate** -> verdict=`PASS`
7. **final answer:**

> We decided to use Postgres for the new analytics service database [0 · Marcus · 00:44].

---

### Q: "What does Marcus owe?"

**Live node trace:**

```
=== [classifier] ===
  latest_turn: 'What does Marcus owe?'
  turn_type=task

=== [rewrite] ===
  standalone_question: 'What does Marcus owe?'

=== [router] ===
  route: {'intent': 'factual_aggregate', 'retrieval_mode': 'structured_filter', 'namespace': ['facts'], 'filters': {}, 'note': ' [structured_filter nudge]'}

=== [retrieve] ===
  company_id=acme_internal mode=structured_filter namespaces={'facts'} filters={} k=5 retry=0
  retrieved 3 items
    [facts] Use Postgres for the new analytics service database
    [facts] Write the migration plan for Postgres
    [facts] Send the final dashboard mockups

=== [compose] ===
  draft: Marcus owes to write the migration plan for Postgres by Friday [acme_q3_sync_0615 · Priya · 01:25].

=== [answer_gate] ===
  judge verdict=PASS note=

=== [answer] ===
  final_answer: Marcus owes to write the migration plan for Postgres by Friday [acme_q3_sync_0615 · Priya · 01:25].
```

**Step-by-step (real values):**

1. **classifier** -> `turn_type = 'task'`
2. **rewrite** -> standalone question: `'What does Marcus owe?'`
3. **router** -> mode=`structured_filter`, namespace=`['facts']`, filters=`{}`
4. **retrieve** -> query vector: `dim=384, L2norm=1.000, first8=[-0.056, +0.039, -0.010, -0.017, -0.053, -0.029, +0.070, +0.053, ...]`

   Retrieved **3** items (structured_filter: complete set, no distance):

   | # | namespace | distance | cos(q,doc) | text |
   |---|-----------|----------|------------|------|
   | 0 | facts | — | -0.031 | Use Postgres for the new analytics service database… |
   | 1 | facts | — | 0.086 | Write the migration plan for Postgres… |
   | 2 | facts | — | -0.031 | Send the final dashboard mockups… |

5. **compose** -> draft: 'Marcus owes to write the migration plan for Postgres by Friday [acme_q3_sync_0615 · Priya · 01:25].'
6. **answer_gate** -> verdict=`PASS`
7. **final answer:**

> Marcus owes to write the migration plan for Postgres by Friday [acme_q3_sync_0615 · Priya · 01:25].

---

### Q: "Did finance approve the budget?"

**Live node trace:**

```
=== [classifier] ===
  latest_turn: 'Did finance approve the budget?'
  turn_type=task

=== [rewrite] ===
  standalone_question: 'Did finance approve the budget?'

=== [router] ===
  route: {'intent': 'factual_aggregate', 'retrieval_mode': 'structured_filter', 'namespace': ['facts'], 'filters': {'owner': 'finance', 'type': 'approval', 'date_range': None, 'meeting_id': None}, 'note': 'Complete set required for owner filter'}

=== [retrieve] ===
  company_id=acme_internal mode=structured_filter namespaces={'facts'} filters={'owner': 'finance', 'type': 'approval', 'date_range': None, 'meeting_id': None} k=5 retry=0
  retrieved 0 items

=== [compose] ===
  draft: No evidence was retrieved to answer this question.

=== [answer_gate] ===
  no evidence/draft -> RETRY

=== [retrieve] ===
  company_id=acme_internal mode=structured_filter namespaces={'facts'} filters={'owner': 'finance', 'type': 'approval', 'date_range': None, 'meeting_id': None} k=8 retry=1
  retrieved 0 items

=== [compose] ===
  draft: No evidence was retrieved to answer this question.

=== [answer_gate] ===
  no evidence/draft -> RETRY

=== [retrieve] ===
  company_id=acme_internal mode=structured_filter namespaces={'facts'} filters={'owner': 'finance', 'type': 'approval', 'date_range': None, 'meeting_id': None} k=11 retry=2
  retrieved 0 items

=== [compose] ===
  draft: No evidence was retrieved to answer this question.

=== [answer_gate] ===
  no evidence after retries -> BAIL

=== [bail] ===
```

**Step-by-step (real values):**

1. **classifier** -> `turn_type = 'task'`
2. **rewrite** -> standalone question: `'Did finance approve the budget?'`
3. **router** -> mode=`structured_filter`, namespace=`['facts']`, filters=`{'owner': 'finance', 'type': 'approval', 'date_range': None, 'meeting_id': None}`
4. **retrieve** -> query vector: `dim=384, L2norm=1.000, first8=[-0.009, +0.076, -0.041, +0.078, +0.067, -0.021, +0.005, +0.010, ...]`

   _(nothing retrieved)_

5. **compose** -> draft: 'No evidence was retrieved to answer this question.'
6. **answer_gate** -> verdict=`BAIL`
7. **final answer:**

> I don't have a meeting where that came up. Want me to check a specific meeting, or rephrase?

---

## D. Takeaways

- **Chunking** = fixed 4-segment windows -> 384-dim vectors. Simple, but
  enough for semantic recall of raw dialogue.
- **Retrieval** = either nearest-neighbour vectors (semantic) or a metadata
  pull of the whole set (structured_filter); the router decides which.
- **Grounding** happens twice: at ingest (drop unprovable facts) and at
  answer time (the gate bails rather than guess).
- **Isolation** = `company_id` filter on every read; nothing else can leak in.
