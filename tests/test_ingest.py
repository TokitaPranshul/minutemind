import json
import shutil
from pathlib import Path

import pytest

BASE = Path(__file__).parent.parent
TEST_CHROMA = str(BASE / ".chroma_test_ingest")


@pytest.fixture(scope="module")
def ingested():
    # fresh store
    shutil.rmtree(TEST_CHROMA, ignore_errors=True)
    from ingest.graph import build_graph
    from store import Store

    data = json.loads((BASE / "sample" / "q3_sync.json").read_text())
    graph = build_graph()
    result = graph.invoke(
        {"raw_input": data, "halt": False, "chroma_path": TEST_CHROMA}
    )
    assert not result.get("halt"), f"ingestion halted: {result.get('halt_reason')}"
    store = Store(TEST_CHROMA)
    facts = store.get_all_facts("acme_internal")
    inferences = store.get_inferences("acme_internal")
    yield {"result": result, "facts": facts, "inferences": inferences, "store": store}
    shutil.rmtree(TEST_CHROMA, ignore_errors=True)


def _fact_texts(facts):
    return [f["text"].lower() + " " + (f["metadata"].get("evidence_quote", "").lower()) for f in facts]


def test_decision_postgres_stored(ingested):
    """1. A Postgres decision exists, PASSed the gate, stored in facts."""
    facts = ingested["facts"]
    decisions = [f for f in facts if f["metadata"].get("type") == "decision"]
    blob = " ".join(_fact_texts(decisions))
    assert "postgres" in blob, f"no Postgres decision found in: {[d['text'] for d in decisions]}"


def test_action_marcus_migration(ingested):
    """2. Action item owner=Marcus, task ~ migration plan, due ~ Friday."""
    facts = ingested["facts"]
    actions = [f for f in facts if f["metadata"].get("type") == "action_item"]
    marcus = [
        a
        for a in actions
        if (a["metadata"].get("owner") or "").lower() == "marcus"
        or "marcus" in (a["metadata"].get("evidence_speaker", "").lower())
    ]
    blob = " ".join(a["text"].lower() for a in actions)
    assert "migration" in blob, f"no migration-plan action item: {[a['text'] for a in actions]}"
    # due ~ Friday somewhere among actions
    dues = " ".join((a["metadata"].get("due") or "").lower() for a in actions)
    assert "friday" in dues or "friday" in blob


def test_action_dana_mockups(ingested):
    """3. Action item owner=Dana, task ~ dashboard mockups, due ~ Wednesday."""
    facts = ingested["facts"]
    actions = [f for f in facts if f["metadata"].get("type") == "action_item"]
    blob = " ".join(a["text"].lower() for a in actions)
    assert "mockup" in blob or "dashboard" in blob, f"no dashboard mockup action: {[a['text'] for a in actions]}"
    dues = " ".join((a["metadata"].get("due") or "").lower() for a in actions) + " " + blob
    assert "wednesday" in dues


def test_redo_charts_dropped(ingested):
    """4. The over-read 'redo dashboard charts' item is DROPPED by the gate."""
    facts = ingested["facts"]
    for f in facts:
        text = f["text"].lower()
        # a fact that claims charts must be redone should not exist
        assert not ("redo" in text and "chart" in text), f"over-read fact survived: {f['text']}"
    # also confirm the grounding report dropped something OR no such fact exists
    report = ingested["result"].get("grounding_report", {})
    # the negation quote must not have produced a surviving 'redo charts' fact
    blob = " ".join(f["text"].lower() for f in facts)
    assert "redo the charts" not in blob


def test_urgency_inference_present(ingested):
    """5. An urgency inference is in inferences (and NOT in facts)."""
    inferences = ingested["inferences"]
    urgency = [i for i in inferences if i["metadata"].get("type") == "urgency"]
    assert urgency, f"no urgency inference. inference types: {[i['metadata'].get('type') for i in inferences]}"
    # NOT in facts collection
    facts = ingested["facts"]
    for f in facts:
        assert f["metadata"].get("type") != "urgency"


def test_every_record_company_id(ingested):
    """6. Every stored record carries company_id=acme_internal."""
    store = ingested["store"]
    for f in ingested["facts"]:
        assert f["metadata"].get("company_id") == "acme_internal"
    for i in ingested["inferences"]:
        assert i["metadata"].get("company_id") == "acme_internal"
    chunks = store.chunks.get(where={"company_id": "acme_internal"})
    assert chunks["ids"], "no chunks stored"
    for m in chunks["metadatas"]:
        assert m.get("company_id") == "acme_internal"
