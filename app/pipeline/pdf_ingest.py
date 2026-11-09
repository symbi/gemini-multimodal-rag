"""PDF ingestion: split into token-budgeted page parts, embed bytes + extracted text."""
from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from app import db, gemini_client
from app.config import settings

logger = logging.getLogger(__name__)

TOKEN_BUDGET = 8192
VISUAL_TOKENS_PER_PAGE = 258
CHARS_PER_TOKEN = 4  # rough heuristic


def _part_bytes(reader: PdfReader, start: int, end: int) -> bytes:
    writer = PdfWriter()
    for page_num in range(start, end):
        writer.add_page(reader.pages[page_num])
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _extract_part_text(reader: PdfReader, start: int, end: int) -> str:
    texts = []
    for page_num in range(start, end):
        try:
            texts.append(reader.pages[page_num].extract_text() or "")
        except Exception:  # noqa: BLE001 - one bad page must not kill the part
            texts.append("")
    return "\n\n".join(t for t in texts if t.strip())


def _plan_parts(reader: PdfReader, total_pages: int) -> list[tuple[int, int]]:
    """Group pages into parts under the token budget (hard cap 6 pages/part).

    Each page costs 258 visual tokens + extracted text tokens. Dense pages
    shrink the part size automatically.
    """
    parts: list[tuple[int, int]] = []
    max_pages = max(1, min(settings.pdf_part_pages, 6))
    start = 0
    while start < total_pages:
        end = min(start + max_pages, total_pages)
        # shrink while the estimated tokens exceed the budget
        while end - start > 1:
            text_len = sum(len(reader.pages[p].extract_text() or "") for p in range(start, end))
            est_tokens = (end - start) * VISUAL_TOKENS_PER_PAGE + text_len // CHARS_PER_TOKEN
            if est_tokens <= TOKEN_BUDGET * 0.9:  # 10% headroom
                break
            end -= 1
        parts.append((start, end))
        start = end
    return parts


def ingest_pdf(doc: dict, path: Path) -> int:
    reader = PdfReader(path)
    if reader.is_encrypted:
        # try empty password before giving up
        try:
            reader.decrypt("")
        except Exception:  # noqa: BLE001
            raise ValueError(f"PDF {path.name} is encrypted and cannot be read")

    total_pages = len(reader.pages)
    parts = _plan_parts(reader, total_pages)

    db.update_document(doc["id"], title=path.stem)

    rows = []
    for idx, (start, end) in enumerate(parts):
        pdf_bytes = _part_bytes(reader, start, end)
        text = _extract_part_text(reader, start, end)
        content_text = (
            f"[PDF {path.name}, pages {start + 1}-{end}]\n{text}"
            if text.strip()
            else f"[PDF {path.name}, pages {start + 1}-{end}, scanned/no extractable text]"
        )
        tmp = path.with_name(f"{path.stem}.part{idx}.pdf")
        tmp.write_bytes(pdf_bytes)
        try:
            emb = gemini_client.embed_file_part(tmp, "application/pdf")
        finally:
            tmp.unlink(missing_ok=True)
        rows.append(
            {
                "document_id": doc["id"],
                "chunk_index": idx,
                "modality": "pdf",
                "title": f"{path.stem} (pages {start + 1}-{end})",
                "content_text": content_text,
                "embedding": emb,
                "source_path": str(path),
                "metadata": {"page_start": start + 1, "page_end": end, "pages": total_pages},
            }
        )
    db.insert_chunks(rows)
    return len(rows)
