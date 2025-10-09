#!/usr/bin/env python3
"""Security Pattern Audit Scaffold (Phase 2B)

Purpose:
  Provide a lightweight sampling and reporting utility to monitor potential
  false positives introduced by expanding SECURITY_DOCUMENT_PATTERNS.

Current State:
  This is a scaffold. It simulates a corpus with mock filenames/content and
  reports matches grouped by pattern. In Phase 2C/3 this will be wired to
  actual database queries and a persisted historical log.

Usage (development):
  python scripts/security_pattern_audit.py --sample-size 10

Planned Extensions:
  - Integrate with Postgres (document_chunks metadata) for real sampling
  - Maintain historical JSON lines log of match distribution
  - Compute precision proxy: proportion of matches containing core security anchors
  - Weekly scheduled run with trend detection
"""
from __future__ import annotations

import argparse
import random
import re
from typing import Dict, List

# Minimal import; in later phase we will import from pdf_processor utilities
SECURITY_FILENAME_PATTERNS = [
    r".*security.*guide.*",
    r".*encryption.*guide.*",
    r".*certificate.*management.*",
]

SECURITY_CONTENT_PATTERNS = [
    r"encryption\s+standards?",
    r"certificate\s+management",
    r"hardware\s+security\s+module",
]

MOCK_FILENAMES = [
    "RNI_4.16_Hardware_Security_Module_Installation_Guide.pdf",
    "System_Operations_Guide.pdf",
    "Encryption_Standards_Guide.pdf",
    "Certificate_Management_Best_Practices.pdf",
    "User_Interface_Overview.pdf",
    "Performance_Tuning_Guide.pdf",
]

MOCK_CONTENT = [
    "This guide explains encryption standards and secure key rotation procedures.",
    "Basic user onboarding instructions for non-admin operators.",
    "Certificate management and lifecycle operations including CSR generation.",
    "Hardware Security Module integration notes with configuration steps.",
    "General performance considerations without security focus.",
]


def sample_documents(sample_size: int) -> List[Dict[str, str]]:
    population = []
    # Pair filenames and random content to simulate variation
    for fn in MOCK_FILENAMES:
        population.append({"filename": fn, "content": random.choice(MOCK_CONTENT)})
    if sample_size >= len(population):
        return population
    return random.sample(population, sample_size)


def match_patterns(docs: List[Dict[str, str]]):
    results = []
    for doc in docs:
        filename_lower = doc["filename"].lower()
        content_lower = doc["content"].lower()
        matched = []
        for pat in SECURITY_FILENAME_PATTERNS:
            if re.search(pat, filename_lower):
                matched.append({"pattern": pat, "type": "filename"})
        for pat in SECURITY_CONTENT_PATTERNS:
            if re.search(pat, content_lower):
                matched.append({"pattern": pat, "type": "content"})
        results.append({"filename": doc["filename"], "matches": matched})
    return results


def summarize(results):
    pattern_counts = {}
    for r in results:
        for m in r["matches"]:
            key = (m["type"], m["pattern"])
            pattern_counts[key] = pattern_counts.get(key, 0) + 1
    return pattern_counts


def main():
    parser = argparse.ArgumentParser(description="Security pattern audit scaffold")
    parser.add_argument("--sample-size", type=int, default=10, help="Number of documents to sample")
    args = parser.parse_args()

    docs = sample_documents(args.sample_size)
    results = match_patterns(docs)
    summary = summarize(results)

    print("Security Pattern Audit (Scaffold)\n-------------------------------")
    for r in results:
        print(f"File: {r['filename']}")
        if r["matches"]:
            for m in r["matches"]:
                print(f"  - Match: {m['type']} | {m['pattern']}")
        else:
            print("  - No matches")
    print("\nAggregate Counts:")
    for (ptype, pat), count in summary.items():
        print(f"  {ptype}: {pat} -> {count}")

    print("\nNOTE: This is a placeholder; integrate with real corpus in later phase.")


if __name__ == "__main__":  # pragma: no cover
    main()
