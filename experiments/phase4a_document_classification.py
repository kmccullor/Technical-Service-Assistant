"""Phase 4A Task 3: Intelligent Document Classification

Implements an intelligent document classification pipeline including:
- Document type prediction
- Technical domain prediction
- Priority scoring (for processing order)
- Quality assessment
- Confidence calibration

This module is intentionally lightweight (mock/statistical) while providing
clear extension points for future integration with real ML models trained
via the Phase 4A infrastructure.
"""

import asyncio
import functools
import json
import math
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from utils.logging_config import get_logger
from utils.monitoring import monitor_performance  # Reused for sync fallbacks

logger = get_logger(__name__)


class DocumentType(Enum):
    MANUAL = "manual"
    SPECIFICATION = "specification"
    SCHEMATIC = "schematic"
    REPORT = "report"
    DRAWING = "drawing"
    PROCEDURE = "procedure"
    UNKNOWN = "unknown"


class TechnicalDomain(Enum):
    ELECTRICAL = "electrical"
    NETWORK = "network"
    MECHANICAL = "mechanical"
    SOFTWARE = "software"
    CHEMICAL = "chemical"
    GENERAL = "general"


@dataclass
class ClassifiedDocument:
    document_id: str
    title: str
    content: str
    predicted_type: DocumentType
    predicted_domain: TechnicalDomain
    priority_score: float
    quality_score: float
    confidence: float
    type_probabilities: Dict[str, float] = field(default_factory=dict)
    domain_probabilities: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DocumentFeatureExtractor:
    """Extracts features from documents for classification."""

    TECHNICAL_PATTERN_MAP = {
        "electrical": [r"ohm", r"resistor", r"capacitor", r"voltage", r"current", r"circuit", r"amplifier"],
        "network": [r"router", r"switch", r"tcp/ip", r"protocol", r"firewall", r"vlan", r"latency"],
        "mechanical": [r"bearing", r"shaft", r"gear", r"torque", r"load", r"tolerance"],
        "software": [r"api", r"database", r"microservice", r"endpoint", r"json", r"deployment"],
        "chemical": [r"ph", r"compound", r"reaction", r"solvent", r"catalyst", r"concentration"],
    }

    TYPE_INDICATORS = {
        "manual": ["guide", "instructions", "overview", "introduction"],
        "specification": ["specification", "spec", "requirements", "parameters", "compliance"],
        "schematic": ["schematic", "diagram", "wiring", "layout"],
        "report": ["analysis", "results", "observations", "summary"],
        "drawing": ["drawing", "figure", "scale", "dimension"],
        "procedure": ["step", "procedure", "process", "sequence"],
    }

    @staticmethod
    def basic_text_features(text: str) -> Dict[str, float]:
        words = text.split()
        length = len(words)
        avg_word_len = sum(len(w) for w in words) / length if length else 0
        digit_ratio = sum(c.isdigit() for c in text) / max(1, len(text))
        uppercase_ratio = sum(c.isupper() for c in text if c.isalpha()) / max(1, sum(c.isalpha() for c in text))
        bullet_points = len(re.findall(r"\n[-*] ", text))
        section_count = len(re.findall(r"\n[A-Z][A-Za-z0-9_ ]+:", text))

        return {
            "length": length,
            "avg_word_len": avg_word_len,
            "digit_ratio": digit_ratio,
            "uppercase_ratio": uppercase_ratio,
            "bullet_points": bullet_points,
            "section_count": section_count,
        }

    @classmethod
    def domain_scores(cls, text: str) -> Dict[str, float]:
        scores = {}
        lower = text.lower()
        for domain, patterns in cls.TECHNICAL_PATTERN_MAP.items():
            count = sum(len(re.findall(p, lower)) for p in patterns)
            scores[domain] = count
        total = sum(scores.values()) or 1
        return {d: v / total for d, v in scores.items()}

    @classmethod
    def type_scores(cls, text: str) -> Dict[str, float]:
        scores = {}
        lower = text.lower()
        for t, indicators in cls.TYPE_INDICATORS.items():
            count = sum(lower.count(ind) for ind in indicators)
            scores[t] = count
        total = sum(scores.values()) or 1
        return {t: v / total for t, v in scores.items()}

    @classmethod
    def extract_all(cls, title: str, content: str) -> Dict[str, Any]:
        features = cls.basic_text_features(content)
        features.update({f"domain_{k}": v for k, v in cls.domain_scores(content).items()})
        features.update({f"type_{k}": v for k, v in cls.type_scores(title + " " + content).items()})
        features["title_length"] = len(title.split())
        return features


class ConfidenceCalibrator:
    """Calibrates confidence scores using temperature scaling and reliability adjustment."""

    def __init__(self, temperature: float = 1.2):
        self.temperature = temperature

    def calibrate(self, probs: Dict[str, float], quality_score: float, sample_size: int) -> float:
        # Temperature scaling
        adjusted = {k: v ** (1 / self.temperature) for k, v in probs.items()}
        total = sum(adjusted.values())
        norm = {k: v / total for k, v in adjusted.items()}
        # Use max probability
        max_p = max(norm.values())
        # Confidence boosted by quality and sample richness
        richness = min(1.0, math.log1p(sample_size) / 5)
        return round(min(1.0, 0.5 * max_p + 0.3 * quality_score + 0.2 * richness), 4)


class PriorityScorer:
    """Scores documents for processing priority based on type, detected complexity, and domain relevance."""

    TYPE_WEIGHTS = {
        DocumentType.SPECIFICATION: 1.0,
        DocumentType.SCHEMATIC: 0.95,
        DocumentType.PROCEDURE: 0.9,
        DocumentType.MANUAL: 0.85,
        DocumentType.REPORT: 0.75,
        DocumentType.DRAWING: 0.7,
        DocumentType.UNKNOWN: 0.5,
    }

    def score(self, doc_type: DocumentType, features: Dict[str, Any]) -> float:
        base = self.TYPE_WEIGHTS.get(doc_type, 0.6)
        complexity = min(1.0, (features.get("section_count", 0) + features.get("bullet_points", 0) / 2) / 20)
        technical_density = sum(v for k, v in features.items() if k.startswith("domain_")) / 6
        length_factor = min(1.0, math.log1p(features.get("length", 1)) / 8)
        return round(min(1.0, 0.4 * base + 0.25 * complexity + 0.2 * technical_density + 0.15 * length_factor), 4)


class QualityAssessor:
    """Assesses document quality based on structural and linguistic indicators."""

    def assess(self, features: Dict[str, Any]) -> float:
        structure = min(1.0, (features.get("section_count", 0) + features.get("bullet_points", 0) / 2) / 25)
        length = min(1.0, math.log1p(features.get("length", 1)) / 8)
        formatting = 1.0 - abs(features.get("uppercase_ratio", 0) - 0.1)  # Penalize shouting
        numeric_richness = min(1.0, features.get("digit_ratio", 0) * 5)
        return round(min(1.0, 0.35 * structure + 0.3 * length + 0.2 * formatting + 0.15 * numeric_richness), 4)


class DocumentTypeClassifier:
    """Simple probabilistic classifier using feature patterns (mock for demonstration)."""

    def predict_proba(self, title: str, content: str) -> Dict[str, float]:
        type_scores = DocumentFeatureExtractor.type_scores(title + " " + content)
        # Slight smoothing
        smoothed = {k: v + 0.05 for k, v in type_scores.items()}
        total = sum(smoothed.values())
        return {k: v / total for k, v in smoothed.items()}


class DomainClassifier:
    def predict_proba(self, content: str) -> Dict[str, float]:
        domain_scores = DocumentFeatureExtractor.domain_scores(content)
        smoothed = {k: v + 0.05 for k, v in domain_scores.items()}
        total = sum(smoothed.values())
        return {k: v / total for k, v in smoothed.items()}


def monitor_performance_async(operation_type: str = "unknown"):
    """Async-aware performance monitoring decorator.

    Falls back to the existing sync monitor for non-async functions.
    Keeps implementation local to avoid modifying global monitoring util.
    """

    def decorator(func):
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start
                    logger.info(f"{func.__name__} ({operation_type}) completed in {duration:.3f}s")
                    return result
                except Exception as e:  # noqa: BLE001
                    duration = time.time() - start
                    logger.error(f"{func.__name__} ({operation_type}) failed after {duration:.3f}s: {e}")
                    raise

            return async_wrapper
        else:
            return monitor_performance(operation_type)(func)

    return decorator


class IntelligentDocumentClassifier:
    """End-to-end intelligent document classification pipeline."""

    def __init__(self):
        self.type_classifier = DocumentTypeClassifier()
        self.domain_classifier = DomainClassifier()
        self.priority_scorer = PriorityScorer()
        self.quality_assessor = QualityAssessor()
        self.confidence_calibrator = ConfidenceCalibrator()
        logger.info("IntelligentDocumentClassifier initialized")

    @monitor_performance_async("document_classification")
    async def classify_document(self, document_id: str, title: str, content: str) -> ClassifiedDocument:
        features = DocumentFeatureExtractor.extract_all(title, content)
        type_probs = self.type_classifier.predict_proba(title, content)
        domain_probs = self.domain_classifier.predict_proba(content)

        predicted_type = max(type_probs.items(), key=lambda x: x[1])[0]
        predicted_domain = max(domain_probs.items(), key=lambda x: x[1])[0]

        doc_type_enum = (
            DocumentType(predicted_type) if predicted_type in DocumentType._value2member_map_ else DocumentType.UNKNOWN
        )
        domain_enum = (
            TechnicalDomain(predicted_domain)
            if predicted_domain in TechnicalDomain._value2member_map_
            else TechnicalDomain.GENERAL
        )

        quality_score = self.quality_assessor.assess(features)
        priority_score = self.priority_scorer.score(doc_type_enum, features)
        confidence = self.confidence_calibrator.calibrate(type_probs, quality_score, features.get("length", 0))

        return ClassifiedDocument(
            document_id=document_id,
            title=title,
            content=content[:5000],  # truncate for storage
            predicted_type=doc_type_enum,
            predicted_domain=domain_enum,
            priority_score=priority_score,
            quality_score=quality_score,
            confidence=confidence,
            type_probabilities=type_probs,
            domain_probabilities=domain_probs,
            metadata={
                "length": features.get("length"),
                "section_count": features.get("section_count"),
            },
        )

    async def batch_classify(self, docs: List[Tuple[str, str, str]]) -> List[ClassifiedDocument]:
        return [await self.classify_document(doc_id, title, content) for doc_id, title, content in docs]

    def aggregate_statistics(self, classified: List[ClassifiedDocument]) -> Dict[str, Any]:
        if not classified:
            return {}
        type_counts: Dict[str, int] = {}
        domain_counts: Dict[str, int] = {}
        avg_priority = np.mean([d.priority_score for d in classified])
        avg_quality = np.mean([d.quality_score for d in classified])
        avg_confidence = np.mean([d.confidence for d in classified])
        for d in classified:
            type_counts[d.predicted_type.value] = type_counts.get(d.predicted_type.value, 0) + 1
            domain_counts[d.predicted_domain.value] = domain_counts.get(d.predicted_domain.value, 0) + 1
        return {
            "total": len(classified),
            "type_distribution": type_counts,
            "domain_distribution": domain_counts,
            "avg_priority": round(float(avg_priority), 4),
            "avg_quality": round(float(avg_quality), 4),
            "avg_confidence": round(float(avg_confidence), 4),
        }


class ClassificationPersistenceManager:
    """Handles persistence of classification results in JSONL and Parquet formats.

    Design goals:
    - Append-friendly JSONL for streaming ingestion use-cases
    - Batch conversion to Parquet for analytics
    - Idempotent load utilities and simple integrity checks
    """

    def __init__(self, base_path: str = "data/classification"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.base_path / "classified_documents.jsonl"
        self.parquet_path = self.base_path / "classified_documents.parquet"
        logger.info(f"ClassificationPersistenceManager initialized at {self.base_path}")

    def save_jsonl(self, docs: List[ClassifiedDocument], append: bool = True) -> Path:
        mode = "a" if append and self.jsonl_path.exists() else "w"
        with open(self.jsonl_path, mode, encoding="utf-8") as f:
            for d in docs:
                record = {
                    "document_id": d.document_id,
                    "title": d.title,
                    "predicted_type": d.predicted_type.value,
                    "predicted_domain": d.predicted_domain.value,
                    "priority_score": d.priority_score,
                    "quality_score": d.quality_score,
                    "confidence": d.confidence,
                    "type_probabilities": d.type_probabilities,
                    "domain_probabilities": d.domain_probabilities,
                    "metadata": d.metadata,
                }
                f.write(json.dumps(record) + "\n")
        logger.info(f"Saved {len(docs)} classification records to {self.jsonl_path}")
        return self.jsonl_path

    def load_jsonl(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if not self.jsonl_path.exists():
            return []
        records: List[Dict[str, Any]] = []
        with open(self.jsonl_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if line.strip():
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError as e:  # noqa: PERF203
                        logger.warning(f"Skipping malformed line {i}: {e}")
                if limit and len(records) >= limit:
                    break
        return records

    def to_parquet(self) -> Path:
        records = self.load_jsonl()
        if not records:
            raise ValueError("No records to convert to Parquet")
        df = pd.DataFrame(records)
        # Normalize nested probability dicts for analytics columns
        prob_type_df = pd.json_normalize(df["type_probabilities"].tolist()).add_prefix("typeprob_")
        prob_domain_df = pd.json_normalize(df["domain_probabilities"].tolist()).add_prefix("domainprob_")
        meta_df = pd.json_normalize(df["metadata"].tolist()).add_prefix("meta_")
        analytic_df = pd.concat(
            [
                df.drop(columns=["type_probabilities", "domain_probabilities", "metadata"]),
                prob_type_df,
                prob_domain_df,
                meta_df,
            ],
            axis=1,
        )
        analytic_df.to_parquet(self.parquet_path, index=False)
        logger.info(f"Converted {len(analytic_df)} records to Parquet at {self.parquet_path}")
        return self.parquet_path

    def load_parquet(self) -> Optional[pd.DataFrame]:
        if not self.parquet_path.exists():
            return None
        return pd.read_parquet(self.parquet_path)

    def roundtrip_validate(self, sample: int = 5) -> bool:
        """Basic integrity check: save -> parquet -> load row count and key fields."""
        try:
            records = self.load_jsonl(limit=sample)
            if not records:
                logger.warning("No records available for roundtrip validation")
                return False
            self.to_parquet()
            pdf = self.load_parquet()
            if pdf is None or pdf.empty:
                return False
            # Check presence of essential columns
            required = {"document_id", "predicted_type", "predicted_domain", "priority_score"}
            missing = required - set(pdf.columns)
            if missing:
                logger.error(f"Roundtrip validation failed. Missing columns: {missing}")
                return False
            return True
        except Exception as e:  # noqa: BLE001
            logger.error(f"Roundtrip validation error: {e}")
            return False


# Simple test harness (async) for quick validation
async def _quick_test():  # pragma: no cover - demo harness
    classifier = IntelligentDocumentClassifier()
    sample_docs = [
        (
            "doc1",
            "Network Infrastructure Guide",
            "This manual provides router and switch configuration steps with VLAN and security hardening.",
        ),
        (
            "doc2",
            "Operational Amplifier Design Spec",
            "Specification of op-amp circuit parameters including voltage gain, bandwidth, and slew rate with tolerance values.",
        ),
        (
            "doc3",
            "Maintenance Procedure",
            "Step 1: Disconnect power. Step 2: Inspect capacitor and resistor array. Step 3: Document measurements.",
        ),
    ]
    results = await classifier.batch_classify(sample_docs)
    stats = classifier.aggregate_statistics(results)
    return results, stats


if __name__ == "__main__":  # pragma: no cover - manual demo execution
    res, st = asyncio.run(_quick_test())  # pragma: no cover
    for r in res:  # pragma: no cover
        logger.info(
            f"{r.document_id}: type={r.predicted_type.value} domain={r.predicted_domain.value} priority={r.priority_score} quality={r.quality_score} conf={r.confidence}"
        )  # pragma: no cover
    logger.info("Stats:", st)  # pragma: no cover
