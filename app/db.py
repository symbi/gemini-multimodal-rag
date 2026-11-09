"""Supabase REST client wrapper: documents/chunks CRUD + match_chunks RPC."""
from __future__ import annotations

import logging
import math
from typing import Any

from supabase import create_client

from app.config import settings

logger = logging.getLogger(__name__)

_INSERT_BATCH_ROWS = 500  # keep under the 50MB PostgREST request limit

_client = None


def get_client():
    global _client
    if _client is None:
        if not settings.supabase_service_role_key:
            raise RuntimeError(
                "SUPABASE_SERVICE_ROLE_KEY is not set. Copy .env.example to .env and "
                "paste your service_role key from Supabase Dashboard -> Settings -> API."
            )
        _client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return _client


def vec_literal(values: list[float]) -> str:
    """Full-precision pgvector literal. PostgREST casts the JSON string into vector."""
    return "[" + ",".join(repr(v) for v in values) + "]"


# --- documents ---------------------------------------------------------------

def insert_document(
    filename: str,
    mime_type: str,
    modality: str,
    size_bytes: int,
    source_path: str,
    title: str | None = None,
) -> dict[str, Any]:
    payload = {
        "filename": filename,
        "mime_type": mime_type,
        "modality": modality,
        "size_bytes": size_bytes,
        "source_path": source_path,
        "title": title or filename,
        "status": "pending",
    }
    resp = get_client().table("documents").insert(payload).execute()
    return resp.data[0]


def get_document(doc_id: str) -> dict[str, Any] | None:
    resp = get_client().table("documents").select("*").eq("id", doc_id).execute()
    return resp.data[0] if resp.data else None


def list_documents() -> list[dict[str, Any]]:
    resp = (
        get_client()
        .table("documents")
        .select("*, chunks(count)", count="exact")
        .order("created_at", desc=True)
        .execute()
    )
    # chunks(count) comes back as [{"count": n}] — flatten to chunk_count
    out = []
    for row in resp.data:
        agg = row.pop("chunks", None)
        row["chunk_count"] = agg[0]["count"] if agg else 0
        out.append(row)
    return out


def update_document(doc_id: str, **fields: Any) -> None:
    get_client().table("documents").update(fields).eq("id", doc_id).execute()


def delete_document(doc_id: str) -> None:
    get_client().table("documents").delete().eq("id", doc_id).execute()


def delete_chunks_for(doc_id: str) -> None:
    get_client().table("chunks").delete().eq("document_id", doc_id).execute()


def reset_stale_processing() -> int:
    """On startup: flip any 'processing' rows back to 'pending' (crash recovery)."""
    resp = (
        get_client()
        .table("documents")
        .update({"status": "pending", "error": None})
        .eq("status", "processing")
        .execute()
    )
    return len(resp.data)


# --- chunks ------------------------------------------------------------------

def insert_chunks(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    client = get_client()
    for i in range(0, len(rows), _INSERT_BATCH_ROWS):
        batch = rows[i : i + _INSERT_BATCH_ROWS]
        prepared = [
            {**row, "embedding": vec_literal(row["embedding"])} for row in batch
        ]
        client.table("chunks").insert(prepared).execute()


def match_chunks(
    query_embedding: list[float],
    match_count: int = 5,
    filter_modality: str | None = None,
) -> list[dict[str, Any]]:
    resp = (
        get_client()
        .rpc(
            "match_chunks",
            {
                "query_embedding": vec_literal(query_embedding),
                "match_count": match_count,
                "filter_modality": filter_modality,
            },
        )
        .execute()
    )
    return resp.data or []


def count_chunks() -> int:
    resp = get_client().table("chunks").select("id", count="exact").limit(1).execute()
    return resp.count or 0


def similarity_sort_key(row: dict[str, Any]) -> float:
    sim = row.get("similarity")
    return -math.nan if sim is None else -float(sim)
