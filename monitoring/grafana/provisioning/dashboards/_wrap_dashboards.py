#!/usr/bin/env python3
"""Wrap raw Grafana dashboards so provisioning can import them reliably.

For each *.json dashboard file in this directory (excluding files starting with underscore):
 1. Load JSON.
 2. Detect if already wrapped (has keys: dashboard, overwrite) -> skip.
 3. Ensure root dashboard object: if file is raw model (has panels, annotations etc), treat as dashboard.
 4. Ensure a top-level title exists: if missing or looks like a panel metric (e.g. 'CPU Usage %'), synthesize a title from filename.
 5. Normalize datasource references: replace objects {"type":"prometheus","uid": null} with string "Prometheus" for simplicity.
 6. Emit wrapped structure: {"dashboard": <dashboard>, "overwrite": true, "folder": "Technical Service Assistant"}
 7. Backup originals already handled externally.

Rationale: Grafana provisioning sometimes rejects dashboards with missing/implicit title or unresolved datasource UID, logging
"Dashboard title cannot be empty" even when title nested incorrectly. This wrapper enforces consistent format.
"""
from __future__ import annotations
import json, re, pathlib, sys

DASHBOARD_DIR = pathlib.Path(__file__).parent
FOLDER_NAME = "Technical Service Assistant"

PANEL_LIKE_TITLES = {"CPU Usage %", "PostgreSQL Active Connections"}

def normalize_datasources(obj):
    if isinstance(obj, dict):
        # If this dict looks like a datasource reference
        if set(obj.keys()) >= {"type", "uid"} and obj.get("type") == "prometheus":
            return "Prometheus"  # use name resolution
        return {k: normalize_datasources(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize_datasources(v) for v in obj]
    return obj

def to_title(filename: str, existing: str | None) -> str:
    if existing and existing not in PANEL_LIKE_TITLES:
        return existing
    stem = re.sub(r'[_-]+', ' ', filename.rsplit('.', 1)[0]).title()
    return f"Technical Service Assistant - {stem}"

modified = []
for path in DASHBOARD_DIR.glob('*.json'):
    if path.name.startswith('_'):  # skip helper files
        continue
    raw = path.read_text(encoding='utf-8')
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"❌ {path.name}: invalid JSON: {e}")
        continue

    # Already wrapped?
    if isinstance(data, dict) and 'dashboard' in data and 'overwrite' in data:
        print(f"➡️  {path.name}: already wrapped – skipping")
        continue

    dashboard = data
    existing_title = dashboard.get('title')
    dashboard['title'] = to_title(path.name, existing_title)

    dashboard = normalize_datasources(dashboard)

    wrapped = {
        "dashboard": dashboard,
        "overwrite": True,
        "folder": FOLDER_NAME,
    }
    path.write_text(json.dumps(wrapped, indent=2), encoding='utf-8')
    modified.append(path.name)
    print(f"✅ Wrapped {path.name} -> title='{dashboard['title']}'")

if not modified:
    print("No dashboards modified.")
else:
    print(f"\n✅ Completed. Wrapped {len(modified)} dashboards.")
