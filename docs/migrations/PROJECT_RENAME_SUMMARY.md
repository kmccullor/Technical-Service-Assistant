# Project Rename Summary

**Date**: 2025-09-20T08:36:16-04:00
**Action**: Project renamed from "AI PDF Vector Stack" to "Technical Service Assistant"
**Directory**: Technical-Service-Assistant → Technical-Service-Assistant

## Changes Made

### 1. Documentation Updates
- Updated all Markdown files in root directory
- Updated all documentation in docs/ directory
- Updated project titles, descriptions, and references

### 2. Configuration Files
- docker-compose.yml: Updated service names and secret keys
- searxng/settings.yml: Updated secret key references
- Container names updated to technical-service-assistant prefix

### 3. Python Code Updates
- All Python files updated with new project name
- Module docstrings and comments updated
- Hardcoded paths updated to new directory structure

### 4. Frontend Updates
- HTML, JavaScript, and CSS files updated
- User interface references updated

### 5. Backup Files Created
- All modified files backed up with timestamp
- Pattern: filename.bak.YYYYMMDD_HHMMSS

## Next Steps

1. Rename the project directory:
   ```bash
   cd /home/kmccullor/Projects/
   mv Technical-Service-Assistant Technical-Service-Assistant
   ```

2. Update any external references or bookmarks

3. Restart Docker containers to pick up new names:
   ```bash
   docker compose down
   docker compose up -d --build
   ```

4. Update any IDE or editor workspace settings

## Verification

After renaming, verify the changes:
```bash
grep -r "Technical-Service-Assistant" . --exclude-dir=.git --exclude="*.bak.*"
grep -r "AI PDF Vector Stack" . --exclude-dir=.git --exclude="*.bak.*"
```

Should return minimal or no results (excluding backup files).
