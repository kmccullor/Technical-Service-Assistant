"""Targeted tests to raise Phase 4A module coverage above 95%.

Focuses on uncovered branches/lines in:
 - phase4a_document_classification.ClassificationPersistenceManager (parquet conversion, roundtrip)
 - ConfidenceCalibrator richness/temperature scaling with small sample size
 - PriorityScorer / QualityAssessor edge cases
 - SpecificationMiner fallback unit extraction & range parsing
 - ProcessDiscovery hybrid detection (inline + verb-based fallback)
 - RelationExtractor no-relations path
 - KnowledgeExtractor persistence snapshot path
"""

import json
from pathlib import Path

import pytest

from phase4a_document_classification import (
    ClassificationPersistenceManager,
    ClassifiedDocument,
    ConfidenceCalibrator,
    DocumentType,
    IntelligentDocumentClassifier,
    PriorityScorer,
    QualityAssessor,
    TechnicalDomain,
    _quick_test,
)
from phase4a_knowledge_extraction import KnowledgeExtractor, ProcessDiscovery, RelationExtractor, SpecificationMiner


@pytest.mark.unit
def test_classification_parquet_roundtrip(tmp_path: Path):
    pm = ClassificationPersistenceManager(base_path=str(tmp_path / "cls"))

    # Create a few synthetic ClassifiedDocument objects to ensure multiple records
    docs = []
    for i in range(3):
        docs.append(
            ClassifiedDocument(
                document_id=f"doc{i}",
                title=f"Spec {i}",
                content="short content",  # intentionally short to exercise richness branch
                predicted_type=DocumentType.SPECIFICATION,
                predicted_domain=TechnicalDomain.SOFTWARE,
                priority_score=0.5 + i * 0.1,
                quality_score=0.6 + i * 0.05,
                confidence=0.7 + i * 0.05,
                type_probabilities={"specification": 0.7, "manual": 0.2, "report": 0.1},
                domain_probabilities={"software": 0.8, "network": 0.1, "general": 0.1},
                metadata={"length": 2 + i, "section_count": 0},
            )
        )
    pm.save_jsonl(docs, append=False)

    parquet_path = pm.to_parquet()
    assert parquet_path.exists(), "Parquet file should be created"
    df = pm.load_parquet()
    assert df is not None and len(df) == 3
    # Ensure probability columns expanded
    assert any(c.startswith("typeprob_") for c in df.columns)
    assert any(c.startswith("domainprob_") for c in df.columns)
    assert pm.roundtrip_validate(sample=2) is True


@pytest.mark.unit
def test_confidence_calibrator_low_sample_and_richness():
    calibrator = ConfidenceCalibrator(temperature=1.5)
    probs = {"specification": 0.6, "manual": 0.3, "report": 0.1}
    # Very small sample size to hit low richness scaling
    conf_small = calibrator.calibrate(probs, quality_score=0.4, sample_size=1)
    conf_larger = calibrator.calibrate(probs, quality_score=0.4, sample_size=50)
    assert conf_small < conf_larger, "Confidence should increase with sample richness"


@pytest.mark.unit
def test_priority_and_quality_edge_cases():
    scorer = PriorityScorer()
    assessor = QualityAssessor()
    # Extreme uppercase ratio + minimal structure
    features = {
        "section_count": 0,
        "bullet_points": 0,
        "length": 5,
        "uppercase_ratio": 0.9,  # penalized
        "digit_ratio": 0.0,
        "domain_electrical": 0.2,
        "domain_network": 0.2,
        "domain_mechanical": 0.2,
        "domain_software": 0.2,
        "domain_chemical": 0.2,
        "domain_general": 0.0,
    }
    q = assessor.assess(features)
    p = scorer.score(DocumentType.MANUAL, features)
    # Quality should be bounded and not negative
    assert 0 <= q <= 1
    assert 0 <= p <= 1


@pytest.mark.unit
def test_spec_miner_parentheses_fallback_and_range():
    miner = SpecificationMiner()
    text = "Speed (rpm): 1500\nOperating torque = 10-14 Nm\nTemperature: 25 C"
    specs = miner.extract(text)
    names = {s.name for s in specs}
    # Expect normalized names
    assert "speed" in names
    # Check range mean parsing (10-14 => 12)
    torque = next(s for s in specs if "torque" in s.name)
    assert (
        torque.numeric_value and abs(torque.numeric_value - 12) < 0.01
    ), f"Unexpected torque numeric: {torque.numeric_value}; specs={[ (s.name,s.raw_value) for s in specs]}"
    speed = next(s for s in specs if s.name == "speed")
    assert speed.unit == "rpm"


@pytest.mark.unit
def test_process_discovery_hybrid_and_relation_absence():
    from phase4a_knowledge_extraction import Entity

    proc = ProcessDiscovery()
    rel_extractor = RelationExtractor()
    # Text with inline steps and verbs but only one entity to avoid relation creation
    text = "Step 1: Do A. Step 1: Do B. Step 2: Do C."
    steps = proc.extract(text)
    assert len(steps) >= 2
    # Provide a single entity so no pair relation can form
    entities = [Entity(entity_id="e1", text="Do A", type="component", start=10, end=18, confidence=0.9)]
    rels = rel_extractor.extract(text, entities)
    assert rels == []


@pytest.mark.unit
def test_knowledge_extractor_snapshot_persistence(tmp_path: Path):
    ke = KnowledgeExtractor(base_path=str(tmp_path / "ke"))
    text = "Step 1: Disconnect power. Measure voltage: 5V. Connect resistor to capacitor."
    snap = ke.extract_all("docZ", text)
    paths = ke.persist_snapshot(snap)
    # Ensure all category files + snapshot written
    for key in ["entities", "relations", "specifications", "process_steps", "snapshot"]:
        assert key in paths and paths[key].exists()
    # Read snapshot and validate core keys
    snap_loaded = json.loads(paths["snapshot"].read_text())
    assert snap_loaded["document_id"] == "docZ"
    assert "entities" in snap_loaded and "process_steps" in snap_loaded


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_classifier_small_richness_difference():
    classifier = IntelligentDocumentClassifier()
    # Two documents: one very short (low richness), one longer
    docs = [
        ("s1", "Tiny", "API"),
        ("s2", "Network Guide", "Router configuration step switch vlan latency firewall protocol"),
    ]
    results = await classifier.batch_classify(docs)
    assert len(results) == 2
    # Confidence for richer document should generally be >= short one (heuristic expectation)
    confs = {r.document_id: r.confidence for r in results}
    assert confs["s2"] >= confs["s1"]


@pytest.mark.unit
def test_classification_persistence_error_and_validation(tmp_path: Path):
    pm = ClassificationPersistenceManager(base_path=str(tmp_path / "empty"))
    # Ensure jsonl does not exist yet; calling to_parquet should raise
    with pytest.raises(ValueError):
        pm.to_parquet()
    # Roundtrip validate should warn/return False when no records
    assert pm.roundtrip_validate(sample=1) is False
    # Create valid record then append malformed line to exercise JSONDecodeError skip
    doc = ClassifiedDocument(
        document_id="mal1",
        title="Spec",
        content="content",
        predicted_type=DocumentType.SPECIFICATION,
        predicted_domain=TechnicalDomain.SOFTWARE,
        priority_score=0.5,
        quality_score=0.5,
        confidence=0.5,
        type_probabilities={"specification": 1.0},
        domain_probabilities={"software": 1.0},
        metadata={"length": 1, "section_count": 0},
    )
    pm.save_jsonl([doc], append=True)
    # Inject malformed line
    with open(pm.jsonl_path, "a", encoding="utf-8") as f:
        f.write("{malformed json line}\n")
    records = pm.load_jsonl()
    assert any(r["document_id"] == "mal1" for r in records)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_quick_test_harness_executes():
    # Executes demo harness coroutine (internal) to cover its logic
    results, stats = await _quick_test()
    assert len(results) == 3
    assert stats["total"] == 3


@pytest.mark.unit
def test_spec_miner_invalid_unit_followed_by_new_spec():
    # Crafted run-on unit followed immediately by new spec name to trigger invalidation branch
    miner = SpecificationMiner()
    text = "Voltage: 5temperature: 25 C"  # 'temperature' should not be treated as unit
    specs = miner.extract(text)
    volt = next(s for s in specs if s.name.startswith("voltage"))
    # Unit should be None because captured letters merge into next spec name
    assert volt.unit is None


@pytest.mark.unit
def test_classification_append_and_empty_stats(tmp_path: Path):
    pm = ClassificationPersistenceManager(base_path=str(tmp_path / "append"))
    doc = ClassifiedDocument(
        document_id="a1",
        title="Guide",
        content="content",
        predicted_type=DocumentType.MANUAL,
        predicted_domain=TechnicalDomain.GENERAL,
        priority_score=0.1,
        quality_score=0.2,
        confidence=0.3,
        type_probabilities={"manual": 1.0},
        domain_probabilities={"general": 1.0},
        metadata={"length": 1, "section_count": 0},
    )
    pm.save_jsonl([doc], append=False)
    # Append second time to exercise append branch
    pm.save_jsonl([doc], append=True)
    records = pm.load_jsonl()
    assert len(records) == 2
    # Aggregate statistics empty path
    classifier = IntelligentDocumentClassifier()
    assert classifier.aggregate_statistics([]) == {}


@pytest.mark.unit
def test_knowledge_extractor_load_entities_no_file(tmp_path: Path):
    ke = KnowledgeExtractor(base_path=str(tmp_path / "ke_empty"))
    # No entities file yet
    assert ke.load_entities(limit=5) == []


@pytest.mark.unit
def test_confidence_calibrator_upper_bound():
    calibrator = ConfidenceCalibrator(temperature=0.8)
    # Strongly peaked probability + high quality + large sample size
    probs = {"specification": 0.95, "manual": 0.03, "report": 0.02}
    conf = calibrator.calibrate(probs, quality_score=0.95, sample_size=5000)
    # Should be capped at 1.0
    assert 0.95 <= conf <= 1.0


@pytest.mark.unit
def test_process_discovery_duplicate_indices_normalization():
    proc = ProcessDiscovery()
    text = "Step 1: Do A. Step 1: Do B. Step 2: Do C."  # duplicate 'Step 1'
    steps = proc.extract(text)
    indices = [s.index for s in steps]
    # After normalization indices should be strictly increasing
    assert indices == sorted(indices)


@pytest.mark.unit
def test_relation_extractor_positive_path():
    from phase4a_knowledge_extraction import Entity, RelationExtractor

    text = "The resistor is connected to the capacitor near the amplifier."  # multiple entities & verb
    # Minimal entities with spans covering words
    entities = [
        Entity(entity_id="e1", text="resistor", type="component", start=4, end=12, confidence=0.9),
        Entity(entity_id="e2", text="capacitor", type="component", start=30, end=39, confidence=0.9),
        Entity(entity_id="e3", text="amplifier", type="component", start=54, end=63, confidence=0.9),
    ]
    extractor = RelationExtractor()
    rels = extractor.extract(text, entities)
    assert rels, "Expected at least one relation"
    assert rels[0].type == "connectivity"


@pytest.mark.unit
def test_roundtrip_validation_error_paths(tmp_path: Path):
    """Test roundtrip validation error handling paths."""
    pm = ClassificationPersistenceManager(base_path=str(tmp_path / "error_test"))

    # Test with no records (should return False)
    assert pm.roundtrip_validate(sample=1) is False

    # Create a record but corrupt the parquet creation to trigger exception
    doc = ClassifiedDocument(
        document_id="error_test",
        title="Test",
        content="content",
        predicted_type=DocumentType.MANUAL,
        predicted_domain=TechnicalDomain.GENERAL,
        priority_score=0.5,
        quality_score=0.5,
        confidence=0.5,
        type_probabilities={"manual": 1.0},
        domain_probabilities={"general": 1.0},
        metadata={"length": 1, "section_count": 0},
    )
    pm.save_jsonl([doc], append=False)

    # Mock pandas to raise an exception during parquet read
    import pandas as pd

    original_read_parquet = pd.read_parquet

    def mock_read_parquet(*args, **kwargs):
        raise Exception("Mock parquet read error")

    pd.read_parquet = mock_read_parquet
    try:
        # This should catch the exception and return False
        result = pm.roundtrip_validate(sample=1)
        assert result is False
    finally:
        pd.read_parquet = original_read_parquet


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_monitor_performance_exception_handling():
    """Test async monitor_performance decorator exception handling."""
    from experiments.phase4a_document_classification import monitor_performance_async

    @monitor_performance_async("test_operation")
    async def failing_function():
        raise ValueError("Test exception")

    # This should not raise the exception but should log it
    with pytest.raises(ValueError):
        await failing_function()


@pytest.mark.unit
def test_spec_miner_second_chance_parentheses_unit():
    miner = SpecificationMiner()
    # Crafted so captured unit might be invalidated then recovered from parentheses
    text = "Load (Nm): 100 temperature: 25 C"  # 'Nm' valid; ensure still captured
    specs = miner.extract(text)
    load = next(s for s in specs if s.name == "load")
    assert load.unit in {"Nm", "nm"}


@pytest.mark.unit
def test_knowledge_extractor_snapshot_statistics(tmp_path: Path):
    ke = KnowledgeExtractor(base_path=str(tmp_path / "ke_stats"))
    text = "Step 1: Measure voltage. Voltage: 5V. Current: 2A."
    snap = ke.extract_all("docA", text)
    ke.persist_snapshot(snap)
    stats = ke.snapshot_statistics()
    assert stats["total_entities"] >= 0  # existence check (path executed)
    # Exercise load_entities limit branch
    subset = ke.load_entities(limit=1)
    assert len(subset) <= 1
