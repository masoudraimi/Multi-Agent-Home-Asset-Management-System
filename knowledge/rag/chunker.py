"""Chunking for long-form reference text (appliance manuals, care guides).

Structured short records (plant care, checklist items) don't go through
this — they're already atomic and are stored directly by
`knowledge/rag/indexer.py`. This module exists for the other real shape of
content the app ingests: free text a user pastes in (a manual excerpt, a
care guide) that's too long for one embedding to represent well.

Uses LlamaIndex's `SentenceSplitter` (`llama-index-core`, importable
standalone — no full LlamaIndex app/index needed) for sentence-aware
boundaries rather than a naive character split, so a chunk doesn't get cut
mid-sentence.
"""

from __future__ import annotations

from llama_index.core.node_parser import SentenceSplitter

# SentenceSplitter's chunk_size/chunk_overlap are token counts (its default
# tokenizer), not characters — sized here to land near ~800 chars / ~120
# chars overlap for typical English text (~4 chars/token).
_DEFAULT_CHUNK_SIZE_TOKENS = 200
_DEFAULT_CHUNK_OVERLAP_TOKENS = 30

_splitter = SentenceSplitter(
    chunk_size=_DEFAULT_CHUNK_SIZE_TOKENS,
    chunk_overlap=_DEFAULT_CHUNK_OVERLAP_TOKENS,
)


def chunk_text(text: str) -> list[str]:
    """Split `text` into sentence-aware chunks suitable for embedding."""
    text = text.strip()
    if not text:
        return []
    return _splitter.split_text(text)
