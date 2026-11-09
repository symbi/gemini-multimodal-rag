"""Query-side retrieval: embed question -> top-k chunks -> context block."""
from __future__ import annotations

from app import db, gemini_client
from app.config import settings

MAX_CONTEXT_CHARS = 24_000  # hard cap on assembled context


def search(question: str, top_k: int | None = None, modality: str | None = None) -> list[dict]:
    """Embed the question and fetch top-k chunks from Supabase."""
    k = top_k or settings.top_k
    query_emb = gemini_client.embed_query(question)
    return db.match_chunks(query_emb, match_count=k, filter_modality=modality)


def build_context_block(chunks: list[dict]) -> str:
    """Number the chunks into a context block for the reasoning model."""
    parts: list[str] = []
    total = 0
    for i, ch in enumerate(chunks, start=1):
        body = (ch.get("content_text") or "").strip() or "[no text content]"
        entry = f"[{i}] {ch.get('filename', '?')} ({ch.get('modality', '?')}): {body}"
        if total + len(entry) > MAX_CONTEXT_CHARS:
            remain = max(0, MAX_CONTEXT_CHARS - total)
            if remain > 200:  # keep a truncated tail entry only if it's meaningful
                parts.append(entry[:remain] + " …[truncated]")
            break
        parts.append(entry)
        total += len(entry)
    return "\n\n".join(parts)
