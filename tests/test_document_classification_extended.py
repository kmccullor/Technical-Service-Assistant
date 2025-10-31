import asyncio

import pandas as pd

from phase4a_document_classification import (
    ClassificationPersistenceManager,
    DocumentFeatureExtractor,
    IntelligentDocumentClassifier,
)


def _run(coro):
    return asyncio.run(coro)


def test_empty_content_edge_case():
    clf = IntelligentDocumentClassifier()
    res = _run(clf.classify_document("empty", "", ""))
    assert res.priority_score >= 0
    assert res.quality_score >= 0
    assert 0 <= res.confidence <= 1


def test_all_caps_numeric_bias():
    clf = IntelligentDocumentClassifier()
    content = "VOLTAGE 5V CURRENT 2A TORQUE 10NM" * 3
    res = _run(clf.classify_document("caps", "TEST", content))
    # Uppercase ratio penalty should reduce quality vs. a neutral baseline
    assert res.quality_score < 0.6


def test_long_document_scaling():
    clf = IntelligentDocumentClassifier()
    content = "This specification includes voltage current resistor capacitor diagram analysis. " * 120
    res = _run(clf.classify_document("long", "Mega Spec", content))
    # Length-based richness should influence confidence upward
    assert res.confidence > 0.4


def test_persistence_roundtrip(tmp_path):
    clf = IntelligentDocumentClassifier()
    docs = [
        ("d1", "Router Guide", "This guide covers router vlan switch latency"),
        ("d2", "Amplifier Spec", "Specification resistor capacitor voltage current tolerance"),
    ]
    results = _run(clf.batch_classify(docs))
    pm = ClassificationPersistenceManager(base_path=str(tmp_path / "clsx"))
    pm.save_jsonl(results, append=False)
    pm.to_parquet()
    df = pm.load_parquet()
    assert isinstance(df, pd.DataFrame)
    assert {"predicted_type", "predicted_domain"}.issubset(df.columns)
    assert pm.roundtrip_validate(sample=2)


def test_feature_extractor_signal_density():
    text = "voltage current voltage current voltage"
    feat = DocumentFeatureExtractor.domain_scores(text)
    # electrical proxies should accumulate
    assert feat.get("electrical", 0) >= max(v for k, v in feat.items() if k != "electrical")
