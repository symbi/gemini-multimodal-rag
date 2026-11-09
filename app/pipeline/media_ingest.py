"""Image/video/audio ingestion: one embedding per file, with duration guards."""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from app import db, gemini_client
from app.config import settings

logger = logging.getLogger(__name__)


def _duration_seconds(path: Path) -> float | None:
    """Best-effort duration detection via ffprobe if available."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        return float(out.stdout.strip())
    except Exception:  # noqa: BLE001
        return None


def ingest_media(doc: dict, path: Path) -> int:
    modality = doc["modality"]
    mime = doc["mime_type"]

    dur: float | None = None
    if modality in ("video", "audio"):
        dur = _duration_seconds(path)
        limit = settings.max_video_seconds if modality == "video" else settings.max_audio_seconds
        if dur is not None and dur > limit + 1:
            raise ValueError(
                f"{modality} is {dur:.0f}s; gemini-embedding-2 supports at most "
                f"{limit}s (file: {path.name})"
            )

    # Caption: plain filename only (no task prefixes for multimodal inputs)
    emb = gemini_client.embed_file_part(path, mime, caption=path.name)
    row = {
        "document_id": doc["id"],
        "chunk_index": 0,
        "modality": modality,
        "title": path.stem,
        "content_text": f"[{modality}: {path.name}]",
        "embedding": emb,
        "source_path": str(path),
        "metadata": {"duration_seconds": dur} if dur else {},
    }
    db.insert_chunks([row])
    return 1
