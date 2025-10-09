# Experiments Directory

This directory contains experimental, prototyping, benchmarking, and phase-based evolution scripts that are not part of the core runtime path. They document historical progression and can be used for:

- Reproducing benchmarking phases (Phase 2C, Phase 3A/3B, Phase 4A)
- Testing multimodal, OCR, and advanced retrieval enhancements
- Rapid iteration on chunking, embeddings, and monitoring integration
- Validating improvement hypotheses before promoting changes into production modules

## Structure

| Category | Examples |
|----------|----------|
| Phase Evolution | `phase2c_accuracy_system.py`, `phase3a_multimodal_system.py`, `phase4a_document_classification.py` |
| Multimodal / OCR | `phase3b_ocr_pipeline.py`, `multimodal_monitoring.py` |
| Embedding & Chunking | `advanced_semantic_chunking.py`, `cross_modal_embeddings.py` |
| Validation & Benchmarking | `validate_accuracy.py`, `validate_improvement_potential.py`, `rag_validation_framework.py` |
| Integrations | `enterprise_integration.py`, `integrate_multimodal_monitoring.py` |

## Promotion Policy
If an experimental script becomes stable and broadly useful, its logic should be migrated into:
- `pdf_processor/` for ingestion & extraction
- `utils/` for reusable utilities
- `reranker/` for API-related logic

## Deprecation Guidance
Scripts here may be deprecated over time. When deprecating:
1. Add a header comment: `# DEPRECATED - superseded by <new_path>`
2. Update this README deprecation section
3. Remove from documentation navigation if no longer relevant

## Current Deprecated Scripts
_None currently marked._

## Notes
Do not import these modules in production services directly to avoid unintended side effects.
