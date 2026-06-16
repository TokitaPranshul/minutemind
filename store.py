"""Chroma wrapper. Three collections: chunks, facts, inferences.

HARD RULE: company_id is a mandatory `where` filter on EVERY retrieval.
Facts and inferences live in separate collections and never cross.
"""
import chromadb

import config


def _and(company_id, where_extra=None):
    """Build a Chroma `where` clause that always pins company_id.

    ChromaDB 1.x accepts direct-equality syntax {'field': value} in both
    collection.get() and collection.query(), whereas the {'field': {'$eq': value}}
    form only works in query(). Use direct equality so one helper covers both.
    """
    conditions = [{"company_id": company_id}]
    if where_extra:
        for key, value in where_extra.items():
            if value is None:
                continue
            conditions.append({key: value})
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


class Store:
    def __init__(self, path=None):
        self.path = path or config.CHROMA_PATH
        self.client = chromadb.PersistentClient(path=self.path)
        self.chunks = self.client.get_or_create_collection("chunks")
        self.facts = self.client.get_or_create_collection("facts")
        self.inferences = self.client.get_or_create_collection("inferences")

    # ---- writes -----------------------------------------------------------
    def add_chunk(self, chunk_id, text, embedding, metadata):
        self.chunks.add(
            ids=[chunk_id], documents=[text], embeddings=[embedding], metadatas=[metadata]
        )

    def add_fact(self, fact_id, text, embedding, metadata):
        self.facts.add(
            ids=[fact_id], documents=[text], embeddings=[embedding], metadatas=[metadata]
        )

    def add_inference(self, inf_id, text, embedding, metadata):
        self.inferences.add(
            ids=[inf_id], documents=[text], embeddings=[embedding], metadatas=[metadata]
        )

    # ---- semantic queries (top-k) -----------------------------------------
    def query_chunks(self, embedding, company_id, n_results=5):
        return self._query(self.chunks, embedding, company_id, n_results)

    def query_facts(self, embedding, company_id, n_results=5):
        return self._query(self.facts, embedding, company_id, n_results)

    def query_inferences(self, embedding, company_id, n_results=5):
        return self._query(self.inferences, embedding, company_id, n_results)

    def _query(self, collection, embedding, company_id, n_results):
        res = collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=_and(company_id),
        )
        out = []
        ids = res.get("ids", [[]])[0]
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        for i in range(len(ids)):
            out.append(
                {
                    "id": ids[i],
                    "text": docs[i],
                    "metadata": metas[i],
                    "distance": dists[i] if i < len(dists) else None,
                }
            )
        return out

    # ---- structured-filter queries (COMPLETE set, not top-k) --------------
    def get_facts(self, company_id, where_extra=None):
        return self._get(self.facts, company_id, where_extra)

    def get_inferences(self, company_id, where_extra=None):
        return self._get(self.inferences, company_id, where_extra)

    def get_all_facts(self, company_id):
        return self._get(self.facts, company_id, None)

    def _get(self, collection, company_id, where_extra):
        res = collection.get(where=_and(company_id, where_extra))
        out = []
        ids = res.get("ids", [])
        docs = res.get("documents", []) or []
        metas = res.get("metadatas", []) or []
        for i in range(len(ids)):
            out.append(
                {
                    "id": ids[i],
                    "text": docs[i] if i < len(docs) else "",
                    "metadata": metas[i] if i < len(metas) else {},
                }
            )
        return out
