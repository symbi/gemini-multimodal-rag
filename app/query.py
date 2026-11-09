"""CLI: ask a question against the RAG index.

Usage:
    uv run python -m app.query "what did the report conclude?" [--top-k 5] [--modality text]
"""
from __future__ import annotations

import argparse
import logging
import sys

from app import db, retrieval
from app.openai_client import answer_question


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Query the multimodal RAG index")
    parser.add_argument("question", help="Natural-language question")
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--modality", choices=["text", "pdf", "image", "video", "audio"], default=None)
    args = parser.parse_args(argv)

    chunks = retrieval.search(args.question, top_k=args.top_k, modality=args.modality)
    if not chunks:
        print("No documents indexed yet. Run: uv run python -m app.ingest <path>")
        return 1

    print(f"Top {len(chunks)} retrieved chunk(s):")
    for i, ch in enumerate(chunks, 1):
        sim = ch.get("similarity")
        sim_s = f"{sim:.3f}" if isinstance(sim, (int, float)) else "?"
        preview = (ch.get("content_text") or "")[:100].replace("\n", " ")
        print(f"  [{i}] {ch['filename']} ({ch['modality']}, sim={sim_s}): {preview}…")
    print()

    context = retrieval.build_context_block(chunks)
    answer, cited = answer_question(args.question, context, len(chunks))
    print("ANSWER\n======")
    print(answer)
    if cited:
        print("\nCited chunks:", ", ".join(f"[{n}]" for n in cited))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    sys.exit(main())
