"""Safe serving of uploaded media files from disk."""
from __future__ import annotations

import mimetypes
from pathlib import Path

from app.config import settings

# Mime types safe to render inline in the browser. Anything else is served as
# an attachment — never render uploaded SVG/HTML inline (stored XSS).
INLINE_SAFE = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "video/mp4",
    "video/quicktime",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "text/plain",
    "text/markdown",
    "text/csv",
}


def resolve_under_uploads(doc_source_path: str) -> Path | None:
    """Resolve a document's source_path, only allowing paths under UPLOAD_DIR.

    Returns None if the path escapes the uploads directory or doesn't exist.
    """
    uploads = settings.upload_dir.resolve()
    try:
        p = Path(doc_source_path).resolve()
        p.relative_to(uploads)
    except ValueError:
        return None
    if not p.is_file():
        return None
    return p


def media_response_headers(mime_type: str, filename: str) -> dict[str, str]:
    """Headers dict for serving a file: inline for whitelisted types, attachment else."""
    mime = (mimetypes.guess_type(filename)[0] or mime_type or "application/octet-stream").split(";")[0]
    disposition = "inline" if mime in INLINE_SAFE else "attachment"
    quoted = filename.replace('"', "")
    return {
        "Content-Disposition": f'{disposition}; filename="{quoted}"',
        "X-Content-Type-Options": "nosniff",
    }
