"""Modality routing + media safety tests (no network)."""
from app.config import detect_modality, mime_for_modality
from app.media import media_response_headers


def test_mime_routing():
    assert detect_modality("a.pdf", "application/pdf") == "pdf"
    assert detect_modality("a.png", "image/png") == "image"
    assert detect_modality("a.jpg", "image/jpeg") == "image"
    assert detect_modality("a.mp4", "video/mp4") == "video"
    assert detect_modality("a.mov", "video/quicktime") == "video"
    assert detect_modality("a.mp3", "audio/mpeg") == "audio"
    assert detect_modality("a.wav", "audio/x-wav") == "audio"
    assert detect_modality("a.txt", "text/plain") == "text"
    assert detect_modality("a.md", "text/markdown") == "text"


def test_extension_fallback():
    # generic mime or none -> extension decides
    assert detect_modality("photo.png", "application/octet-stream") == "image"
    assert detect_modality("doc.pdf", None) == "pdf"
    assert detect_modality("notes.md", "application/octet-stream") == "text"
    assert detect_modality("main.py", "") == "text"
    assert detect_modality("clip.mp4", "binary/octet-stream") == "video"


def test_unsupported():
    assert detect_modality("file.xyz", "application/octet-stream") is None
    assert detect_modality("file.webp", "image/webp") is None  # webp unsupported by the model
    assert detect_modality("file.flac", "audio/x-flac") is None
    assert detect_modality("file.m4a", "audio/mp4") is None


def test_prefix_fallback():
    # No permissive mime-prefix fallback: model-unsupported formats are rejected
    # even when the mime looks plausible (image/*, video/*, audio/*).
    assert detect_modality("x.dat", "video/x-something") is None
    assert detect_modality("x.dat", "audio/whatever") is None


def test_inline_whitelist():
    h = media_response_headers("image/png", "cat.png")
    assert h["Content-Disposition"].startswith("inline")
    h2 = media_response_headers("image/svg+xml", "evil.svg")
    assert h2["Content-Disposition"].startswith("attachment")
    assert h2["X-Content-Type-Options"] == "nosniff"


def test_mime_for_modality():
    for m in ("text", "pdf", "image", "video", "audio"):
        assert mime_for_modality(m)
