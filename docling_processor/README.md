# docling_processor

Docling-based processor for multi-format document ingestion, chunking, and database integration. Provides structured extraction with Prometheus metrics for operational visibility.

## Overview
- Uses Docling for AI-powered extraction and chunking of PDF, DOCX, PPTX, XLSX, HTML, images, and audio files.
- Outputs structured chunks compatible with the existing `document_chunks` table in Postgres.
- Integrates with existing health/repair logic and metrics.
- Designed for Docker deployment (see Dockerfile and docker-compose.yml).

## Key Files
- `docling_processor.py`: Main processing & metrics emission loop (polling ingestion)
- `requirements.txt`: Includes `prometheus_client` for metrics endpoint
- `Dockerfile`: Builds minimal runtime (Debian slim + OCR libs + Python deps)

## Metrics Exposed (Port 9110)
```
docling_documents_processed_total      # Successfully processed documents
docling_documents_failed_total         # Failed documents
docling_chunks_created_total           # Total chunks written to DB
docling_last_success_timestamp         # Unix timestamp of last successful document
docling_processing_duration_seconds_*  # Per-document processing time histogram
docling_cycle_duration_seconds_*       # End-to-end polling cycle histogram
docling_active_files_in_cycle          # Number of file entries found this cycle
```

Prometheus scrape job (already configured in `monitoring/prometheus/prometheus.yml`):
```yaml
- job_name: 'docling-processor'
	static_configs:
		- targets: ['docling_processor:9110']
	scrape_interval: 30s
```

Alert suggestions (add to `alerts.yml` when alertmanager is enabled):
```yaml
- alert: DoclingStalled
	expr: time() - docling_last_success_timestamp > 900
	for: 5m
	labels:
		severity: warning
	annotations:
		summary: 'Docling ingestion stalled'
		description: 'No successful document processing > 15m'

- alert: DoclingHighFailureRate
	expr: (rate(docling_documents_failed_total[10m]) / (rate(docling_documents_processed_total[10m]) + 1)) > 0.2
	for: 10m
	labels:
		severity: warning
	annotations:
		summary: 'High Docling failure rate'
		description: 'Failure ratio exceeded 20% over last 10m'
```

## Processing Flow
1. Poll `uploads/` every `POLL_INTERVAL_SECONDS` (default 60s)
2. Convert documents with Docling (text, tables, pictures)
3. Build generalized chunks preserving basic metadata (label / inferred page index)
4. Insert document + chunks via shared PDF processor DB utilities
5. Update ingestion & per-document metrics
6. Archive source file to `archive/` (move or copy+remove fallback)

## Failure Handling
* Failed documents increment `docling_documents_failed_total` and move to archive
* Database connection errors logged and cycle skipped (metrics still record cycle duration)
* Non-fatal extraction issues (individual tables/pictures) logged at debug level

## Development Notes
* Ensure `prometheus_client` is installed (added 2025-10-08) – missing dependency causes port 9110 connection refusals
* Histogram buckets currently default; adjust if latency distribution stabilizes
* Directories inside `uploads/` are skipped; only files processed
* Export `DOCLING_DEVICE=cpu` (already set in `docker-compose.yml`) to force Docling's accelerator settings to stay on CPU even when CUDA is available

## Testing
```bash
# Inside repo
docker compose logs -f docling_processor
curl -s http://localhost:9110/metrics | grep docling_documents_processed_total
curl -s 'http://localhost:9091/api/v1/query?query=histogram_quantile(0.95,sum by (le) (rate(docling_processing_duration_seconds_bucket[15m])))'
```

## Usage
- Place documents in `uploads/` directory (PDF, DOCX, PPTX, XLSX, HTML, images, audio).
- Run the processor in Docker; it will ingest, chunk, and write to the database.

## Testing
- Compare results to legacy pipeline for accuracy and completeness.
- Validate multi-format support and health checks.
