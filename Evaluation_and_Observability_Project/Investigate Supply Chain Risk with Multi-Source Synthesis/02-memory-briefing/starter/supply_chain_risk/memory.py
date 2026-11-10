"""Shared memory — a Chroma DB vector store all agents read from and write to.

Claims from every source are embedded with a local sentence-transformers model
(no API key, offline) so any step can semantically retrieve related claims
across sources — the basis for corroboration and conflict detection. Provenance
travels with each claim: the full `Claim` is serialized into metadata and
reconstructed on retrieval, so source/date/confidence survive the round-trip.

Production note: swap the local embedding function for a hosted embeddings
provider (e.g. Voyage AI) without changing the interface.
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Any

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from .models import Claim

EMBED_MODEL = "all-MiniLM-L6-v2"
COLLECTION = "supply_chain_claims"


def _claim_id(claim: Claim) -> str:
    key = f"{claim.source}|{claim.metric_id}|{claim.claim}"
    return hashlib.sha1(key.encode()).hexdigest()


def _document(claim: Claim) -> str:
    return f"{claim.claim} {claim.evidence}"


class SharedMemory:
    """A Chroma-backed store of claims with semantic cross-source retrieval."""

    def __init__(self, embedding_model: str = EMBED_MODEL) -> None:
        self._client = chromadb.EphemeralClient(settings=Settings(anonymized_telemetry=False))
        embed: Any = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )
        # TODO: Create the collection. The in-process EphemeralClient caches one
        #   system per process, so a FIXED collection name collides across
        #   SharedMemory instances ("Collection already exists"). Give each
        #   instance a UNIQUE collection name, e.g. f"{COLLECTION}_{uuid.uuid4().hex}".
        unique_name = f"{COLLECTION}_{uuid.uuid4().hex}"
        self._collection = self._client.create_collection(
            name=unique_name,
            embedding_function=embed,
        )

    def add_claims(self, claims: list[Claim]) -> None:
        """Upsert claims; embeds claim+evidence, stores provenance as metadata."""
        if not claims:
            return
        # TODO: Build parallel lists of ids (_claim_id), documents (_document), and
        #   metadata, then self._collection.upsert(ids=, documents=, metadatas=).
        #   Chroma metadata values must be str/int/float/bool — None, lists, and
        #   tuples are rejected. Store source_date as an ISO string, and store the
        #   whole claim as JSON (c.model_dump_json()) so it can be rehydrated intact.
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for claim in claims:
            cid = _claim_id(claim)
            doc = _document(claim)
            meta = {
                "claim_json": claim.model_dump_json(),
                "source": claim.source,
                "source_date": claim.source_date.isoformat(),
                "confidence": float(claim.confidence),
                "metric_id": claim.metric_id,
            }
            ids.append(cid)
            documents.append(doc)
            metadatas.append(meta)

        self._collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        
    def _hydrate(self, metadatas: Any) -> list[Claim]:
        if not metadatas:
            return []
        flat_metas = metadatas[0] if isinstance(metadatas, list) and len(metadatas) > 0 and isinstance(metadatas[0], list) else metadatas
        return [Claim.model_validate_json(str(m["claim_json"])) for m in flat_metas if m and "claim_json" in m]
    
    def search(self, query: str, k: int = 5) -> list[Claim]:
        """Return the k claims most semantically similar to `query`."""
        # TODO: Query the collection with query_texts=[query] and hydrate the
        #   returned metadatas back into Claims.
        total_count = self.count()
        if total_count == 0:
            return []
        n_results = min(k, total_count)
        result = self._collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["metadatas"]
        )
        metadatas = result.get("metadatas", [])
        return self._hydrate(metadatas)
    
    def related_to(self, claim: Claim, k: int = 5) -> list[Claim]:
        """Return claims similar to `claim`, excluding the claim itself."""
        # TODO: Query with the claim's document text, then drop the claim itself
        #   (match on _claim_id) before hydrating and returning up to k claims.
        total_count = self.count()
        if total_count == 0:
            return []
        target_id = _claim_id(claim)
        doc = _document(claim)

        n_results = min(k + 1, total_count)
        # Chroma returns IDs by default; "ids" is not a valid explicit include option.
        result = self._collection.query(
            query_texts=[doc],
            n_results=n_results,
            include=["metadatas"]
        )

        metadatas_list = result.get("metadatas", [[]])
        ids_list = result.get("ids", [[]])

        filtered_metas = []
        for m_list, id_list in zip(metadatas_list, ids_list):
            for m, cid in zip(m_list, id_list):
                if cid != target_id:
                    filtered_metas.append(m)
                if len(filtered_metas) >= k:
                    break
            if len(filtered_metas) >= k:
                break

        return self._hydrate(filtered_metas)

    def count(self) -> int:
        return int(self._collection.count())
    