# Multimodal RAG — Gemini Embedding 2 + Supabase pgvector + Codex

Upload documents (text, code, PDF, images, video, audio), embed them with
Google's multimodal **`gemini-embedding-2`** model into **Supabase pgvector**,
then ask questions answered by an **OpenAI Codex** model over the retrieved
chunks — with citations.

## Setup

```bash
# 1. Install dependencies
uv sync

# 2. Configure keys
cp .env.example .env
#    -> fill in GEMINI_API_KEY, OPENAI_API_KEY, SUPABASE_SERVICE_ROLE_KEY
#       (Supabase Dashboard -> Settings -> API -> service_role key)

# 3. Run the app
uv run python main.py
#    (or: uv run uvicorn app.server.main:app --host 127.0.0.1 --port 8000)
#    then open http://127.0.0.1:8000
```

The Supabase schema (documents/chunks tables, HNSW index, `match_chunks` RPC)
is already applied to project `gnarrrwqzskmmpcuvomi` via MCP. To inspect it:
Dashboard → SQL Editor, or ask the Supabase MCP server to list migrations.

## Where to upload documents

- **GUI (recommended, ≤200 MB/file):** drag & drop onto the drop zone at
  `http://127.0.0.1:8000`. Files are saved to `data/uploads/` and embedding
  starts automatically.
- **CLI:** copy files into `data/uploads/` (any subfolder works), then:
  ```bash
  uv run python -m app.ingest data/uploads/           # everything there
  uv run python -m app.ingest path/to/one.pdf         # single file
  uv run python -m app.ingest --no-process some/dir   # register only
  ```
- **Over 200 MB:** place the file directly into `data/uploads/` (bypassing the
  browser upload), then click **Embed pending** in the GUI or run the CLI.

Supported types: text/code files (.txt .md .py .js .json .yaml …), **PDF**,
**PNG/JPEG**, **MP4/MOV** (≤120 s), **MP3/WAV** (≤180 s).

## How documents are processed and embedded

1. Each file is saved to `data/uploads/` and registered in Supabase as a
   `documents` row with `status=pending`.
2. The pipeline (a background thread in the server, or synchronous in the CLI)
   routes by modality:
   - **text/code** → paragraph-aware chunks (~1500 chars, 200 overlap) → each
     chunk embedded as `title: {title} | text: {chunk}` (the model's asymmetric
     retrieval-document format);
   - **PDF** → split into parts of ≤6 pages (shrunk further if the estimated
     token count would exceed the model's 8,192-token input limit) → each part's
     bytes embedded directly (the model reads the PDF visually) while the
     extracted text is stored for the reasoning model;
   - **image / video / audio** → whole file embedded as one vector with the
     filename as a plain caption (multimodal inputs must not carry task
     prefixes). Files >19 MB go through the Gemini Files API automatically.
3. Vectors land in the `chunks` table (`vector(1536)`, cosine HNSW index).
   Query-side, the question is embedded as `task: search result | query: {q}`
   and matched via the `match_chunks` RPC.
4. Statuses: `pending` → `processing` → `embedded`, or `failed` (hover the
   status in the GUI to see the error; click **Re-embed** to retry).
   Re-embedding is idempotent: old chunks are deleted first.

## How to run queries

- **GUI:** type a question, optionally filter by modality and top-k, click
  **Ask**. You get the Codex answer with `[n]` citations highlighted, plus the
  retrieved chunks with similarity scores, modality badges, and inline media
  previews (thumbnails, video/audio players).
- **CLI:**
  ```bash
  uv run python -m app.query "What does the report conclude?" --top-k 5
  uv run python -m app.query "cats" --modality image
  ```
- **HTTP API:**
  ```bash
  curl -s localhost:8000/api/query -H 'content-type: application/json' \
       -d '{"question": "what is in the images?", "top_k": 5}' | jq
  ```

## Architecture

```
upload ──▶ data/uploads/ ──▶ documents(pending) ──▶ pipeline (by modality)
                                                          │ gemini-embedding-2 (1536d)
                                                          ▼
       answer ◀── Codex (gpt-6.1-terra) ◀── context ◀── chunks + match_chunks RPC (HNSW cosine)
              ▲                                        ▲
              └── question ── embed as "task: search result | query: …"
```

## Limitations

- `gemini-embedding-2` input limits: 8,192 tokens (text), 6 images/request
  (PNG/JPEG), PDF ≤6 pages/part (1 strongly recommended — inputs past the
  token cap are silently truncated), video ≤120 s (MP4/MOV), audio ≤180 s
  (MP3/WAV). Over-length video/audio fail with a clear error message.
- The model has **no `task_type` parameter** — task intent is encoded in the
  prompt text (`task: search result | query: …` / `title: … | text: …`).
  Multimodal captions must not carry task prefixes.
- Intel-Mac quirk: this project pins `cryptography<46` because newer versions
  ship no macOS x86_64 wheels (rustc too old to build from source).
- The server binds to `127.0.0.1` only — it holds the Supabase service-role key.
- `.env` and `data/` are gitignored; never commit the service key.

## Tests

```bash
uv run pytest          # unit tests, no network, no keys needed
```

## Helper scripts

```bash
uv run python scripts/check_keys.py        # which API keys are configured
uv run python scripts/show_index.py         # current documents + chunk counts
uv run python scripts/verify_embedding.py   # embedding + Supabase round-trip
uv run python scripts/verify_retrieval.py   # retrieval relevance checks
uv run python scripts/make_sample_data.py   # generate sample text/PDF/PNG
uv run python scripts/make_media_sample.py  # generate sample video/audio (ffmpeg)
```

