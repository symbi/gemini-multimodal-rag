"""CLI: ingest files/directories into the RAG index.

Usage:
    uv run python -m app.ingest <path> [more paths...]
    uv run python -m app.ingest data/uploads            # (re)register everything there
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from app import db
from app.pipeline.ingest import process_document, register_files

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest files into the multimodal RAG index")
    parser.add_argument("paths", nargs="+", help="Files or directories (walked recursively)")
    parser.add_argument("--no-process", action="store_true", help="Only register, don't embed yet")
    args = parser.parse_args(argv)

    files: list[Path] = []
    for p in map(Path, args.paths):
        if p.is_dir():
            files.extend(sorted(q for q in p.rglob("*") if q.is_file()))
        else:
            files.append(p)

    if not files:
        print("No files found.", file=sys.stderr)
        return 1

    try:
        docs = register_files(files)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    pending = [d for d in docs if d["status"] in ("pending", "failed")]
    print(f"{len(docs)} document(s) registered ({len(pending)} to embed).")
    if args.no_process:
        return 0

    failures = 0
    for d in docs:
        if d["status"] in ("pending", "failed"):
            print(f"Embedding {d['filename']} ({d['modality']})...", flush=True)
            process_document(d["id"])
            # process_document updates status synchronously; fetch to report
            final = db.get_document(d["id"])
            if final and final["status"] == "embedded":
                print(f"  OK: {d['filename']}")
            else:
                failures += 1
                msg = (final or {}).get("error", "unknown error")
                print(f"  FAILED: {d['filename']}: {msg}", file=sys.stderr)
    if failures:
        print(f"{failures} document(s) failed.", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    sys.exit(main())
