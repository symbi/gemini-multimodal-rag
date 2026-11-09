"""Entry point for `uv run python main.py` — starts the RAG web server.

Equivalent to: uv run uvicorn app.server.main:app --host 127.0.0.1 --port 8000
"""
import uvicorn


def main() -> None:
    uvicorn.run("app.server.main:app", host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
