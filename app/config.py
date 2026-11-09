"""Application settings loaded from .env with validation."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REQUIRED_DIM = 1536  # must match the Supabase migration (extensions.vector(1536))


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    openai_api_key: str
    codex_model: str
    supabase_url: str
    supabase_service_role_key: str
    embed_dim: int
    embed_batch_size: int
    pdf_part_pages: int
    max_video_seconds: int
    max_audio_seconds: int
    top_k: int
    upload_dir: Path
    max_upload_mb: int


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


def load_settings() -> Settings:
    embed_dim = _int_env("EMBED_DIM", REQUIRED_DIM)
    if embed_dim != REQUIRED_DIM:
        raise RuntimeError(
            f"EMBED_DIM={embed_dim} but the Supabase schema uses vector({REQUIRED_DIM}). "
            "Changing dimensions requires a new migration and re-embedding everything. "
            "Keep EMBED_DIM=1536."
        )
    return Settings(
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        codex_model=os.environ.get("CODEX_MODEL", "gpt-6.1-terra"),
        supabase_url=os.environ.get("SUPABASE_URL", "https://gnarrrwqzskmmpcuvomi.supabase.co").rstrip("/"),
        supabase_service_role_key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""),
        embed_dim=embed_dim,
        embed_batch_size=_int_env("EMBED_BATCH_SIZE", 16),
        pdf_part_pages=_int_env("PDF_PART_PAGES", 6),
        max_video_seconds=_int_env("MAX_VIDEO_SECONDS", 120),
        max_audio_seconds=_int_env("MAX_AUDIO_SECONDS", 180),
        top_k=_int_env("TOP_K", 5),
        upload_dir=Path(os.environ.get("UPLOAD_DIR", "./data/uploads")).resolve(),
        max_upload_mb=_int_env("MAX_UPLOAD_MB", 200),
    )


settings = load_settings()

# ---------------------------------------------------------------------------
# Modality routing

# mime type -> modality. Extensions cover cases where a browser sends a
# generic mime type or none at all.
MIME_TO_MODALITY: dict[str, str] = {
    "text/plain": "text",
    "text/markdown": "text",
    "text/html": "text",
    "text/csv": "text",
    "text/x-python": "text",
    "text/x-shellscript": "text",
    "application/json": "text",
    "application/xml": "text",
    "application/x-yaml": "text",
    "application/pdf": "pdf",
    "image/png": "image",
    "image/jpeg": "image",
    "video/mp4": "video",
    "video/quicktime": "video",
    "audio/mpeg": "audio",
    "audio/mp3": "audio",
    "audio/wav": "audio",
    "audio/x-wav": "audio",
}

# extension -> modality (fallback when mime is unknown/generic)
EXT_TO_MODALITY: dict[str, str] = {
    ".txt": "text", ".md": "text", ".markdown": "text", ".rst": "text",
    ".csv": "text", ".tsv": "text", ".log": "text", ".json": "text",
    ".yaml": "text", ".yml": "text", ".xml": "text", ".html": "text", ".htm": "text",
    ".py": "text", ".js": "text", ".ts": "text", ".tsx": "text", ".jsx": "text",
    ".go": "text", ".rs": "text", ".java": "text", ".c": "text", ".h": "text",
    ".cpp": "text", ".hpp": "text", ".sh": "text", ".rb": "text", ".php": "text",
    ".sql": "text", ".css": "text", ".toml": "text", ".ini": "text", ".cfg": "text",
    ".pdf": "pdf",
    ".png": "image", ".jpg": "image", ".jpeg": "image",
    ".mp4": "video", ".mov": "video",
    ".mp3": "audio", ".wav": "audio",
}


def detect_modality(filename: str, mime_type: str | None) -> str | None:
    """Map a file to a modality via mime type first, then extension."""
    mime = (mime_type or "").split(";")[0].strip().lower()
    if mime in MIME_TO_MODALITY:
        return MIME_TO_MODALITY[mime]
    # application/octet-stream and friends: fall through to extension
    ext = Path(filename).suffix.lower()
    if ext in EXT_TO_MODALITY:
        return EXT_TO_MODALITY[ext]
    return None


def mime_for_modality(modality: str) -> str:
    """A reasonable inline-servable mime type per modality (for serving files)."""
    return {
        "text": "text/plain; charset=utf-8",
        "pdf": "application/pdf",
        "image": "image/jpeg",
        "video": "video/mp4",
        "audio": "audio/mpeg",
    }.get(modality, "application/octet-stream")
