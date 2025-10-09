# pdf_processor

This directory contains utilities and CLI wrappers used to extract content from PDFs, chunk text, generate embeddings, and insert data into the project's Postgres/PGVector database.

Overview
- `utils.py` — central shared functions used across the project:
  - extract_text(pdf_path)
  - extract_tables(pdf_path)
  - extract_images(pdf_path, output_dir)
  - chunk_text(text, document_name, start_index)
  - chunk_tables(...), chunk_images(...)
  - get_embedding(text, model, ollama_url)
  - get_db_connection(...)
  - insert_chunk_and_embedding(conn, chunk, embedding, model_name)
  - setup_logger(program_name, log_dir)

- CLI wrappers: `extract_text.py`, `extract_tables.py`, `extract_images.py` — thin wrappers that call into `utils.py` and print JSON output for integration with other scripts.

Why this refactor
- Previously, multiple scripts contained duplicated implementations for extraction, chunking, and DB logic. These were consolidated to reduce maintenance surface area and keep behavior consistent across different pipelines.

Environment variables and configuration
- `OLLAMA_URL` or pass `ollama_url` to `get_embedding` — default: `http://localhost:11434/api/embeddings`
- `EMBEDDING_MODEL` or pass `model` to `get_embedding` — default: `nomic-embed-text:v1.5`
- Database environment variables used by `get_db_connection`:
  - `DB_NAME` (default: `vector_db`)
  - `DB_USER` (default: `postgres`)
  - `DB_PASSWORD` (default: `postgres`)
  - `DB_HOST` (default: `localhost`)
  - `DB_PORT` (default: `5432`)
- `LOG_DIR` used by `setup_logger` (default: `/tmp` or project `logs/` if set by callers)

Quick examples
- Extract text from a PDF:
  ```bash
  python3 pdf_processor/extract_text.py /path/to/file.pdf
  ```
- Extract tables (JSON output):
  ```bash
  python3 pdf_processor/extract_tables.py /path/to/file.pdf
  ```
- Extract images to a directory:
  ```bash
  python3 pdf_processor/extract_images.py /path/to/file.pdf ./out_images
  ```

Integration
- The `bin/` scripts and `pdf_processor/process_pdfs.py` call into `utils.py`. If you change behavior (e.g., chunking strategy), update `utils.py` so all pipelines pick up the change.

Testing
- Add unit tests for `utils.py` functions in `pdf_processor/tests/` and use a disposable/local Postgres for DB-related integration tests.

Notes
- Camelot requires system dependencies (Ghostscript). Ensure the runtime environment (Docker image or host) includes these binaries.
- PyMuPDF (fitz) and camelot must be installed in the project's Python environment.
