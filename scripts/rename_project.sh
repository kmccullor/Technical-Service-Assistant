#!/bin/bash

# Project Rename Script: Technical-Service-Assistant → Technical-Service-Assistant
# Date: September 20, 2025

set -e

echo "🔄 Starting project rename from 'Technical-Service-Assistant' to 'Technical-Service-Assistant'"
echo "==================================================================================="

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Backup function
backup_file() {
    local file=$1
    if [[ -f "$file" ]]; then
        cp "$file" "${file}.bak.$(date +%Y%m%d_%H%M%S)"
        log "Backed up $file"
    fi
}

# File replacement function
replace_in_file() {
    local file=$1
    local old_pattern=$2
    local new_pattern=$3
    
    if [[ -f "$file" ]]; then
        backup_file "$file"
        sed -i "s|$old_pattern|$new_pattern|g" "$file"
        log "Updated references in $file"
    fi
}

# Main replacement logic
main() {
    log "Phase 1: Update documentation files"
    
    # Update main documentation
    for file in README.md ARCHITECTURE.md CHANGELOG.md PROJECT_STATUS_SEPTEMBER_2025.md AI_CATEGORIZATION_SUCCESS.md NEXT_STEPS_ANALYSIS.md PLANNING_TASK_REVIEW.md; do
        if [[ -f "$file" ]]; then
            replace_in_file "$file" "AI PDF Vector Stack" "Technical Service Assistant"
            replace_in_file "$file" "Technical-Service-Assistant" "Technical-Service-Assistant"
            replace_in_file "$file" "ai_pdf_vector_stack" "technical_service_assistant"
        fi
    done
    
    # Update docs directory
    find docs/ -name "*.md" -type f | while read -r file; do
        replace_in_file "$file" "AI PDF Vector Stack" "Technical Service Assistant"
        replace_in_file "$file" "Technical-Service-Assistant" "Technical-Service-Assistant"
        replace_in_file "$file" "ai_pdf_vector_stack" "technical_service_assistant"
    done
    
    log "Phase 2: Update configuration files"
    
    # Update Docker Compose
    replace_in_file "docker-compose.yml" "Technical-Service-Assistant" "technical-service-assistant"
    
    # Update SearXNG config
    replace_in_file "searxng/settings.yml" "Technical-Service-Assistant" "technical-service-assistant"
    
    log "Phase 3: Update Python code files"
    
    # Update reranker components
    find reranker/ -name "*.py" -type f | while read -r file; do
        replace_in_file "$file" "AI PDF Vector Stack" "Technical Service Assistant"
        replace_in_file "$file" "Technical-Service-Assistant" "Technical-Service-Assistant"
        replace_in_file "$file" "ai_pdf_vector_stack" "technical_service_assistant"
    done
    
    # Update reasoning engine
    find reasoning_engine/ -name "*.py" -type f | while read -r file; do
        replace_in_file "$file" "AI PDF Vector Stack" "Technical Service Assistant"
        replace_in_file "$file" "Technical-Service-Assistant" "Technical-Service-Assistant"
        replace_in_file "$file" "ai_pdf_vector_stack" "technical_service_assistant"
    done
    
    # Update scripts
    find scripts/ -name "*.py" -type f | while read -r file; do
        replace_in_file "$file" "AI PDF Vector Stack" "Technical Service Assistant"
        replace_in_file "$file" "Technical-Service-Assistant" "Technical-Service-Assistant"
        replace_in_file "$file" "ai_pdf_vector_stack" "technical_service_assistant"
    done
    
    # Update bin directory
    find bin/ -name "*.py" -type f | while read -r file; do
        replace_in_file "$file" "AI PDF Vector Stack" "Technical Service Assistant"
        replace_in_file "$file" "Technical-Service-Assistant" "Technical-Service-Assistant"
        replace_in_file "$file" "ai_pdf_vector_stack" "technical_service_assistant"
    done
    
    # Update other Python files
    find . -maxdepth 1 -name "*.py" -type f | while read -r file; do
        replace_in_file "$file" "AI PDF Vector Stack" "Technical Service Assistant"
        replace_in_file "$file" "Technical-Service-Assistant" "Technical-Service-Assistant"
        replace_in_file "$file" "ai_pdf_vector_stack" "technical_service_assistant"
    done
    
    log "Phase 4: Update frontend files"
    
    # Update frontend
    find frontend/ -name "*.html" -o -name "*.js" -o -name "*.css" | while read -r file; do
        replace_in_file "$file" "AI PDF Vector Stack" "Technical Service Assistant"
        replace_in_file "$file" "Technical-Service-Assistant" "Technical-Service-Assistant"
        replace_in_file "$file" "ai_pdf_vector_stack" "technical_service_assistant"
    done
    
    log "Phase 5: Update hardcoded paths"
    
    # Update hardcoded paths in specific files
    if [[ -f "bin/remote_embedding_test.py" ]]; then
        replace_in_file "bin/remote_embedding_test.py" "/home/kmccullor/Projects/Technical-Service-Assistant" "/home/kmccullor/Projects/Technical-Service-Assistant"
    fi
    
    if [[ -f "bin/monitor_uploads.py" ]]; then
        replace_in_file "bin/monitor_uploads.py" "/home/kmccullor/Projects/Technical-Service-Assistant" "/home/kmccullor/Projects/Technical-Service-Assistant"
    fi
    
    if [[ -f "bin/process_all_pdfs.py" ]]; then
        replace_in_file "bin/process_all_pdfs.py" "/home/kmccullor/Projects/Technical-Service-Assistant" "/home/kmccullor/Projects/Technical-Service-Assistant"
    fi
    
    log "Phase 6: Update container names in Docker Compose"
    
    # Update container names
    replace_in_file "docker-compose.yml" "Technical-Service-Assistant-" "technical-service-assistant-"
    
    log "Phase 7: Create project rename summary"
    
    # Create rename summary
    cat > "PROJECT_RENAME_SUMMARY.md" << EOF
# Project Rename Summary

**Date**: $(date -Iseconds)  
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
   \`\`\`bash
   cd /home/kmccullor/Projects/
   mv Technical-Service-Assistant Technical-Service-Assistant
   \`\`\`

2. Update any external references or bookmarks

3. Restart Docker containers to pick up new names:
   \`\`\`bash
   docker compose down
   docker compose up -d --build
   \`\`\`

4. Update any IDE or editor workspace settings

## Verification

After renaming, verify the changes:
\`\`\`bash
grep -r "Technical-Service-Assistant" . --exclude-dir=.git --exclude="*.bak.*"
grep -r "AI PDF Vector Stack" . --exclude-dir=.git --exclude="*.bak.*"
\`\`\`

Should return minimal or no results (excluding backup files).
EOF
    
    success "Project rename completed successfully!"
    echo ""
    
    log "Summary of changes:"
    echo "  ✅ Documentation files updated"
    echo "  ✅ Configuration files updated"
    echo "  ✅ Python code updated"
    echo "  ✅ Frontend files updated"
    echo "  ✅ Hardcoded paths updated"
    echo "  ✅ Container names updated"
    echo "  ✅ Backup files created"
    echo ""
    
    warning "Important next steps:"
    echo "  1. Rename the project directory manually"
    echo "  2. Restart Docker containers"
    echo "  3. Update any external references"
    echo ""
    
    log "Project rename script completed. See PROJECT_RENAME_SUMMARY.md for details."
}

# Check if we're in the right directory
if [[ ! -f "README.md" ]] || [[ ! -f "docker-compose.yml" ]]; then
    error "This script must be run from the project root directory"
    exit 1
fi

# Run the main function
main "$@"