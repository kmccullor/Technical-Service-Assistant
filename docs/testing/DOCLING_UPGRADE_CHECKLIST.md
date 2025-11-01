# Docling Upgrade Regression Checklist

Use this checklist whenever bumping the Docling dependency to a newer release. The goal is to reconfirm that OCR toggles, pipeline options, and ingestion metrics continue to function as expected.

1. **Update dependency pin**
   - Edit `docling_processor/requirements.txt` with the new `docling==<version>` pin.
   - Rebuild the `docling_processor` container: `docker compose up -d --build docling_processor`.

2. **Validate runtime compatibility**
   - Tail the processor logs for import or initialization warnings.
   - Confirm the startup log reports the detected Docling version and does not trigger the mismatch warning added in `docling_processor.py`.

3. **Run functional regression tests**
   - `make test`
   - `pytest tests/docling --maxfail=1 -v` (if additional docling-specific tests are added).
   - Manually ingest a representative sample (native PDF, scanned PDF requiring OCR, DOCX, PPTX) and confirm chunk counts.

4. **Review metrics and dashboards**
   - `curl -s http://localhost:9110/metrics | grep docling_`
   - Check Grafana panel “Docling Processor Health” for steady ingestion timestamps and failure counts.

5. **Document findings**
   - Update `CHANGELOG.md` with the new Docling version and any migration notes.
   - Record anomalies or required code changes so future upgrades benefit from the context.

Rollback if any regression is observed and open an issue with the failure details.
