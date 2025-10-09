# Scripts Reference

Central reference for the executable Python scripts that ship with the Technical Service Assistant. Unless noted otherwise, scripts are idempotent / read-only aside from writing logs or inserting into Postgres.

## Conventions
- Run from repository root with active virtual environment.
- Many scripts share helpers centralized in `pdf_processor/utils.py`.
- Use `--help` where available to view arguments (add argparse in future if missing).

## Ingestion & Processing
| Script | Purpose | Notes |
|--------|---------|-------|
| `pdf_processor/process_pdfs.py` | Background poller ingesting PDFs | Container entrypoint; honors env config |
| `bin/extract_text.py` | Extract raw text to JSON | Single PDF path argument |
| `bin/extract_tables.py` | Extract tables to JSON | Requires Ghostscript / Camelot dependencies |
| `bin/extract_images.py` | Extract images to directory | Saves under provided output dir |
| `bin/create_chunks.py` | Chunk existing text file | Uses overlap strategy |
| `bin/load_embeddings_to_db.py` | Bulk insert prepared embeddings | Expects JSONL or structured input (improve doc later) |

## Retrieval / QA / Evaluation
| Script | Purpose | Notes |
|--------|---------|-------|
| `bin/ask_questions.py` | Perform semantic search + ask LLM | Uses embedding + optional rerank |
| `bin/analyze_embeddings.py` | Evaluate embedding model performance | Produces similarity metrics & HTML logs |
| `scripts/eval_suite.py` | Retrieval quality metrics | Recall@K, MRR, nDCG, timing metrics, optional rerank comparison |
| `bin/benchmark_all_embeddings.py` | Orchestrate multi-model tests | Leverages multiple Ollama ports |
| `bin/generate_questions.py` | Generate synthetic eval questions | Helps build benchmark sets |
| `bin/remote_embedding_test.py` | Test remote embedding endpoint (if configured) | Useful for external model services |
| `bin/local_embedding_test.py` | Sanity test local embedding server | Quick connectivity check |

## Monitoring / Utilities
| Script | Purpose | Notes |
|--------|---------|-------|
| `test_connectivity.py` | Check service reachability | Postgres, Ollama, etc. |
| `bin/monitor_uploads.py` | Log newly added PDFs (debug) | Redundant with poller; dev aid |
| `distribute_models.py` | Push models to multiple Ollama instances | For parallel readiness |
| `migrate_models.py` | Move / sync models between instances | Housekeeping |
| `scripts/verify_ingestion.py` | Validate DB state after run | Could evolve into test harness |

## Future Enhancements
Planned improvements:
- Standardize CLI args with `argparse` and `--json` output mode.
- Add `--dry-run` where modifications occur.
- Expand rerank comparison to include multiple model endpoints.

---
Update this document when adding or modifying scripts to keep onboarding friction low.
