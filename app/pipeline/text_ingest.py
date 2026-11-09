"""Text document ingestion: chunk -> embed -> rows."""
from __future__ import annotations

from pathlib import Path

from app import db, gemini_client
from app.chunker import chunk_text, extract_title


def ingest_text(doc: dict, path: Path) -> int:
    """Returns number of chunks embedded. Raises on failure."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    title = extract_title(raw, fallback=path.name)
    chunks = chunk_text(raw)
    if not chunks:
        raise ValueError(f"No extractable text in {path.name}")

    db.update_document(doc["id"], title=title)

    embeddings = gemini_client.embed_doc_texts([(title, c) for c in chunks])
    rows = [
        {
            "document_id": doc["id"],
            "chunk_index": i,
            "modality": "text",
            "title": title,
            "content_text": chunk,
            "embedding": emb,
            "source_path": str(path),
            "metadata": {"char_count": len(chunk)},
        }
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
    ]
    db.insert_chunks(rows)
    return len(rows)
