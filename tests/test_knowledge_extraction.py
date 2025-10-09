import os
from pathlib import Path

from phase4a_knowledge_extraction import (
    KnowledgeExtractor,
    _demo_text,
)


def test_extraction_basic(tmp_path):
    ke = KnowledgeExtractor(base_path=str(tmp_path / "kg"))
    text = _demo_text()
    snapshot = ke.extract_all("doc1", text)

    # Basic counts
    assert len(snapshot.entities) >= 5
    assert len(snapshot.specifications) >= 2
    assert len(snapshot.process_steps) >= 2

    # At least one relation extracted
    assert len(snapshot.relations) >= 1

    # Persistence
    paths = ke.persist_snapshot(snapshot)
    assert "entities" in paths and paths["entities"].exists()
    assert paths["snapshot"].exists()

    # Load partial stats
    ents_loaded = ke.load_entities(limit=3)
    assert len(ents_loaded) <= 3


def test_spec_normalization(tmp_path):
    ke = KnowledgeExtractor(base_path=str(tmp_path / "kg2"))
    text = "Voltage: 5V torque = 12 Nm speed (rpm): 1500 temperature: 25 C"
    snapshot = ke.extract_all("doc2", text)
    units = {s.unit for s in snapshot.specifications if s.unit}
    # Expect normalized units include V, Nm, rpm, C
    assert {"V", "Nm", "rpm", "C"}.issubset(units)


def test_process_ordering(tmp_path):
    ke = KnowledgeExtractor(base_path=str(tmp_path / "kg3"))
    text = """Step 1: Remove cover\nStep 2: Inspect gear\nStep 3: Install sensor"""
    snapshot = ke.extract_all("doc3", text)
    indices = [s.index for s in snapshot.process_steps]
    assert indices == sorted(indices)
    assert len(snapshot.process_steps) == 3


def test_relation_window(tmp_path):
    ke = KnowledgeExtractor(base_path=str(tmp_path / "kg4"))
    text = "The resistor is connected to the capacitor while the amplifier remains idle."
    snapshot = ke.extract_all("doc4", text)
    assert any(r.type == "connectivity" for r in snapshot.relations)


def test_spec_range_and_invalid_unit(tmp_path):
    ke = KnowledgeExtractor(base_path=str(tmp_path / "kg5"))
    text = "Voltage: 5-15V torque = 10-20 Nm bogusvalue: 10XYZ speed (rpm): 1200"
    snap = ke.extract_all("doc5", text)
    # Range numeric_value should be averaged
    rng = [s for s in snap.specifications if s.name.startswith("voltage")][0]
    assert rng.numeric_value is not None and 9.5 < rng.numeric_value < 10.6
    # Invalid unit 'XYZ' should be dropped
    assert not any(s.unit == "XYZ" for s in snap.specifications)


def test_no_relations_case(tmp_path):
    ke = KnowledgeExtractor(base_path=str(tmp_path / "kg6"))
    text = "Resistor capacitor amplifier listed without verbs."
    snap = ke.extract_all("doc6", text)
    assert len(snap.entities) >= 2
    assert len(snap.relations) == 0


def test_fallback_step_detection(tmp_path):
    ke = KnowledgeExtractor(base_path=str(tmp_path / "kg7"))
    text = "Install sensor\nRemove cover\nInspect gear"
    snap = ke.extract_all("doc7", text)
    assert len(snap.process_steps) == 3
