#!/usr/bin/env python3
"""Unwrap previously wrapped dashboards for Grafana file provisioning.

This reverses _wrap_dashboards.py output so Grafana's file provider sees a raw model
(root object contains 'title', 'panels', etc.). Also sets a folder via provisioning
provider config, not inside the dashboard JSON.

Steps per file:
 1. Load JSON.
 2. If top-level has 'dashboard', extract it.
 3. Ensure dashboard['title'] exists & non-empty; synthesize from filename if needed.
 4. Normalize datasource references: replace objects of shape {'type':'prometheus',...}
    with string 'Prometheus'.
 5. Write back raw model.
"""
from __future__ import annotations
import json, pathlib, re

DIR = pathlib.Path(__file__).parent

SAFE_TITLE_PREFIX = "Technical Service Assistant - "

PANEL_LIKE = {"CPU Usage %", "PostgreSQL Active Connections"}


def synthesize_title(fname: str) -> str:
    stem = fname.rsplit('.', 1)[0]
    human = re.sub(r'[_-]+', ' ', stem).title()
    if not human.lower().startswith('technical service assistant'):
        human = SAFE_TITLE_PREFIX + human
    return human


def normalize_datasource(obj):
    if isinstance(obj, dict):
        # Replace datasource object usage with string when clearly Prometheus
        if obj.keys() >= {"type"} and obj.get("type") == "prometheus":
            return "Prometheus"
        return {k: normalize_datasource(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize_datasource(v) for v in obj]
    return obj

changed = []
for f in DIR.glob('*.json'):
    if f.name.startswith('_'):  # skip helper scripts
        continue
    data = json.loads(f.read_text(encoding='utf-8'))
    if isinstance(data, dict) and 'dashboard' in data and isinstance(data['dashboard'], dict):
        dashboard = data['dashboard']
    else:
        dashboard = data

    title = dashboard.get('title')
    if not title or title in PANEL_LIKE:
        title = synthesize_title(f.name)
        dashboard['title'] = title

    dashboard = normalize_datasource(dashboard)

    # Strip provisioning envelope if present
    if 'dashboard' in data:
        f.write_text(json.dumps(dashboard, indent=2), encoding='utf-8')
        changed.append(f.name)
    else:
        # Already raw; just update if modified
        f.write_text(json.dumps(dashboard, indent=2), encoding='utf-8')
        changed.append(f.name)

print(f"✅ Unwrapped/normalized {len(changed)} dashboards:")
for n in changed:
    print("  -", n)
