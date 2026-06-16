# 1 · Input Transcript — `acme_q3_sync_0615`

- **Title:** Q3 platform sync
- **Date:** 2026-06-15
- **Company (tenant):** `acme_internal`
- **Attendees:** Priya, Marcus, Dana
- **Segments:** 10

This is exactly what enters the pipeline — already-transcribed, speaker-
labelled, timestamped text. (Audio capture + transcription is upstream and
out of scope; see README.)

## Conversation

| # | time | speaker | text |
|---|------|---------|------|
| 0 | 00:12 | Marcus | Main thing today — we still haven't picked the database for the new analytics service. We're three weeks from the Acme launch and this is blocking me. |
| 1 | 00:31 | Priya | Right. Last sync we were torn between Postgres and Mongo. Where did we land? |
| 2 | 00:44 | Marcus | I spent the week testing both. Postgres handles our query patterns way better. I want to commit to Postgres. |
| 3 | 01:10 | Dana | Any impact on the dashboard work? I don't want to redo the charts. |
| 4 | 01:18 | Marcus | No, the API stays the same. You're fine. |
| 5 | 01:25 | Priya | Okay, let's lock it — Postgres it is. Marcus, can you write up the migration plan? I'd like it by Friday so we're not scrambling. |
| 6 | 01:40 | Marcus | Friday's tight but doable. I'll have a draft. |
| 7 | 01:52 | Priya | And Dana, send me the final dashboard mockups by Wednesday? |
| 8 | 01:58 | Dana | Yep, Wednesday works. |
| 9 | 02:05 | Priya | Great. The Acme launch is the priority — everything else can slip. |

## Raw JSON (what `run_ingest.py` reads)

```json
{
  "company_id": "acme_internal",
  "meeting_id": "acme_q3_sync_0615",
  "title": "Q3 platform sync",
  "date": "2026-06-15",
  "attendees": [
    "Priya",
    "Marcus",
    "Dana"
  ],
  "segments": [
    {
      "speaker": "Marcus",
      "t": "00:12",
      "text": "Main thing today — we still haven't picked the database for the new analytics service. We're three weeks from the Acme launch and this is blocking me."
    },
    {
      "speaker": "Priya",
      "t": "00:31",
      "text": "Right. Last sync we were torn between Postgres and Mongo. Where did we land?"
    },
    {
      "speaker": "Marcus",
      "t": "00:44",
      "text": "I spent the week testing both. Postgres handles our query patterns way better. I want to commit to Postgres."
    },
    {
      "speaker": "Dana",
      "t": "01:10",
      "text": "Any impact on the dashboard work? I don't want to redo the charts."
    },
    {
      "speaker": "Marcus",
      "t": "01:18",
      "text": "No, the API stays the same. You're fine."
    },
    {
      "speaker": "Priya",
      "t": "01:25",
      "text": "Okay, let's lock it — Postgres it is. Marcus, can you write up the migration plan? I'd like it by Friday so we're not scrambling."
    },
    {
      "speaker": "Marcus",
      "t": "01:40",
      "text": "Friday's tight but doable. I'll have a draft."
    },
    {
      "speaker": "Priya",
      "t": "01:52",
      "text": "And Dana, send me the final dashboard mockups by Wednesday?"
    },
    {
      "speaker": "Dana",
      "t": "01:58",
      "text": "Yep, Wednesday works."
    },
    {
      "speaker": "Priya",
      "t": "02:05",
      "text": "Great. The Acme launch is the priority — everything else can slip."
    }
  ]
}
```