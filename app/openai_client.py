"""OpenAI Codex reasoning over retrieved chunks (Responses API)."""
from __future__ import annotations

import logging
import re

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the reasoning engine of a multimodal RAG system.
You are given numbered context chunks retrieved from a vector database by
semantic similarity to the user's question. Chunks may be text, PDF pages,
or placeholders for images/videos/audio (e.g. "[image: cat.jpg]") — the
retrieval matched their content embeddings even though you only see the label.

Answer the user's question using the context chunks.

Rules:
1. Base your answer on the numbered chunks. Cite every fact with [n] markers
   referring to chunk numbers, e.g. "The launch date is March 3 [1][2]."
2. If the chunks are insufficient, say what's missing and answer from general
   knowledge only if clearly flagged: prefix that part with "Beyond the
   documents:".
3. Be concise. Prefer short paragraphs or bullets. Markdown is rendered."""

_CITATION_RE = re.compile(r"\[(\d{1,2})\]")


def answer_question(question: str, context_block: str, top_k: int) -> tuple[str, list[int]]:
    """Ask Codex. Returns (answer_text, cited_chunk_numbers)."""
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to .env (https://platform.openai.com/api-keys)."
        )
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.responses.create(
        model=settings.codex_model,
        instructions=SYSTEM_PROMPT,
        input=(
            f"Retrieved context chunks (top {top_k}, ordered by similarity):\n\n"
            f"{context_block}\n\n"
            f"User question: {question}"
        ),
    )
    answer = response.output_text
    cited = sorted({int(m) for m in _CITATION_RE.findall(answer)})
    return answer, cited


def parse_citations(text: str) -> list[int]:
    """Standalone parser for tests/other callers."""
    return sorted({int(m) for m in _CITATION_RE.findall(text)})
