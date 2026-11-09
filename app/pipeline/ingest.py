"""Ingest pipeline router: status transitions + modality dispatch."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app import db
from app.config import settings
from app.pipeline.media_ingest import ingest_media
from app.pipeline.pdf_ingest import ingest_pdf
from app.pipeline.text_ingest import ingest_text

logger = logging.getLogger(__name__)


def process_document(doc_id: str) -> None:
    """Embed one document end-to-end. Safe to re-run (delete-then-insert chunks)."""
    doc = db.get_document(doc_id)
    if doc is None:
        logger.error("Document %s not found", doc_id)
        return
    if doc["status"] == "processing":
        return  # another worker/thread has it

    db.update_document(doc_id, status="processing", error=None)
    try:
        path = Path(doc["source_path"])
        if not path.is_file():
            raise FileNotFoundError(f"Source file missing: {path}")

        n = 0
        if doc["modality"] == "text":
            n = ingest_text(doc, path)
        elif doc["modality"] == "pdf":
            parts = ingest_pdf(doc, path)
            n = parts
        elif doc["modality"] in ("image", "video", "audio"):
            n = ingest_media(doc, path)
        else:
            raise ValueError(f"Unsupported modality: {doc['modality']}")

        db.update_document(doc_id, status="embedded", error=None)
        logger.info("Embedded %s (%s): %d chunk(s)", doc["filename"], doc["modality"], n)
    except Exception as exc:  # noqa: BLE001 - capture everything into status
        logger.exception("Ingest failed for %s", doc_id)
        db.update_document(doc_id, status="failed", error=str(exc)[:500])


def register_files(paths: list[Path]) -> list[dict[str, Any]]:
    """Register files on disk (already saved) as pending documents, idempotent by source_path."""
    out: list[dict[str, Any]] = []
    by_source: dict[str, dict[str, Any]] = {d["source_path"]: d for d in db.list_documents()}
    for p in paths:
        modality = detect_modality_for_file(p)
        if modality is None:
            raise ValueError(
                f"Unsupported file type: {p.name} — supported: text, md, code, pdf, png/jpg, mp4/mov, mp3/wav"
            )
        if str(p) in by_source:
            out.append(by_source[str(p)])
            continue
        doc = db.insert_document(
            filename=p.name,
            mime_type=_mime_for(p, modality),
            modality=modality,
            size_bytes=p.stat().st_size,
            source_path=str(p),
            title=p.stem,
        )
        out.append(doc)
    return out


def detect_modality_for_file(p: Path) -> str | None:
    from app.config import detect_modality

    return detect_modality(p.name, None)


def _mime_for(p: Path, modality: str) -> str:
    import mimetypes

    m, _ = mimetypes.guess_type(p.name)
    return m or {
        "text": "text/plain",
        "pdf": "application/pdf",
        "image": "image/png",
        "video": "video/mp4",
        "audio": "audio/mpeg",
    }[modality]
