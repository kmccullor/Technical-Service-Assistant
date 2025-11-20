#!/bin/bash
"""
Quick Archive Reprocessing Script

Simple bash script to move all archived PDFs back to uploads for reprocessing.
"""

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ARCHIVE_DIR="$PROJECT_ROOT/archive"
UPLOADS_DIR="$PROJECT_ROOT/uploads"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}  Archive Reprocessing for Privacy Classification${NC}"
echo -e "${BLUE}===============================================${NC}"

# Check if directories exist
if [ ! -d "$ARCHIVE_DIR" ]; then
    echo -e "${RED}❌ Archive directory not found: $ARCHIVE_DIR${NC}"
    exit 1
fi

if [ ! -d "$UPLOADS_DIR" ]; then
    echo -e "${RED}❌ Uploads directory not found: $UPLOADS_DIR${NC}"
    exit 1
fi

# Count PDFs in archive
PDF_COUNT=$(find "$ARCHIVE_DIR" -name "*.pdf" -type f | wc -l)

if [ "$PDF_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  No PDF files found in archive directory${NC}"
    exit 0
fi

echo -e "${BLUE}📋 Found $PDF_COUNT PDF files in archive${NC}"
echo -e "${BLUE}📂 Archive: $ARCHIVE_DIR${NC}"
echo -e "${BLUE}📂 Uploads: $UPLOADS_DIR${NC}"

# List first few files as examples
echo -e "\n${BLUE}📄 Example files to be reprocessed:${NC}"
find "$ARCHIVE_DIR" -name "*.pdf" -type f | head -5 | while read file; do
    echo -e "   - $(basename "$file")"
done

if [ "$PDF_COUNT" -gt 5 ]; then
    echo -e "   ... and $((PDF_COUNT - 5)) more files"
fi

# Confirm with user
echo -e "\n${YELLOW}❓ This will copy all archived PDFs back to uploads for reprocessing.${NC}"
echo -e "${YELLOW}   The PDF processor will automatically detect and classify them.${NC}"
read -p "Proceed? (y/N): " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}📋 Reprocessing cancelled${NC}"
    exit 0
fi

# Process files
echo -e "\n${BLUE}🔄 Starting reprocessing...${NC}"

PROCESSED=0
FAILED=0
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Find and process each PDF file
find "$ARCHIVE_DIR" -name "*.pdf" -type f | while read file; do
    filename=$(basename "$file")
    name_without_ext="${filename%.*}"

    # Create unique filename with timestamp
    new_filename="${name_without_ext}_reprocess_${TIMESTAMP}_${PROCESSED}.pdf"
    destination="$UPLOADS_DIR/$new_filename"

    # Copy file to uploads (keep original in archive)
    if cp "$file" "$destination"; then
        echo -e "${GREEN}✅ Queued: $filename -> $new_filename${NC}"
        ((PROCESSED++))
    else
        echo -e "${RED}❌ Failed: $filename${NC}"
        ((FAILED++))
    fi

    # Small delay to avoid overwhelming the processor
    sleep 1
done

echo -e "\n${BLUE}===============================================${NC}"
echo -e "${GREEN}🎉 Reprocessing queue completed!${NC}"
echo -e "${GREEN}   Successfully queued: $PROCESSED files${NC}"

if [ "$FAILED" -gt 0 ]; then
    echo -e "${RED}   Failed to queue: $FAILED files${NC}"
fi

echo -e "\n${BLUE}📋 Next steps:${NC}"
echo -e "   1. Monitor PDF processor logs: ${YELLOW}docker logs -f pdf_processor${NC}"
echo -e "   2. Check processing progress: ${YELLOW}ls -la $UPLOADS_DIR${NC}"
echo -e "   3. View privacy classification results in database"
echo -e "   4. Run privacy statistics: ${YELLOW}python scripts/test_privacy_classification.py${NC}"

echo -e "\n${BLUE}💡 The PDF processor will automatically:${NC}"
echo -e "   - Extract text from each document"
echo -e "   - Scan for confidentiality keywords"
echo -e "   - Classify as public or private"
echo -e "   - Store with appropriate privacy level"

echo -e "\n${GREEN}✨ Archive reprocessing initiated successfully!${NC}"
