# 2 · Output — what `acme_q3_sync_0615` became

Backend: **groq / llama-3.1-8b-instant**

Ingestion turns the transcript into three kinds of stored records, each in
its own Chroma collection. **Facts** and **inferences** are kept separate on
purpose; `company_id` is stamped on every record.

**Indexed counts:** `{'facts': 3, 'inferences': 4, 'chunks': 3}`

## Grounding report (what passed / was dropped)

Every decision & action item must clear the grounding gate (verbatim-quote
code check, then an LLM judge). Ungrounded claims are dropped, not stored.

```json
{
  "passed": [
    {
      "claim": "Use Postgres for the new analytics service database",
      "label": "decision",
      "note": "Marcus explicitly states his commitment to Postgres for the new analytics service database."
    },
    {
      "claim": "Write the migration plan for Postgres",
      "label": "action_item:Marcus",
      "note": "Priya's request to Marcus to write the migration plan is a direct assignment of the action item."
    },
    {
      "claim": "Send the final dashboard mockups",
      "label": "action_item:Dana",
      "note": "Polite request from Priya to Dana to send final dashboard mockups by Wednesday"
    }
  ],
  "dropped": []
}
```

## FACTS collection

### `acme_q3_sync_0615:fact:d1`  (decision)
- **text:** Use Postgres for the new analytics service database
- **owner / due:** — / —
- **evidence:** Marcus @ 00:44 — "Postgres handles our query patterns way better. I want to commit to Postgres."
- **confidence:** 0.95

### `acme_q3_sync_0615:fact:a1`  (action_item)
- **text:** Write the migration plan for Postgres
- **owner / due:** Marcus / Friday
- **evidence:** Priya @ 01:25 — "Let's lock it — Postgres it is. Marcus, can you write up the migration plan?"
- **confidence:** 0.9

### `acme_q3_sync_0615:fact:a2`  (action_item)
- **text:** Send the final dashboard mockups
- **owner / due:** Dana / Wednesday
- **evidence:** Priya @ 01:52 — "And Dana, send me the final dashboard mockups by Wednesday?"
- **confidence:** 0.9

## INFERENCES collection

Soft reads (sentiment, urgency, firmness…). These **skip** the grounding
gate and are always labelled as inferences downstream — never stated as fact.

| id | type | label | confidence |
|----|------|-------|------------|
| `acme_q3_sync_0615:inf:overall_sentiment` | overall_sentiment | overall_sentiment: aligned, decisive | 0.8 |
| `acme_q3_sync_0615:inf:urgency` | urgency | urgency: high | 0.8 |
| `acme_q3_sync_0615:inf:df0` | decision_firmness | decision_firmness: d1: locked | 0.95 |
| `acme_q3_sync_0615:inf:cs0` | commitment_strength | commitment_strength: a1: firm | 0.9 |

## CHUNKS collection

Raw transcript, sliced into windows for semantic search (see Doc 3 for the
chunking deep-dive).

| id | t_start–t_end | speakers | preview |
|----|---------------|----------|---------|
| `acme_q3_sync_0615:chunk:0` | 00:12–01:10 | Dana,Marcus,Priya | [00:12] Marcus: Main thing today — we still haven't picked the databas… |
| `acme_q3_sync_0615:chunk:1` | 01:18–01:52 | Marcus,Priya | [01:18] Marcus: No, the API stays the same. You're fine. [01:25] Priya… |
| `acme_q3_sync_0615:chunk:2` | 01:58–02:05 | Dana,Priya | [01:58] Dana: Yep, Wednesday works. [02:05] Priya: Great. The Acme lau… |
