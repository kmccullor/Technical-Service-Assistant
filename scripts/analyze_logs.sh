#!/bin/bash

# Advanced Log Analysis Script for Technical Service Assistant
# Analyzes container logs for critical issues and provides specific recommendations

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 Advanced Log Analysis - $(date)${NC}"

# Initialize counters
NETWORK_ISSUES=0
MODEL_ISSUES=0
DATABASE_ISSUES=0
PROCESSING_ISSUES=0
PERFORMANCE_ISSUES=0

# Analyze PDF Processor Critical Issues
echo -e "\n${BLUE}=== PDF PROCESSOR ANALYSIS ===${NC}"

# Network connectivity issues
NETWORK_ERRORS=$(docker logs --since="24h" pdf_processor 2>&1 | grep -c "Failed to resolve" || echo "0")
if [ "$NETWORK_ERRORS" -gt 0 ]; then
    echo -e "${RED}🚨 CRITICAL: $NETWORK_ERRORS DNS resolution failures${NC}"
    echo "   Impact: Cannot connect to Ollama instances"
    echo "   Affected: ollama-server-2, ollama-server-3, ollama-server-4"
    NETWORK_ISSUES=$NETWORK_ERRORS
fi

# Embedding generation failures
EMBEDDING_ERRORS=$(docker logs --since="24h" pdf_processor 2>&1 | grep -c "Failed to get embedding" || echo "0")
if [ "$EMBEDDING_ERRORS" -gt 0 ]; then
    echo -e "${RED}🚨 CRITICAL: $EMBEDDING_ERRORS embedding generation failures${NC}"
    echo "   Impact: Documents cannot be processed for vector search"
    echo "   Root cause: Ollama API connectivity issues"
    MODEL_ISSUES=$EMBEDDING_ERRORS
fi

# Database connection issues
DB_CONNECTION_ERRORS=$(docker logs --since="24h" pdf_processor 2>&1 | grep -c "Failed to connect to database" || echo "0")
if [ "$DB_CONNECTION_ERRORS" -gt 0 ]; then
    echo -e "${RED}🚨 CRITICAL: $DB_CONNECTION_ERRORS database connection failures${NC}"
    echo "   Impact: Cannot store processed documents"
    DATABASE_ISSUES=$((DATABASE_ISSUES + DB_CONNECTION_ERRORS))
fi

# AI Classification issues
AI_CLASSIFICATION_ERRORS=$(docker logs --since="24h" pdf_processor 2>&1 | grep -c "Failed to get AI classification" || echo "0")
if [ "$AI_CLASSIFICATION_ERRORS" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  WARNING: $AI_CLASSIFICATION_ERRORS AI classification failures${NC}"
    echo "   Impact: Documents processed without AI metadata"
    PROCESSING_ISSUES=$AI_CLASSIFICATION_ERRORS
fi

# Analyze Database Issues
echo -e "\n${BLUE}=== DATABASE ANALYSIS ===${NC}"

# Schema constraint violations
CONSTRAINT_ERRORS=$(docker logs --since="24h" pgvector 2>&1 | grep -c "violates check constraint" || echo "0")
if [ "$CONSTRAINT_ERRORS" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  WARNING: $CONSTRAINT_ERRORS schema constraint violations${NC}"
    echo "   Impact: Data dictionary functionality affected"
    DATABASE_ISSUES=$((DATABASE_ISSUES + CONSTRAINT_ERRORS))
fi

# Missing column errors
COLUMN_ERRORS=$(docker logs --since="24h" pgvector 2>&1 | grep -c "column.*does not exist" || echo "0")
if [ "$COLUMN_ERRORS" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  WARNING: $COLUMN_ERRORS missing column errors${NC}"
    echo "   Impact: Data dictionary queries failing"
    DATABASE_ISSUES=$((DATABASE_ISSUES + COLUMN_ERRORS))
fi

# Analyze Ollama Model Availability
echo -e "\n${BLUE}=== OLLAMA MODEL ANALYSIS ===${NC}"

MODELS_LOADED=0
MODELS_MISSING=0

for i in {1..4}; do
    PORT=$((11434 + i - 1))
    MODEL_COUNT=$(curl -s --connect-timeout 3 "http://localhost:$PORT/api/tags" 2>/dev/null | jq -r '.models[]?.name' 2>/dev/null | wc -l || echo "0")
    
    if [ "$MODEL_COUNT" -eq 0 ]; then
        echo -e "${RED}❌ Ollama-server-$i: No models loaded${NC}"
        ((MODELS_MISSING++))
    else
        echo -e "${GREEN}✅ Ollama-server-$i: $MODEL_COUNT models loaded${NC}"
        ((MODELS_LOADED++))
    fi
done

# Analyze System Performance
echo -e "\n${BLUE}=== PERFORMANCE ANALYSIS ===${NC}"

# Check for timeout issues
TIMEOUT_ERRORS=$(docker logs --since="24h" pdf_processor 2>&1 | grep -ic "timeout" || echo "0")
if [ "$TIMEOUT_ERRORS" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  WARNING: $TIMEOUT_ERRORS timeout issues${NC}"
    PERFORMANCE_ISSUES=$TIMEOUT_ERRORS
fi

# Check for memory/resource warnings
MEMORY_WARNINGS=$(docker logs --since="24h" redis-cache 2>&1 | grep -ic "memory overcommit" || echo "0")
if [ "$MEMORY_WARNINGS" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  WARNING: Redis memory overcommit disabled${NC}"
    echo "   Impact: Potential performance degradation and save failures"
    PERFORMANCE_ISSUES=$((PERFORMANCE_ISSUES + MEMORY_WARNINGS))
fi

# Generate Specific Recommendations
echo -e "\n${BLUE}=== SPECIFIC RECOMMENDATIONS ===${NC}"

if [ "$NETWORK_ISSUES" -gt 0 ]; then
    echo -e "${RED}🔧 FIX NETWORK CONNECTIVITY:${NC}"
    echo "   1. docker compose restart pdf_processor"
    echo "   2. docker network inspect technical-service-assistant_default"
    echo "   3. If issues persist: docker compose down && docker compose up -d"
    echo ""
fi

if [ "$MODELS_MISSING" -gt 0 ]; then
    echo -e "${RED}🔧 FIX MODEL LOADING:${NC}"
    echo "   1. Pull required models on all instances:"
    for i in {1..4}; do
        if [ "$i" -le "$MODELS_MISSING" ]; then
            echo "      docker exec ollama-server-$i ollama pull nomic-embed-text:v1.5"
            echo "      docker exec ollama-server-$i ollama pull mistral:7b"
        fi
    done
    echo "   2. Verify models: curl http://localhost:11434/api/tags"
    echo ""
fi

if [ "$DATABASE_ISSUES" -gt 0 ]; then
    echo -e "${YELLOW}🔧 FIX DATABASE ISSUES:${NC}"
    echo "   1. Check schema integrity:"
    echo "      docker exec -it pgvector psql -U postgres -d postgres -c \"\\d+ documents;\""
    echo "   2. If severe: Consider schema migration or recreation"
    echo ""
fi

if [ "$PERFORMANCE_ISSUES" -gt 0 ]; then
    echo -e "${YELLOW}🔧 FIX PERFORMANCE ISSUES:${NC}"
    echo "   1. Enable memory overcommit:"
    echo "      sudo sysctl vm.overcommit_memory=1"
    echo "   2. Make permanent: echo 'vm.overcommit_memory = 1' | sudo tee -a /etc/sysctl.conf"
    echo ""
fi

# Summary
echo -e "\n${BLUE}=== ANALYSIS SUMMARY ===${NC}"
echo "Network Issues: $NETWORK_ISSUES"
echo "Model Issues: $MODEL_ISSUES" 
echo "Database Issues: $DATABASE_ISSUES"
echo "Processing Issues: $PROCESSING_ISSUES"
echo "Performance Issues: $PERFORMANCE_ISSUES"
echo "Models Loaded: $MODELS_LOADED/4"

TOTAL_CRITICAL=$((NETWORK_ISSUES + MODEL_ISSUES + DATABASE_ISSUES))
TOTAL_WARNINGS=$((PROCESSING_ISSUES + PERFORMANCE_ISSUES))

if [ "$TOTAL_CRITICAL" -gt 0 ]; then
    echo -e "\n${RED}🔴 SYSTEM STATUS: $TOTAL_CRITICAL critical issues require immediate attention${NC}"
    exit 1
elif [ "$TOTAL_WARNINGS" -gt 3 ]; then
    echo -e "\n${YELLOW}🟡 SYSTEM STATUS: $TOTAL_WARNINGS warning issues should be addressed${NC}" 
    exit 2
else
    echo -e "\n${GREEN}🟢 SYSTEM STATUS: No critical issues detected${NC}"
    exit 0
fi