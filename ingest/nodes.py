"""Ingestion graph nodes.

intake -> validate -> speaker_resolution -> analyzer -> grounding_gate -> indexer
"""
import json

import config
import llm
from schemas import AnalyzerOutput, GroundingVerdict
from store import Store

PROMPTS = config.PROMPTS_DIR


def _load_prompt(name):
    return (PROMPTS / name).read_text()


def _t_to_seconds(t):
    """Parse 'mm:ss' (or 'hh:mm:ss') to seconds; tolerant of junk."""
    try:
        parts = [int(p) for p in str(t).split(":")]
    except ValueError:
        return None
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return None


def _format_transcript(segments):
    lines = []
    for s in segments:
        lines.append(f"[{s.get('t','')}] {s.get('speaker','')}: {s.get('text','')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# intake
# ---------------------------------------------------------------------------
def intake(state):
    raw = state.get("raw_input") or {}
    print("\n=== [intake] received ===")
    print(f"  keys: {list(raw.keys())}")
    required = ["company_id", "meeting_id", "segments"]
    missing = [k for k in required if not raw.get(k)]
    if missing:
        reason = f"malformed input, missing: {missing}"
        print(f"  HALT: {reason}")
        return {"halt": True, "halt_reason": reason}
    company_id = raw["company_id"]
    print(f"  company_id={company_id} meeting_id={raw['meeting_id']} segments={len(raw['segments'])}")
    return {"company_id": company_id, "halt": False}


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------
def validate(state):
    raw = state["raw_input"]
    segments = raw.get("segments", [])
    print("\n=== [validate] ===")
    if not segments:
        print("  HALT: no segments")
        return {"halt": True, "halt_reason": "no segments"}
    with_speaker = sum(1 for s in segments if s.get("speaker", "").strip())
    well_formed = sum(
        1
        for s in segments
        if s.get("speaker", "").strip()
        and str(s.get("t", "")).strip()
        and s.get("text", "").strip()
    )
    coverage = with_speaker / len(segments)
    print(f"  segments={len(segments)} diarization_coverage={coverage:.0%} well_formed={well_formed}")
    if coverage < 0.8:
        reason = f"diarization coverage {coverage:.0%} below 80%"
        print(f"  HALT: {reason}")
        return {"halt": True, "halt_reason": reason}
    print("  PASS")
    return {"halt": False}


# ---------------------------------------------------------------------------
# speaker_resolution
# ---------------------------------------------------------------------------
def speaker_resolution(state):
    raw = state["raw_input"]
    print("\n=== [speaker_resolution] ===")
    transcript = [
        {"speaker": s.get("speaker", ""), "t": s.get("t", ""), "text": s.get("text", "")}
        for s in raw.get("segments", [])
    ]
    print(f"  resolved {len(transcript)} segments (names already present -> pass-through)")
    return {"transcript_of_record": transcript}


# ---------------------------------------------------------------------------
# analyzer
# ---------------------------------------------------------------------------
def analyzer(state):
    print("\n=== [analyzer] ===")
    transcript = state["transcript_of_record"]
    transcript_text = _format_transcript(transcript)
    prompt_template = _load_prompt("analyzer.txt")
    system = prompt_template.replace("{transcript_of_record}", transcript_text)
    user = "Extract the grounded record now. Output only the JSON object."

    last_error = None
    for attempt in range(2):
        try:
            sys_prompt = system
            if attempt > 0:
                sys_prompt = (
                    system
                    + f"\n\n# PREVIOUS ATTEMPT FAILED VALIDATION\nError: {last_error}\n"
                    + "Return corrected JSON that exactly matches the SCHEMA."
                )
            raw_out = llm.chat(sys_prompt, user, json=True, temperature=0.1)
            parsed = AnalyzerOutput.model_validate(raw_out)
            meeting_id = state["raw_input"].get("meeting_id")
            data = parsed.model_dump()
            data["meeting_id"] = meeting_id
            print(
                f"  extracted: {len(data['facts']['decisions'])} decisions, "
                f"{len(data['facts']['action_items'])} action_items, "
                f"{len(data['facts']['entities'])} entities"
            )
            print(f"  summary: {data['summary'][:120]}")
            return {"analyzer_output": data, "halt": False}
        except Exception as e:  # noqa: BLE001
            last_error = str(e)
            print(f"  attempt {attempt + 1} failed: {last_error[:200]}")

    print("  HALT: analyzer produced unparseable JSON twice")
    return {"halt": True, "halt_reason": f"analyzer JSON validation failed: {last_error}"}


# ---------------------------------------------------------------------------
# grounding_gate
# ---------------------------------------------------------------------------
def _normalize(s):
    """Lowercase + collapse whitespace for fuzzy quote matching."""
    import re, unicodedata
    s = unicodedata.normalize("NFKD", s)
    s = s.lower()
    # strip punctuation at word boundaries that LLMs commonly vary
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _quote_exists(transcript, evidence):
    """Code check: quote appears near t spoken by that speaker.

    First tries exact substring match (strict). Falls back to normalised
    comparison so minor punctuation/unicode differences don't drop real facts.
    """
    quote = (evidence.get("quote") or "").strip()
    speaker = (evidence.get("speaker") or "").strip()
    t_sec = _t_to_seconds(evidence.get("t"))
    if not quote:
        return False
    q_norm = _normalize(quote)
    for seg in transcript:
        if seg.get("speaker", "").strip() != speaker:
            continue
        seg_text = seg.get("text", "")
        seg_sec = _t_to_seconds(seg.get("t"))
        in_window = (t_sec is None or seg_sec is None or abs(seg_sec - t_sec) <= 30)
        if not in_window:
            continue
        # exact match
        if quote in seg_text:
            return True
        # normalised fuzzy match (covers punctuation/unicode drift)
        if q_norm and q_norm in _normalize(seg_text):
            return True
    return False


def _context_window(transcript, t, radius=2):
    """Return a few surrounding lines around t."""
    t_sec = _t_to_seconds(t)
    indexed = list(enumerate(transcript))
    center = 0
    if t_sec is not None:
        best = None
        for i, seg in indexed:
            seg_sec = _t_to_seconds(seg.get("t"))
            if seg_sec is None:
                continue
            d = abs(seg_sec - t_sec)
            if best is None or d < best[0]:
                best = (d, i)
        if best:
            center = best[1]
    lo = max(0, center - radius)
    hi = min(len(transcript), center + radius + 1)
    return _format_transcript(transcript[lo:hi])


def grounding_gate(state):
    print("\n=== [grounding_gate] ===")
    analyzer_output = state["analyzer_output"]
    transcript = state["transcript_of_record"]
    judge_prompt = _load_prompt("grounding_judge.txt")

    report = {"passed": [], "dropped": []}
    surviving_decisions = []
    surviving_actions = []

    def judge_fact(claim_label, claim_text, evidence):
        # Step 1: code check (verbatim quote near t by that speaker)
        if not _quote_exists(transcript, evidence):
            reason = "quote not found verbatim near timestamp/speaker"
            print(f"  DROP [{claim_label}] '{claim_text[:60]}' -> {reason}")
            report["dropped"].append(
                {"claim": claim_text, "label": claim_label, "reason": reason, "stage": "code_check"}
            )
            return False
        # Step 2: LLM judge (supports-in-context)
        window = _context_window(transcript, evidence.get("t"))
        # Remind the judge: polite requests ("can you...?") ARE valid evidence for
        # action items — they are assignments, not genuine open questions.
        user = (
            f"CLAIM TYPE: {claim_label}\n"
            f"CLAIM: {claim_text}\n"
            f"CITED EVIDENCE: speaker={evidence.get('speaker')} "
            f"t={evidence.get('t')} quote={evidence.get('quote')!r}\n\n"
            f"TRANSCRIPT WINDOW:\n{window}\n\n"
            f"NOTE: For action_item claims, a polite request ('can you do X?') "
            f"is valid evidence that X was assigned — it is not an open question. "
            f"Only DROP if the quote is a NEGATION ('I don't want to do X') or a "
            f"genuinely hypothetical/conditional statement.\n"
        )
        try:
            raw = llm.chat(judge_prompt, user, json=True, temperature=0.1)
            verdict = GroundingVerdict.model_validate(raw)
        except Exception as e:  # noqa: BLE001
            reason = f"judge JSON failed, dropping safely: {e}"
            print(f"  DROP [{claim_label}] '{claim_text[:60]}' -> {reason}")
            report["dropped"].append(
                {"claim": claim_text, "label": claim_label, "reason": reason, "stage": "judge"}
            )
            return False
        if verdict.verdict.upper() == "PASS" and verdict.supports_claim:
            print(f"  PASS [{claim_label}] '{claim_text[:60]}' -> {verdict.note}")
            report["passed"].append(
                {"claim": claim_text, "label": claim_label, "note": verdict.note}
            )
            return True
        print(f"  DROP [{claim_label}] '{claim_text[:60]}' -> {verdict.note}")
        report["dropped"].append(
            {"claim": claim_text, "label": claim_label, "reason": verdict.note, "stage": "judge"}
        )
        return False

    for d in analyzer_output["facts"]["decisions"]:
        if judge_fact("decision", d["text"], d["evidence"]):
            surviving_decisions.append(d)

    for a in analyzer_output["facts"]["action_items"]:
        label = f"action_item:{a.get('owner')}"
        if judge_fact(label, a["task"], a["evidence"]):
            surviving_actions.append(a)

    analyzer_output["facts"]["decisions"] = surviving_decisions
    analyzer_output["facts"]["action_items"] = surviving_actions

    print(
        f"  grounding done: {len(report['passed'])} passed, "
        f"{len(report['dropped'])} dropped (inferences skip the gate)"
    )
    return {"analyzer_output": analyzer_output, "grounding_report": report}


# ---------------------------------------------------------------------------
# indexer
# ---------------------------------------------------------------------------
def _chunk_segments(segments, size=4):
    chunks = []
    for i in range(0, len(segments), size):
        group = segments[i : i + size]
        if not group:
            continue
        text = _format_transcript(group)
        chunks.append(
            {
                "text": text,
                "t_start": group[0].get("t", ""),
                "t_end": group[-1].get("t", ""),
                "speaker": ",".join(sorted({g.get("speaker", "") for g in group})),
            }
        )
    return chunks


def indexer(state):
    print("\n=== [indexer] ===")
    raw = state["raw_input"]
    analyzer_output = state["analyzer_output"]
    company_id = raw["company_id"]
    meeting_id = raw["meeting_id"]
    date = raw.get("date", "")
    transcript = state["transcript_of_record"]

    store = Store(state.get("chroma_path"))

    fact_count = 0
    inf_count = 0
    chunk_count = 0

    # ---- facts ----
    fact_texts = []
    fact_records = []  # (id, text, metadata)
    for d in analyzer_output["facts"]["decisions"]:
        text = d["text"]
        meta = {
            "type": "decision",
            "text": text,
            "company_id": company_id,
            "meeting_id": meeting_id,
            "date": date,
            "evidence_speaker": d["evidence"]["speaker"],
            "evidence_t": d["evidence"]["t"],
            "evidence_quote": d["evidence"]["quote"],
            "confidence": float(d.get("confidence", 0.0)),
        }
        fact_texts.append(text)
        fact_records.append((f"{meeting_id}:fact:{d['id']}", text, meta))
    for a in analyzer_output["facts"]["action_items"]:
        text = a["task"]
        meta = {
            "type": "action_item",
            "text": text,
            "company_id": company_id,
            "meeting_id": meeting_id,
            "date": date,
            "evidence_speaker": a["evidence"]["speaker"],
            "evidence_t": a["evidence"]["t"],
            "evidence_quote": a["evidence"]["quote"],
            "confidence": float(a.get("confidence", 0.0)),
            "owner": a.get("owner") or "",
            "due": a.get("due") or "",
        }
        fact_texts.append(text)
        fact_records.append((f"{meeting_id}:fact:{a['id']}", text, meta))

    if fact_texts:
        embs = llm.embed(fact_texts)
        for (fid, text, meta), emb in zip(fact_records, embs):
            store.add_fact(fid, text, emb, meta)
            fact_count += 1

    # ---- inferences ----
    inf_records = []  # (id, text, metadata)
    inf = analyzer_output["inferences"]

    def add_inf(inf_type, label, confidence, evidence_t, suffix):
        if not label:
            return
        text = f"{inf_type}: {label}"
        meta = {
            "type": inf_type,
            "label": str(label),
            "confidence": float(confidence or 0.0),
            "company_id": company_id,
            "meeting_id": meeting_id,
            "date": date,
            "evidence_t": json.dumps(evidence_t or []),
        }
        inf_records.append((f"{meeting_id}:inf:{suffix}", text, meta))

    if inf.get("overall_sentiment"):
        s = inf["overall_sentiment"]
        add_inf("overall_sentiment", s.get("label"), s.get("confidence"), s.get("evidence"), "overall_sentiment")
    if inf.get("urgency"):
        u = inf["urgency"]
        add_inf("urgency", u.get("label"), u.get("confidence"), u.get("evidence"), "urgency")
    for i, s in enumerate(inf.get("per_speaker_sentiment", [])):
        add_inf("per_speaker_sentiment", f"{s.get('speaker')}: {s.get('label')}", s.get("confidence"), s.get("evidence"), f"pss{i}")
    for i, df in enumerate(inf.get("decision_firmness", [])):
        add_inf("decision_firmness", f"{df.get('ref')}: {df.get('label')}", df.get("confidence"), df.get("evidence"), f"df{i}")
    for i, cs in enumerate(inf.get("commitment_strength", [])):
        add_inf("commitment_strength", f"{cs.get('ref')}: {cs.get('label')}", cs.get("confidence"), cs.get("evidence"), f"cs{i}")
    for i, rb in enumerate(inf.get("risks_blockers", [])):
        add_inf("risks_blockers", rb.get("desc"), rb.get("confidence"), rb.get("evidence"), f"rb{i}")
    for i, tp in enumerate(inf.get("tension_points", [])):
        add_inf("tension_points", tp.get("desc"), tp.get("confidence"), tp.get("evidence"), f"tp{i}")
    for i, ol in enumerate(inf.get("open_loops", [])):
        add_inf("open_loops", ol.get("desc"), ol.get("confidence"), ol.get("evidence"), f"ol{i}")
    if inf.get("participation_balance"):
        pb = inf["participation_balance"]
        add_inf("participation_balance", pb.get("note"), pb.get("confidence"), [], "participation_balance")

    if inf_records:
        inf_texts = [r[1] for r in inf_records]
        embs = llm.embed(inf_texts)
        for (iid, text, meta), emb in zip(inf_records, embs):
            store.add_inference(iid, text, emb, meta)
            inf_count += 1

    # ---- transcript chunks ----
    chunks = _chunk_segments(transcript)
    if chunks:
        chunk_texts = [c["text"] for c in chunks]
        embs = llm.embed(chunk_texts)
        for i, (c, emb) in enumerate(zip(chunks, embs)):
            meta = {
                "company_id": company_id,
                "meeting_id": meeting_id,
                "date": date,
                "speaker": c["speaker"],
                "t_start": c["t_start"],
                "t_end": c["t_end"],
            }
            store.add_chunk(f"{meeting_id}:chunk:{i}", c["text"], emb, meta)
            chunk_count += 1

    counts = {"facts": fact_count, "inferences": inf_count, "chunks": chunk_count}
    print(f"  indexed: {counts}")
    return {"indexed_counts": counts}
