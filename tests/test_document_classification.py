import asyncio
import os
from pathlib import Path

import pandas as pd

from phase4a_document_classification import (
    DocumentFeatureExtractor,
    IntelligentDocumentClassifier,
    ClassificationPersistenceManager,
)


def test_feature_extractor_basic():
    text = "Voltage and current measurements with resistor and capacitor in circuit diagram"
    features = DocumentFeatureExtractor.extract_all("Circuit Spec", text)
    assert features["length"] > 5
    # Domain feature presence
    assert any(k.startswith("domain_") for k in features.keys())
    # Type feature presence
    assert any(k.startswith("type_") for k in features.keys())


def test_async_single_classification():
    async def run():
        clf = IntelligentDocumentClassifier()
        result = await clf.classify_document(
            "docX", "Router Configuration Manual", "This guide covers router switch vlan configuration and latency optimization"
        )
        assert result.predicted_domain.value in {"network", "electrical", "mechanical", "software", "chemical", "general"}
        assert 0 <= result.priority_score <= 1
        assert 0 <= result.quality_score <= 1
        assert 0 <= result.confidence <= 1
        assert sum(result.type_probabilities.values()) == pytest.approx(1.0, rel=1e-3)
        return result

    import pytest

    res = asyncio.run(run())
    assert res is not None


def test_batch_and_stats_persistence_roundtrip(tmp_path):
    async def run_batch():
        clf = IntelligentDocumentClassifier()
        docs = [
            ("d1", "Network Guide", "Router switch vlan latency firewall"),
            ("d2", "Amplifier Spec", "Op-amp voltage gain resistor capacitor circuit"),
            ("d3", "Procedure", "Step 1: Remove power. Step 2: Inspect gear torque load tolerance."),
        ]
        res = await clf.batch_classify(docs)
        stats = clf.aggregate_statistics(res)
        return res, stats

    res, stats = asyncio.run(run_batch())
    assert stats["total"] == 3

    pm = ClassificationPersistenceManager(base_path=str(tmp_path / "cls"))
    pm.save_jsonl(res, append=False)
    # Validate JSONL load
    loaded = pm.load_jsonl()
    assert len(loaded) == 3

    # Convert to Parquet
    parquet_path = pm.to_parquet()
    assert parquet_path.exists()

    df = pm.load_parquet()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    assert "predicted_type" in df.columns
    assert pm.roundtrip_validate(sample=2) is True
