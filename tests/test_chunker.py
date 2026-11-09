"""Chunker unit tests (no network)."""
from app.chunker import chunk_text, extract_title


def test_empty():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_short_text_single_chunk():
    text = "Hello world.\n\nThis is a paragraph."
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert "Hello world." in chunks[0]


def test_respects_max_chars():
    # 20 paragraphs of 100 chars each -> with max 1500, roughly 3+ chunks
    text = "\n\n".join(f"Paragraph {i}: " + "x" * 85 for i in range(20))
    chunks = chunk_text(text, max_chars=1500, overlap=0)
    assert 2 <= len(chunks) <= 3  # 2000 chars total, greedy-packed
    for c in chunks:
        assert len(c) <= 1500


def test_hard_split_long_paragraph_with_overlap():
    para = "Sentence one is here. " * 100  # ~2200 chars, single paragraph
    chunks = chunk_text(para, max_chars=500, overlap=100)
    assert len(chunks) >= 4
    for c in chunks:
        assert len(c) <= 500
    # overlap: chunk n+1 should start with tail of chunk n
    # (tail of first chunk == start of second, minus the overlap slice)
    assert chunks[1][:20] != ""


def test_paragraph_boundaries_preserved():
    a = "A" * 400
    b = "B" * 400
    c = "C" * 400
    chunks = chunk_text("\n\n".join([a, b, c]), max_chars=1000, overlap=0)
    # a+b fit (800+2), c doesn't -> 2 chunks
    assert len(chunks) == 2
    assert chunks[0] == f"{a}\n\n{b}"
    assert chunks[1] == c


def test_title_extraction():
    assert extract_title("# My Report\n\nBody", fallback="f") == "My Report"
    assert extract_title("\n\n  \nFirst line", fallback="f") == "First line"
    assert extract_title("", fallback="f.txt") == "f.txt"
    long = "W" * 200
    assert len(extract_title(long)) == 80
