"""Gemini embedding client: gemini-embedding-2 wrappers with retry + batching."""
from __future__ import annotations

import logging
import random
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

MODEL = "gemini-embedding-2"

# Task instruction formats documented for gemini-embedding-2 (no task_type param).
QUERY_PREFIX = "task: search result | query: "
INLINE_LIMIT_BYTES = 19 * 1024 * 1024  # ~20MB inline_data payload cap; use Files API above this


class EmbeddingError(RuntimeError):
    pass


def _client() -> genai.Client:
    if not settings.gemini_api_key:
        raise EmbeddingError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key "
            "from https://aistudio.google.com/apikey"
        )
    return genai.Client(api_key=settings.gemini_api_key)


def _backoff(attempt: int) -> float:
    return min(30.0, (2 ** attempt) + random.uniform(0, 1))


def _retryable(exc: Exception) -> bool:
    """Retry on rate limits and server errors, never on auth/argument errors."""
    text = str(exc)
    name = type(exc).__name__
    retryable_names = ("ServerError", "APIError", "APICallError", "ClientError", "GenAiError")
    if name in retryable_names or any(r in name for r in ("Error",)):
        # 4xx client errors are only retryable when rate-limit (429)
        for code in ("429", "500", "502", "503", "504", "UNAVAILABLE", "DEADLINE_EXCEEDED", "RESOURCE_EXHAUSTED"):
            if code in text:
                return True
        return name == "ServerError"  # 5xx from the API
    return False


def _with_retries(fn, *, label: str, attempts: int = 5):
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - classify below
            last = exc
            if not _retryable(exc):
                raise
            wait = _backoff(attempt)
            logger.warning("Gemini %s attempt %d/%d failed (%s); retrying in %.1fs",
                           label, attempt + 1, attempts, exc, wait)
            time.sleep(wait)
    raise EmbeddingError(f"Gemini embedding failed after {attempts} attempts: {last}")


def _embed_contents(contents: list[types.Content], *, label: str) -> list[list[float]]:
    """Embed a list of Content objects -> one embedding per Content."""
    client = _client()
    result = client.models.embed_content(
        model=MODEL,
        contents=contents,
        config=types.EmbedContentConfig(output_dimensionality=settings.embed_dim),
    )
    embeddings = [list(e.values) for e in result.embeddings]
    if len(embeddings) != len(contents):
        raise EmbeddingError(
            f"{label}: expected {len(contents)} embeddings, got {len(embeddings)}"
        )
    for vec in embeddings:
        if len(vec) != settings.embed_dim:
            raise EmbeddingError(
                f"{label}: embedding dim {len(vec)} != configured {settings.embed_dim}"
            )
    return embeddings


def embed_query(question: str) -> list[float]:
    """Embed a search query with the search task instruction."""
    content = types.Content(role="user", parts=[types.Part.from_text(text=QUERY_PREFIX + question)])
    return _with_retries(lambda: _embed_contents([content], label="query"), label="query")[0]


def embed_doc_texts(items: list[tuple[str, str]]) -> list[list[float]]:
    """Embed document chunks. items: [(title, chunk_text)] -> one embedding each.

    Documents use the asymmetric format: 'title: {title} | text: {content}'.
    """
    if not items:
        return []

    def fmt(title: str, body: str) -> types.Content:
        text = f"title: {title or 'none'} | text: {body}"
        return types.Content(role="user", parts=[types.Part.from_text(text=text)])

    out: list[list[float]] = []
    batch_size = max(1, settings.embed_batch_size)
    i = 0
    while i < len(items):
        batch = items[i : i + batch_size]
        contents = [fmt(t, b) for t, b in batch]

        def call(bs: int) -> list[list[float]]:
            return _embed_contents(contents[:bs], label=f"doc-batch@{i}")

        try:
            out.extend(_with_retries(lambda: call(len(batch)), label=f"doc-batch@{i}"))
        except EmbeddingError:
            # Adaptive halving: token/rate errors on big batches -> split and retry
            if len(batch) > 1:
                logger.warning("Batch of %d failed; halving and retrying as two calls", len(batch))
                out.extend(embed_doc_texts(batch[: len(batch) // 2]))
                out.extend(embed_doc_texts(batch[len(batch) // 2 :]))
            else:
                raise
        i += batch_size
    return out


def embed_file_part(path: Path, mime_type: str, *, caption: str | None = None) -> list[float]:
    """Embed a single media/PDF file part (whole file or one PDF segment).

    Files <= ~19MB are sent inline; larger go through the Files API (upload,
    poll until ACTIVE, embed from URI, then delete the remote file).
    """
    size = path.stat().st_size
    if size <= INLINE_LIMIT_BYTES:
        data = path.read_bytes()
        parts = [types.Part.from_bytes(data=data, mime_type=mime_type)]
        if caption:
            parts.append(types.Part.from_text(text=caption))
        content = types.Content(role="user", parts=parts)
        return _with_retries(lambda: _embed_contents([content], label=str(path.name)), label=str(path.name))[0]

    # Files API path for large files
    client = _client()
    uploaded = client.files.upload(
        file=str(path), config=types.UploadFileConfig(mime_type=mime_type)
    )
    try:
        deadline = time.time() + 300
        while True:
            f = client.files.get(name=uploaded.name)
            state = str(getattr(f, "state", "") or "")
            if "ACTIVE" in state.upper():
                break
            if "FAILED" in state.upper():
                raise EmbeddingError(f"Files API upload of {path.name} failed state={state}")
            if time.time() > deadline:
                raise EmbeddingError(f"Files API upload of {path.name} never became ACTIVE")
            time.sleep(2)
        content = types.Content(
            role="user",
            parts=[types.Part.from_uri(file_uri=f.uri, mime_type=mime_type)],
        )
        return _with_retries(lambda: _embed_contents([content], label=str(path.name)), label=str(path.name))[0]
    finally:
        try:
            client.files.delete(name=uploaded.name)
        except Exception:  # noqa: BLE001 - best-effort cleanup
            logger.debug("Failed to delete Files API object for %s", path.name)
