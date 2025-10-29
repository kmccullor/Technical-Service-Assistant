"""Public facade for Phase 4A document classification utilities.

The full reference implementation lives under
`experiments/phase4a_document_classification.py`.  Tests and runtime
modules import this shim so we avoid duplicating logic while keeping the
original file in the experiments namespace.
"""

from experiments.phase4a_document_classification import (  # noqa: F401
    ClassifiedDocument,
    ClassificationPersistenceManager,
    ConfidenceCalibrator,
    DocumentFeatureExtractor,
    DocumentType,
    DocumentTypeClassifier,
    IntelligentDocumentClassifier,
    PriorityScorer,
    QualityAssessor,
    TechnicalDomain,
    monitor_performance_async,
    _quick_test,
)

__all__ = [
    "ClassifiedDocument",
    "ClassificationPersistenceManager",
    "ConfidenceCalibrator",
    "DocumentFeatureExtractor",
    "DocumentType",
    "DocumentTypeClassifier",
    "IntelligentDocumentClassifier",
    "PriorityScorer",
    "QualityAssessor",
    "TechnicalDomain",
    "monitor_performance_async",
    "_quick_test",
]
