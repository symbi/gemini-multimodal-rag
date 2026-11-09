"""Manual verification: gemini-embedding-2 + Supabase round-trip.

Run: uv run python scripts/verify_embedding.py
Reads keys from .env (via app.config). Never prints secrets.
"""
from __future__ import annotations

import math
import sys

from app import db, gemini_client


def l2(vec: list[float]) -> float:
    return math.sqrt(sum(v * v for v in vec))


def cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def main() -> int:
    print("1) embedding a query")
    q = gemini_client.embed_query("What is the revenue for Q3?")
    print(f"   dim={len(q)} l2={l2(q):.6f}")

    print("2) embedding a batch of 3 document chunks")
    vecs = gemini_client.embed_doc_texts([
        ("Q3 Report", "Revenue grew 12% year over year to 4.2 million dollars."),
        ("Q3 Report", "The company announced a new Berlin office in September."),
        ("Other", "Unrelated content about bicycles and mountain trails."),
    ])
    print(f"   count={len(vecs)} dims={ {len(v) for v in vecs} }")
    for i, v in enumerate(vecs):
        print(f"   doc[{i}] l2={l2(v):.6f}")

    print("3) relevance sanity (query vs each doc)")
    sims = [cos(q, v) for v in vecs]
    for i, s in enumerate(sims):
        print(f"   sim(query, doc[{i}]) = {s:.4f}")
    best = max(range(len(sims)), key=lambda i: sims[i])
    print(f"   best match = doc[{best}] (expected doc[0], the revenue chunk)")
    ok = best == 0

    print("4) Supabase round-trip")
    doc = db.insert_document(
        filename="__verify__", mime_type="text/plain", modality="text",
        size_bytes=0, source_path="/tmp/__verify__.txt", title="verify",
    )
    db.insert_chunks([{
        "document_id": doc["id"], "chunk_index": 0, "modality": "text",
        "title": "verify", "content_text": "Revenue grew 12% to 4.2 million dollars.",
        "embedding": q, "source_path": "/tmp/__verify__.txt", "metadata": {},
    }])
    hits = db.match_chunks(q, match_count=3)
    print(f"   match_chunks returned {len(hits)} row(s)")
    for h in hits:
        print(f"   -> {h['filename']} sim={h['similarity']:.4f}")
    rpc_ok = bool(hits) and abs(float(hits[0]["similarity"]) - 1.0) < 1e-6
    db.delete_document(doc["id"])
    print(f"   cleanup: documents={len(db.list_documents())} chunks={db.count_chunks()}")

    print("\nRESULT:", "PASS" if (ok and rpc_ok) else "FAIL")
    return 0 if (ok and rpc_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
