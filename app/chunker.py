"""Paragraph-aware text chunking with overlap."""
from __future__ import annotations
import re

_SENTENCE_END = re.compile(r"(?<=[.!?。！？])\s+")
_PARA_SPLIT = re.compile(r"\n\s*\n")


def extract_title(text: str, fallback: str = "untitled") -> str:
    """First non-empty line, trimmed to 80 chars — used as the doc-format title."""
    for line in text.splitlines():
        s = line.strip().lstrip("#").strip()
        if s:
            return s[:80]
    return fallback


def chunk_text(
    text: str,
    max_chars: int = 1500,
    overlap: int = 200,
) -> list[str]:
    """Split text into chunks of ~max_chars with `overlap` chars carried over.

    Prefers paragraph boundaries, then sentence boundaries, then hard-splits
    long paragraphs. Never returns empty chunks.
    """
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in _PARA_SPLIT.split(text) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if current:
            chunks.append("\n\n".join(current))
            current, current_len = [], 0

    for para in paragraphs:
        # Hard-split any paragraph longer than max_chars, on sentence boundaries where possible
        while len(para) > max_chars:
            flush()
            cut = _find_cut(para, max_chars)
            chunks.append(para[:cut].strip())
            para = para[max(0, cut - overlap) :].strip()
        if current_len + len(para) + 2 > max_chars:
            flush()
        current.append(para)
        current_len += len(para) + 2
    flush()

    # Ensure overlap between consecutive chunks that came from flush() of full
    # paragraphs isn't strictly necessary (embedding context is large); the
    # overlap on hard-splits above preserves continuity for long paragraphs.
    return [c for c in chunks if c]


def _find_cut(para: str, max_chars: int) -> int:
    """Best cut position <= max_chars: sentence boundary, then word, then hard."""
    window = para[:max_chars]
    m = None
    for m in _SENTENCE_END.finditer(window):
        pass
    if m and m.end() > max_chars // 2:
        return m.end()
    sp = window.rfind(" ")
    if sp > max_chars // 2:
        return sp + 1
    return max_chars
