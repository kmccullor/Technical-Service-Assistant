"""Phase 4A Task 4: Automated Knowledge Extraction (Local-First)

This module performs heuristic/local extraction of structured technical knowledge:
- Entities (components, materials, signals, tools)
- Relations (connectivity, flow, part-of)
- Specification parameters (name, value, unit)
- Process steps (ordered procedural instructions)
- Knowledge graph snapshot assembly + persistence

Design Principles:
- 100% local: No network or external model calls
- Extensible: Clear hooks for future ML-based NER/RE integration
- Transparent: Deterministic regex + rule-based pipeline with confidence heuristics
- Incremental persistence: JSONL append + snapshot graph export

"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from utils.logging_config import get_logger
from utils.monitoring import monitor_performance

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class Entity:
    entity_id: str
    text: str
    type: str
    start: int
    end: int
    confidence: float
    occurrences: int = 1
    context_window: Optional[str] = None


@dataclass
class Relation:
    relation_id: str
    source_id: str
    target_id: str
    type: str
    evidence: str
    confidence: float


@dataclass
class SpecificationParameter:
    spec_id: str
    name: str
    raw_value: str
    numeric_value: Optional[float]
    unit: Optional[str]
    context: Optional[str]
    confidence: float


@dataclass
class ProcessStep:
    step_id: str
    index: int
    action: str
    raw_text: str
    dependencies: List[int] = field(default_factory=list)
    confidence: float = 0.8


@dataclass
class KnowledgeGraphSnapshot:
    snapshot_id: str
    created_at: str
    document_id: str
    entities: List[Entity]
    relations: List[Relation]
    specifications: List[SpecificationParameter]
    process_steps: List[ProcessStep]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at,
            "document_id": self.document_id,
            "entities": [asdict(e) for e in self.entities],
            "relations": [asdict(r) for r in self.relations],
            "specifications": [asdict(s) for s in self.specifications],
            "process_steps": [asdict(p) for p in self.process_steps],
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Extraction Helpers
# ---------------------------------------------------------------------------


class EntityExtractor:
    """Heuristic entity extraction using curated domain lexicons and regex."""

    COMPONENT_TERMS = [
        "resistor",
        "capacitor",
        "transistor",
        "amplifier",
        "router",
        "switch",
        "gear",
        "shaft",
        "bearing",
        "motor",
        "sensor",
        "controller",
        "valve",
        "pump",
    ]

    MATERIAL_TERMS = ["steel", "copper", "aluminum", "plastic", "ceramic"]
    SIGNAL_TERMS = ["voltage", "current", "temperature", "pressure", "latency"]
    TOOL_TERMS = ["screwdriver", "wrench", "oscilloscope", "multimeter"]

    TYPE_MAP: Dict[str, str] = {}
    for t in COMPONENT_TERMS:
        TYPE_MAP[t] = "component"
    for t in MATERIAL_TERMS:
        TYPE_MAP[t] = "material"
    for t in SIGNAL_TERMS:
        TYPE_MAP[t] = "signal"
    for t in TOOL_TERMS:
        TYPE_MAP[t] = "tool"

    WORD_BOUNDARY_PATTERN = re.compile(r"\b(" + r"|".join(re.escape(t) for t in TYPE_MAP.keys()) + r")\b", re.IGNORECASE)

    def extract(self, text: str, context_window: int = 40) -> List[Entity]:
        entities: Dict[Tuple[str, int, int], Entity] = {}
        for match in self.WORD_BOUNDARY_PATTERN.finditer(text):
            raw = match.group(1)
            normalized = raw.lower()
            ent_type = self.TYPE_MAP.get(normalized, "other")
            start, end = match.span()
            left = max(0, start - context_window)
            right = min(len(text), end + context_window)
            ctx = text[left:right]
            key = (normalized, start, end)
            confidence = 0.9 if ent_type != "other" else 0.6
            entities[key] = Entity(
                entity_id=str(uuid.uuid4()),
                text=normalized,
                type=ent_type,
                start=start,
                end=end,
                confidence=confidence,
                occurrences=1,
                context_window=ctx,
            )
        return list(entities.values())


class SpecificationMiner:
    """Extract name:value(+unit) technical specifications."""

    # Patterns like: Voltage: 5V, torque = 12 Nm, speed (rpm): 1500, temperature: 25 C
    SPEC_PATTERN = re.compile(
        r"(?P<name>[A-Za-z][A-Za-z0-9_ \-/()]{2,40}?)\s*(?:[:=]|\bis\b)\s*"
        r"(?P<value>[0-9]+(?:\.[0-9]+)?(?:\s*[–-]\s*[0-9]+(?:\.[0-9]+)?)?)\s*"
        r"(?P<unit>[A-Za-z%Ωμ/°]{0,5})",
        re.IGNORECASE,
    )

    UNIT_NORMALIZE = {
        "volts": "V",
        "volt": "V",
        "amps": "A",
        "amp": "A",
        "c": "C",
        "°c": "C",
        "ohms": "Ω",
        "ohm": "Ω",
        "nm": "Nm",
        "rpm": "rpm",
        "hz": "Hz",
        "w": "W",
    }

    RANGE_SPLIT = re.compile(r"[–-]")

    def normalize_unit(self, unit: str) -> Optional[str]:
        if not unit:
            return None
        u = unit.strip().lower()
        return self.UNIT_NORMALIZE.get(u, unit)

    def parse_numeric(self, raw_value: str) -> Optional[float]:
        # If range, take mean heuristic
        if self.RANGE_SPLIT.search(raw_value):
            parts = [p.strip() for p in self.RANGE_SPLIT.split(raw_value) if p.strip()]
            nums = []
            for p in parts:
                try:
                    nums.append(float(p))
                except ValueError:
                    return None
            if nums:
                return sum(nums) / len(nums)
            return None
        try:
            return float(raw_value)
        except ValueError:
            return None

    PAREN_UNIT_PATTERN = re.compile(r"^(?P<base>.+?)\((?P<unit>[A-Za-z%Ωμ/°]{1,6})\)$")

    def extract(self, text: str) -> List[SpecificationParameter]:
        specs: List[SpecificationParameter] = []
        for m in self.SPEC_PATTERN.finditer(text):
            raw_name = m.group("name").strip()
            name = raw_name.lower()
            raw_value = m.group("value").strip()
            captured_unit = m.group("unit")
            unit = self.normalize_unit(captured_unit)

            # If unit absent try to extract from parenthetical part of the name e.g. 'speed (rpm)'
            if (not unit) and '(' in raw_name and raw_name.endswith(')'):
                pm = self.PAREN_UNIT_PATTERN.match(raw_name)
                if pm:
                    candidate_unit = self.normalize_unit(pm.group('unit'))
                    # Only accept short plausible unit tokens
                    if candidate_unit and len(candidate_unit) <= 5:
                        unit = candidate_unit
                        name = pm.group('base').strip().lower()

            # Discard obviously invalid long unit captures (e.g. a following word like 'temperature')
            if unit and len(unit) > 5:
                unit = None
            # Guard against partial capture of following spec name (e.g., 'temperat' from 'temperature:')
            if unit and captured_unit:
                end_pos = m.end('unit')
                if end_pos < len(text) and text[end_pos].isalpha():  # next char continues a word
                    unit = None
            # Additional disambiguation: if immediately after numeric (and optional unit) a new spec name pattern appears, drop unit
            if unit:
                lookahead_segment = text[m.end('value'): m.end('value') + 30]
                # pattern: optional space then word >=3 chars then ':'
                if re.search(r"\s+[A-Za-z][A-Za-z0-9_ \-/()]{2,40}:", lookahead_segment):
                    # Only drop if captured unit length >=3 (more likely false positive) and not in known unit map
                    if captured_unit and (len(captured_unit) > 2 and captured_unit.lower() not in self.UNIT_NORMALIZE):
                        unit = None
            # Second-chance parentheses extraction if unit invalidated
            if (not unit) and '(' in raw_name and raw_name.endswith(')'):
                pm2 = self.PAREN_UNIT_PATTERN.match(raw_name)
                if pm2:
                    candidate_unit2 = self.normalize_unit(pm2.group('unit'))
                    if candidate_unit2 and len(candidate_unit2) <= 5:
                        unit = candidate_unit2
                        name = pm2.group('base').strip().lower()
            num = self.parse_numeric(raw_value)
            confidence = 0.85 if num is not None else 0.7
            specs.append(
                SpecificationParameter(
                    spec_id=str(uuid.uuid4()),
                    name=name,
                    raw_value=raw_value,
                    numeric_value=num,
                    unit=unit,
                    context=None,
                    confidence=confidence,
                )
            )
        return specs


class ProcessDiscovery:
    """Identify procedural steps in text."""

    STEP_PATTERNS = [
        re.compile(r"^(?:step\s+)?(?P<idx>[0-9]{1,3})[).:\-]\s+(?P<action>.+)", re.IGNORECASE),
        re.compile(r"^(?P<bullet>[-*])\s+(?P<action>.+)")
    ]

    def extract(self, text: str) -> List[ProcessStep]:
        steps: List[ProcessStep] = []

        # First pass: detect inline multi-step patterns (e.g., 'Step 1: ... Step 2: ...')
        inline_pattern = re.compile(r"(Step\s+[0-9]{1,3}[:).\-]\s+)", re.IGNORECASE)
        segments: List[Tuple[str, int]] = []
        last_pos = 0
        matches = list(inline_pattern.finditer(text))
        if matches:
            for i, m in enumerate(matches):
                start = m.start()
                if i > 0:
                    prev = matches[i - 1]
                    segments.append((text[prev.start():start], prev.start()))
            # Add final segment
            last_match = matches[-1]
            segments.append((text[last_match.start():], last_match.start()))
        else:
            # Fallback: treat as lines
            for line in text.splitlines():
                segments.append((line, 0))

        # Process segments individually using line-level logic
        for segment_text, _ in segments:
            for line in segment_text.splitlines():
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                matched = False
                for pat in self.STEP_PATTERNS:
                    m = pat.match(line_stripped)
                    if m:
                        matched = True
                        if "idx" in m.groupdict() and m.group("idx"):
                            try:
                                idx = int(m.group("idx"))
                            except ValueError:
                                idx = len(steps) + 1
                            action = m.group("action").strip()
                        else:
                            idx = len(steps) + 1
                            action = m.group("action").strip()
                        steps.append(
                            ProcessStep(
                                step_id=str(uuid.uuid4()),
                                index=idx,
                                action=action,
                                raw_text=line_stripped,
                                dependencies=[idx - 1] if idx > 1 else [],
                                confidence=0.85 if "idx" in m.groupdict() else 0.7,
                            )
                        )
                        break
                if not matched:
                    if re.match(r"^(install|remove|inspect|measure|tighten|connect|disconnect|verify|record)\b", line_stripped, re.IGNORECASE):
                        steps.append(
                            ProcessStep(
                                step_id=str(uuid.uuid4()),
                                index=len(steps) + 1,
                                action=line_stripped,
                                raw_text=line_stripped,
                                dependencies=[len(steps)] if steps else [],
                                confidence=0.6,
                            )
                        )

        # Normalize duplicate indices
        seen = set()
        for s in steps:
            if s.index in seen:
                s.index = max([st.index for st in steps]) + 1
            seen.add(s.index)
        steps.sort(key=lambda x: x.index)
        return steps


class RelationExtractor:
    """Extract simple relations based on connectivity verbs and proximity."""

    CONNECT_VERBS = ["connect", "connected", "attach", "attached", "link", "linked", "couple", "coupled"]
    VERB_PATTERN = re.compile(r"\b(" + r"|".join(CONNECT_VERBS) + r")\b", re.IGNORECASE)

    WINDOW = 80  # character window around relation verb

    def extract(self, text: str, entities: List[Entity]) -> List[Relation]:
        relations: List[Relation] = []
        if not entities:
            return relations
        # Build quick lookup by span overlap
        for m in self.VERB_PATTERN.finditer(text):
            verb_span = m.span()
            left = max(0, verb_span[0] - self.WINDOW)
            right = min(len(text), verb_span[1] + self.WINDOW)
            window_entities = [e for e in entities if not (e.end < left or e.start > right)]
            # Pair first two distinct entities in window as relation
            if len(window_entities) >= 2:
                # Prefer distinct types if possible
                window_entities.sort(key=lambda e: (e.start, e.type))
                e1 = window_entities[0]
                e2 = None
                for candidate in window_entities[1:]:
                    if candidate.entity_id != e1.entity_id:
                        e2 = candidate
                        break
                if e2:
                    relations.append(
                        Relation(
                            relation_id=str(uuid.uuid4()),
                            source_id=e1.entity_id,
                            target_id=e2.entity_id,
                            type="connectivity",
                            evidence=text[left:right],
                            confidence=0.8,
                        )
                    )
        return relations


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class KnowledgeExtractor:
    def __init__(self, base_path: str = "data/knowledge"):
        self.entity_extractor = EntityExtractor()
        self.spec_miner = SpecificationMiner()
        self.process_discovery = ProcessDiscovery()
        self.relation_extractor = RelationExtractor()
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"KnowledgeExtractor initialized at {self.base_path}")

    @monitor_performance("knowledge_extraction")
    def extract_all(self, document_id: str, text: str) -> KnowledgeGraphSnapshot:
        entities = self.entity_extractor.extract(text)
        specs = self.spec_miner.extract(text)
        steps = self.process_discovery.extract(text)
        relations = self.relation_extractor.extract(text, entities)

        snapshot = KnowledgeGraphSnapshot(
            snapshot_id=str(uuid.uuid4()),
            created_at=datetime.utcnow().isoformat(),
            document_id=document_id,
            entities=entities,
            relations=relations,
            specifications=specs,
            process_steps=steps,
            metadata={
                "entity_count": len(entities),
                "relation_count": len(relations),
                "spec_count": len(specs),
                "process_step_count": len(steps),
            },
        )
        return snapshot

    # Persistence -----------------------------------------------------------
    def persist_snapshot(self, snapshot: KnowledgeGraphSnapshot) -> Dict[str, Path]:
        # Append each category to JSONL, plus full snapshot
        paths: Dict[str, Path] = {}
        cat_map = {
            "entities": snapshot.entities,
            "relations": snapshot.relations,
            "specifications": snapshot.specifications,
            "process_steps": snapshot.process_steps,
        }
        for name, items in cat_map.items():
            p = self.base_path / f"{name}.jsonl"
            with open(p, "a", encoding="utf-8") as f:
                for item in items:
                    f.write(json.dumps(asdict(item)) + "\n")
            paths[name] = p
        snap_path = self.base_path / f"snapshot_{snapshot.snapshot_id}.json"
        with open(snap_path, "w", encoding="utf-8") as f:
            json.dump(snapshot.to_dict(), f, indent=2)
        paths["snapshot"] = snap_path
        logger.info(
            "Persisted snapshot %s (entities=%d, relations=%d, specs=%d, steps=%d)",
            snapshot.snapshot_id,
            len(snapshot.entities),
            len(snapshot.relations),
            len(snapshot.specifications),
            len(snapshot.process_steps),
        )
        return paths

    def load_entities(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        p = self.base_path / "entities.jsonl"
        if not p.exists():
            return []
        out: List[Dict[str, Any]] = []
        with open(p, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if line.strip():
                    out.append(json.loads(line))
                if limit and len(out) >= limit:
                    break
        return out

    def snapshot_statistics(self) -> Dict[str, Any]:
        return {
            "total_entities": len(self.load_entities(limit=None)),
        }


# ---------------------------------------------------------------------------
# Quick Test Harness
# ---------------------------------------------------------------------------

def _demo_text() -> str:
    return (
        "Step 1: Disconnect power. Step 2: Inspect resistor and capacitor. "
        "Measure voltage: 5V and current: 2A. The resistor is connected to the amplifier. "
        "Then install the sensor and tighten the shaft. Operating torque = 12 Nm. Speed (rpm): 1500."
    )


def _quick_demo():  # pragma: no cover - demo harness
    ke = KnowledgeExtractor()
    text = _demo_text()
    snap = ke.extract_all("doc_demo", text)
    ke.persist_snapshot(snap)
    print("Entities:", [e.text for e in snap.entities])
    print("Specs:", [(s.name, s.raw_value, s.unit) for s in snap.specifications])
    print("Relations:", len(snap.relations))
    print("Steps:", [(st.index, st.action[:25]) for st in snap.process_steps])


if __name__ == "__main__":  # pragma: no cover
    _quick_demo()  # pragma: no cover
