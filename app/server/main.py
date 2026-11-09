"""FastAPI server: upload, documents, query + static GUI. Binds 127.0.0.1 only."""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app import db, retrieval
from app.config import detect_modality, settings
from app.media import media_response_headers, resolve_under_uploads
from app.openai_client import answer_question
from app.pipeline.ingest import process_document, register_files

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Multimodal RAG — Gemini Embedding 2", version="0.1.0")

# Ingest runs in Starlette's threadpool (sync `def` endpoint tasks); cap
# concurrent Gemini API work.
_ingest_semaphore = threading.Semaphore(2)

_STATIC = Path(__file__).parent / "static"


@app.on_event("startup")
def _startup() -> None:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    try:
        n = db.reset_stale_processing()
        if n:
            logger.info("Reset %d stale 'processing' document(s) to pending", n)
    except Exception:  # noqa: BLE001 - DB may be unreachable; GUI still serves
        logger.warning("Could not reset stale documents on startup", exc_info=True)


def _guarded_process(doc_id: str) -> None:
    with _ingest_semaphore:
        process_document(doc_id)


# --- models ------------------------------------------------------------------

class QueryRequest(BaseModel):
    question: str
    top_k: int | None = None
    modality: str | None = None


# --- endpoints ---------------------------------------------------------------

@app.post("/api/upload")
def upload(background: BackgroundTasks, files: list[UploadFile] = File(...)) -> dict:
    saved: list[dict] = []
    for f in files:
        modality = detect_modality(f.filename or "", f.content_type)
        if modality is None:
            raise HTTPException(
                415,
                f"Unsupported file type: {f.filename} ({f.content_type}). "
                "Supported: text/code files, PDF, PNG/JPEG, MP4/MOV, MP3/WAV.",
            )
        if f.size and f.size > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(413, f"{f.filename} exceeds {settings.max_upload_mb}MB")

        dest_dir = settings.upload_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = _unique_path(dest_dir / (f.filename or "upload.bin"))
        with dest.open("wb") as out:
            while chunk := f.file.read(1024 * 1024):
                out.write(chunk)

        doc = db.insert_document(
            filename=dest.name,
            mime_type=(f.content_type or "").split(";")[0] or _fallback_mime(modality),
            modality=modality,
            size_bytes=dest.stat().st_size,
            source_path=str(dest),
            title=dest.stem,
        )
        saved.append(doc)
        background.add_task(_guarded_process, doc["id"])
    return {"documents": saved}


def _fallback_mime(modality: str) -> str:
    return {"text": "text/plain", "pdf": "application/pdf", "image": "image/png",
            "video": "video/mp4", "audio": "audio/mpeg"}[modality]


def _unique_path(p: Path) -> Path:
    if not p.exists():
        return p
    stem, suffix = p.stem, p.suffix
    for i in range(1, 1000):
        cand = p.with_name(f"{stem}-{i}{suffix}")
        if not cand.exists():
            return cand
    raise HTTPException(409, f"Too many duplicate files named {p.name}")


@app.get("/api/documents")
def documents() -> dict:
    return {"documents": db.list_documents()}


@app.get("/api/info")
def info() -> dict:
    """Model/config info for the GUI footer."""
    return {
        "embedding_model": "gemini-embedding-2",
        "embed_dim": settings.embed_dim,
        "codex_model": settings.codex_model,
        "top_k": settings.top_k,
    }


@app.post("/api/reembed/{doc_id}")
def reembed(doc_id: str, background: BackgroundTasks) -> dict:
    doc = db.get_document(doc_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    db.update_document(doc_id, status="pending", error=None)
    background.add_task(_guarded_process, doc_id)
    return {"ok": True, "id": doc_id}


@app.delete("/api/documents/{doc_id}")
def delete_doc(doc_id: str) -> dict:
    doc = db.get_document(doc_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    db.delete_document(doc_id)  # chunks cascade
    try:
        p = Path(doc["source_path"])
        if resolve_under_uploads(doc["source_path"]):
            p.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not delete local file for %s", doc_id)
    return {"ok": True}


@app.post("/api/query")
def query(req: QueryRequest) -> dict:
    if not req.question.strip():
        raise HTTPException(422, "question must not be empty")
    try:
        chunks = retrieval.search(req.question, top_k=req.top_k, modality=req.modality)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Retrieval failed")
        raise HTTPException(502, f"Retrieval failed: {exc}") from exc
    if not chunks:
        return {"answer": "No documents found in the index. Upload some first.",
                "citations": [], "chunks": []}
    context = retrieval.build_context_block(chunks)
    try:
        answer, cited = answer_question(req.question, context, len(chunks))
    except Exception as exc:  # noqa: BLE001
        # Retrieval succeeded — return the chunks anyway so the GUI stays useful.
        logger.warning("Codex answer failed: %s", exc)
        return {
            "answer": f"**Reasoning model unavailable:** {exc}\n\n"
                      f"Retrieved {len(chunks)} chunk(s) below — the sources are still shown.",
            "citations": [],
            "chunks": chunks,
            "degraded": True,
        }
    return {
        "answer": answer,
        "citations": cited,
        "chunks": chunks,
    }


@app.get("/api/media/{doc_id}")
def media(doc_id: str) -> FileResponse:
    doc = db.get_document(doc_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    p = resolve_under_uploads(doc["source_path"])
    if p is None:
        raise HTTPException(404, "File missing on disk")
    return FileResponse(p, headers=media_response_headers(doc["mime_type"], p.name))


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC / "index.html")


@app.get("/app.js")
def app_js() -> FileResponse:
    return FileResponse(_STATIC / "app.js", media_type="application/javascript")


@app.get("/style.css")
def style_css() -> FileResponse:
    return FileResponse(_STATIC / "style.css", media_type="text/css")


@app.get("/favicon.svg")
def favicon() -> FileResponse:
    return FileResponse(_STATIC / "favicon.svg", media_type="image/svg+xml")


@app.exception_handler(Exception)
async def unhandled(_req, exc):  # noqa: ANN001
    return JSONResponse(status_code=500, content={"detail": str(exc)})
