"""Ingest a long-form document (e.g. a pasted appliance manual excerpt) into
an agent's semantic memory, with chunking + provenance metadata for citation.

Structured short records (plant care, checklist items — see indexer.py) skip
this path entirely; they're already atomic and stored directly.
"""

from __future__ import annotations

from core.memory.semantic import SemanticMemory
from knowledge.rag.chunker import chunk_text


def ingest_document(*, agent_name: str, source_name: str, text: str, doc_type: str = "manual") -> int:
    """Chunk `text` and store each chunk in `agent_name`'s semantic memory.

    Returns the number of chunks stored. Metadata shape matches indexer.py's
    convention (`source`, plus a `source_type` discriminator) so retrieval
    can render a consistent [source#id] citation regardless of whether the
    hit came from a structured record or an ingested document.
    """
    mem = SemanticMemory(agent_name)
    chunks = chunk_text(text)
    for i, chunk in enumerate(chunks):
        mem.store(chunk, metadata={
            "source": source_name,
            "source_type": doc_type,
            "chunk_index": i,
            "chunk_count": len(chunks),
        })
    return len(chunks)
