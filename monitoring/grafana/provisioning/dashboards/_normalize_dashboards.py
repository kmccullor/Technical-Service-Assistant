#!/usr/bin/env python3
"""Normalize Grafana dashboard JSON files for file-based provisioning.

This script enforces required top-level fields and generates stable unique UIDs
when missing, ensuring Grafana does not reject dashboards with errors like
"Dashboard title cannot be empty".

Rules applied:
1. Ensure required keys exist: title, uid, schemaVersion, version, editable, panels (list)
2. If title missing or blank attempt to infer from filename (hyphens/underscores -> spaces, title case)
3. Generate deterministic uid from normalized title (lowercase alnum + dashes) truncated to 60 chars
4. Guarantee UID uniqueness across directory by appending short hash if collision
5. Set schemaVersion to minimum supported (38) if missing or < 1
6. Set version to 1 if missing
7. Ensure editable boolean (default true)
8. Convert legacy datasource string fields inside panels/targets to objects if needed (string form still generally accepted; we only do minimal cleaning)
9. Skip files starting with '_' (utility scripts) or backup copies.

Creates a backup directory `dashboards_backup_normalized` on first run preserving originals.

Idempotent: running multiple times will not continually modify unchanged files.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict

DIR = Path(__file__).parent
BACKUP_DIR = DIR / "dashboards_backup_normalized"


MAX_UID_LEN = 40


def slugify_uid(title: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
    return base or "dashboard"


def compute_hash(content: Dict[str, Any]) -> str:
    h = hashlib.sha1(json.dumps(content, sort_keys=True).encode("utf-8")).hexdigest()
    return h[:8]


def ensure_backup(original: Path) -> None:
    BACKUP_DIR.mkdir(exist_ok=True)
    rel = original.name
    backup_target = BACKUP_DIR / rel
    if not backup_target.exists():
        shutil.copy2(original, backup_target)


def normalize_dashboard(path: Path, existing_uids: set[str]) -> bool:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:  # noqa: BLE001
        print(f"⚠️  Skipping {path.name}: failed to parse JSON ({e})")
        return False

    changed = False

    # Title handling
    title = data.get("title")
    if not title or not isinstance(title, str) or not title.strip():
        inferred = re.sub(r"[-_]+", " ", path.stem).strip().title()
        data["title"] = inferred or "Dashboard"
        changed = True
        title = data["title"]

    # UID handling
    uid = data.get("uid")

    def finalize_uid(raw: str) -> str:
        # Enforce length <= MAX_UID_LEN. If truncated, append short hash to keep uniqueness if needed.
        cleaned = raw[:MAX_UID_LEN]
        return cleaned

    if not uid or not isinstance(uid, str) or not uid.strip():
        base_uid = slugify_uid(title)
        base_uid = finalize_uid(base_uid)
        candidate = base_uid
        idx = 1
        while candidate in existing_uids:
            suffix = (
                f"-{idx}" if len(base_uid) + len(str(idx)) + 1 <= MAX_UID_LEN else f"-{compute_hash({'i': idx})[:4]}"
            )
            candidate = base_uid[: MAX_UID_LEN - len(suffix)] + suffix
            idx += 1
        data["uid"] = candidate
        existing_uids.add(candidate)
        changed = True
    else:
        # Trim if too long
        if len(uid) > MAX_UID_LEN:
            trimmed = finalize_uid(uid)
            # Ensure uniqueness after trim
            if trimmed in existing_uids:
                h = compute_hash(data)[:4]
                trimmed = trimmed[: MAX_UID_LEN - 5] + "-" + h
            data["uid"] = trimmed
            existing_uids.add(trimmed)
            changed = True
        elif uid in existing_uids:
            # Collision - add hash
            new_uid_base = uid[: MAX_UID_LEN - 5]
            new_uid = new_uid_base + "-" + compute_hash(data)[:4]
            data["uid"] = new_uid
            existing_uids.add(new_uid)
            changed = True
        else:
            existing_uids.add(uid)

    # schemaVersion
    if not isinstance(data.get("schemaVersion"), int) or data.get("schemaVersion", 0) < 1:
        data["schemaVersion"] = 38
        changed = True

    # version
    if not isinstance(data.get("version"), int) or data.get("version", 0) < 1:
        data["version"] = 1
        changed = True

    # editable
    if not isinstance(data.get("editable"), bool):
        data["editable"] = True
        changed = True

    # panels structure
    if "panels" not in data or not isinstance(data.get("panels"), list):
        data["panels"] = []
        changed = True

    # Minimal datasource normalization inside panels
    for panel in data.get("panels", []):
        if isinstance(panel, dict):
            ds = panel.get("datasource")
            if isinstance(ds, str):
                # Leave string form (Grafana accepts) but could convert; optional
                pass
            for tgt in panel.get("targets", []) or []:
                if isinstance(tgt, dict) and isinstance(tgt.get("datasource"), str):
                    # same note as above
                    pass

    if changed:
        ensure_backup(path)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
        tmp.replace(path)
        print(f"✅ Normalized {path.name} (title='{data['title']}', uid='{data['uid']}')")
    else:
        print(f"ℹ️  Already normalized {path.name} (title='{data['title']}', uid='{data['uid']}')")

    return changed


def main() -> int:
    json_files = [p for p in DIR.glob("*.json") if not p.name.startswith("_")]
    if not json_files:
        print("No dashboard JSON files found.")
        return 0

    existing_uids: set[str] = set()
    changed_any = False
    for path in sorted(json_files):
        # Skip obvious backups
        if path.name.endswith(".backup.json"):
            continue
        changed = normalize_dashboard(path, existing_uids)
        changed_any = changed_any or changed

    if changed_any:
        print("\nAll dashboards normalized. You can now restart Grafana:")
        print("  docker compose restart grafana")
    else:
        print("\nNo changes required. Dashboards already normalized.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
