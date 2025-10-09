#!/bin/bash

# Daily Morning Checklist Automation Script
# Technical Service Assistant Project
# Run this script every morning before development work

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging
LOG_FILE="logs/daily_checklist_$(date +%Y%m%d).log"
mkdir -p logs

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}❌ ERROR: $1${NC}" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}⚠️  WARNING: $1${NC}" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}✅ SUCCESS: $1${NC}" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}ℹ️  INFO: $1${NC}" | tee -a "$LOG_FILE"
}

# Initialize counters
CRITICAL_ISSUES=0
WARNING_ISSUES=0
TESTS_PASSED=0
TESTS_FAILED=0

echo -e "${BLUE}🌅 Starting Daily Morning Checklist - $(date)${NC}"
log "Starting daily morning checklist"

# Phase 1: Docker Container Health Check
echo -e "\n${BLUE}=== Phase 1: Docker Container Health Check ===${NC}"

info "Checking container status against docker-compose.yml..."

# Get expected services from docker-compose.yml
EXPECTED_CONTAINERS=($(grep -E "container_name:" docker-compose.yml | awk '{print $2}' | sort))
info "Expected containers from docker-compose.yml: ${EXPECTED_CONTAINERS[*]}"

RUNNING_CONTAINERS=($(docker ps --format "{{.Names}}" | sort))
MISSING_CONTAINERS=()

for container in "${EXPECTED_CONTAINERS[@]}"; do
    if docker ps --filter "name=$container" --filter "status=running" -q | grep -q .; then
        success "$container is running"
        ((TESTS_PASSED++))
    else
        error "$container is not running (expected from docker-compose.yml)"
        MISSING_CONTAINERS+=("$container")
        ((CRITICAL_ISSUES++))
        ((TESTS_FAILED++))
        
        # Try to start the container
        info "Attempting to start $container..."
        if docker compose start "$container" > /dev/null 2>&1; then
            sleep 5
            if docker ps --filter "name=$container" --filter "status=running" -q | grep -q .; then
                success "$container started successfully"
                # Remove from missing list since we fixed it
                MISSING_CONTAINERS=("${MISSING_CONTAINERS[@]/$container}")
                ((CRITICAL_ISSUES--))
                ((TESTS_FAILED--))
                ((TESTS_PASSED++))
            else
                error "Failed to start $container after restart attempt"
            fi
        else
            error "Failed to restart $container"
        fi
    fi
done

# Check for extra containers not in compose file
EXTRA_CONTAINERS=()
for container in "${RUNNING_CONTAINERS[@]}"; do
    if [[ ! " ${EXPECTED_CONTAINERS[*]} " =~ " ${container} " ]]; then
        EXTRA_CONTAINERS+=("$container")
    fi
done

if [ ${#EXTRA_CONTAINERS[@]} -gt 0 ]; then
    warning "Extra containers running (not in docker-compose.yml): ${EXTRA_CONTAINERS[*]}"
    ((WARNING_ISSUES++))
fi

# Calculate health percentage
TOTAL_EXPECTED=${#EXPECTED_CONTAINERS[@]}
RUNNING_EXPECTED=$((TOTAL_EXPECTED - ${#MISSING_CONTAINERS[@]}))
HEALTH_PERCENT=$((RUNNING_EXPECTED * 100 / TOTAL_EXPECTED))
info "Container Health: $HEALTH_PERCENT% ($RUNNING_EXPECTED/$TOTAL_EXPECTED services running)"

# Health check endpoints
info "Testing service endpoints..."
ENDPOINTS=(
    "http://localhost:8008/health:Reranker"
    "http://localhost:11434/api/tags:Ollama-1"
    "http://localhost:11435/api/tags:Ollama-2" 
    "http://localhost:11436/api/tags:Ollama-3"
    "http://localhost:11437/api/tags:Ollama-4"
    "http://localhost:8888:SearXNG"
    "http://localhost:8080:Frontend"
)

for endpoint_info in "${ENDPOINTS[@]}"; do
    IFS=':' read -r endpoint name <<< "$endpoint_info"
    if curl -f -s --connect-timeout 10 "$endpoint" > /dev/null 2>&1; then
        success "$name endpoint responsive"
        ((TESTS_PASSED++))
    else
        error "$name endpoint not responding ($endpoint)"
        ((CRITICAL_ISSUES++))
        ((TESTS_FAILED++))
    fi
done

# Phase 2: Log Review & Issue Detection
echo -e "\n${BLUE}=== Phase 2: Log Review & Issue Detection ===${NC}"

info "Scanning container logs for errors (last 24 hours)..."

# Check container logs for critical errors with detailed analysis
CONTAINERS_TO_CHECK=("pdf_processor" "reranker" "pgvector" "ollama-server-1" "redis-cache" "rag-app")

info "Performing detailed log analysis for critical issues..."

# Track critical issues by type
PDF_PROCESSOR_ERRORS=0
PDF_PROCESSOR_WARNINGS=0
DATABASE_ERRORS=0
REDIS_WARNINGS=0
NETWORK_ISSUES=0
MODEL_LOADING_ISSUES=0

for container in "${CONTAINERS_TO_CHECK[@]}"; do
    if docker ps --filter "name=$container" -q | grep -q .; then
        error_count=$(docker logs --since="24h" "$container" 2>/dev/null | grep -E "(ERROR|FATAL|Exception|Failed)" | wc -l || echo "0")
        warning_count=$(docker logs --since="24h" "$container" 2>/dev/null | grep -E "(WARNING|Warning)" | wc -l || echo "0")
        
        # Container-specific analysis
        case $container in
            "pdf_processor")
                PDF_PROCESSOR_ERRORS=$error_count
                PDF_PROCESSOR_WARNINGS=$warning_count
                
                # Check for specific PDF processor issues
                network_errors=$(docker logs --since="24h" "$container" 2>/dev/null | grep -c "Failed to resolve" || echo "0")
                embedding_errors=$(docker logs --since="24h" "$container" 2>/dev/null | grep -c "Failed to get embedding" || echo "0")
                db_connection_errors=$(docker logs --since="24h" "$container" 2>/dev/null | grep -c "Failed to connect to database" || echo "0")
                
                if [ "$network_errors" -gt 0 ]; then
                    error "PDF Processor: $network_errors DNS resolution failures (Ollama connectivity)"
                    NETWORK_ISSUES=$((NETWORK_ISSUES + network_errors))
                    ((CRITICAL_ISSUES++))
                fi
                
                if [ "$embedding_errors" -gt 0 ]; then
                    error "PDF Processor: $embedding_errors embedding generation failures"
                    MODEL_LOADING_ISSUES=$((MODEL_LOADING_ISSUES + embedding_errors))
                    ((CRITICAL_ISSUES++))
                fi
                
                if [ "$db_connection_errors" -gt 0 ]; then
                    error "PDF Processor: $db_connection_errors database connection failures"
                    ((CRITICAL_ISSUES++))
                fi
                ;;
                
            "pgvector")
                DATABASE_ERRORS=$error_count
                if [ "$error_count" -gt 0 ]; then
                    warning "$container has $error_count database errors"
                    ((WARNING_ISSUES++))
                    
                    # Show recent database errors
                    echo "Recent database errors:"
                    docker logs --since="24h" "$container" 2>/dev/null | grep -E "(ERROR|FATAL)" | tail -3 || true
                fi
                ;;
                
            "redis-cache")
                REDIS_WARNINGS=$warning_count
                if [ "$warning_count" -gt 0 ]; then
                    warning "$container has $warning_count warnings (likely memory overcommit)"
                    ((WARNING_ISSUES++))
                fi
                ;;
        esac
        
        if [ "$error_count" -gt 0 ] || [ "$warning_count" -gt 5 ]; then
            if [ "$error_count" -gt 0 ]; then
                error "$container has $error_count errors in last 24h"
                ((CRITICAL_ISSUES++))
            fi
            if [ "$warning_count" -gt 5 ]; then
                warning "$container has $warning_count warnings in last 24h"
                ((WARNING_ISSUES++))
            fi
            
            # Show sample of recent issues
            echo "Recent issues from $container:"
            docker logs --since="24h" "$container" 2>/dev/null | grep -E "(ERROR|FATAL|Exception|Failed|WARNING)" | tail -3 || true
        else
            success "$container has no critical errors"
            ((TESTS_PASSED++))
        fi
    else
        warning "Cannot check logs for $container (container not found)"
        ((WARNING_ISSUES++))
    fi
done

# Check Ollama model loading issues across all instances
info "Checking Ollama model availability across all instances..."
for i in {1..4}; do
    if docker ps --filter "name=ollama-server-$i" -q | grep -q .; then
        model_count=$(curl -s --connect-timeout 5 "http://localhost:1143$((3+i))/api/tags" 2>/dev/null | jq -r '.models[]?.name' | wc -l || echo "0")
        if [ "$model_count" -eq 0 ]; then
            error "Ollama-server-$i has no models loaded"
            ((MODEL_LOADING_ISSUES++))
            ((CRITICAL_ISSUES++))
        else
            success "Ollama-server-$i has $model_count models loaded"
            ((TESTS_PASSED++))
        fi
    fi
done

# Log analysis summary
log "=== LOG ANALYSIS SUMMARY ==="
log "PDF Processor: $PDF_PROCESSOR_ERRORS errors, $PDF_PROCESSOR_WARNINGS warnings"
log "Database: $DATABASE_ERRORS errors"
log "Redis: $REDIS_WARNINGS warnings"
log "Network Issues: $NETWORK_ISSUES"
log "Model Loading Issues: $MODEL_LOADING_ISSUES"

# Check disk space
info "Checking disk space..."
disk_usage=$(df . | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$disk_usage" -gt 90 ]; then
    error "Disk usage at ${disk_usage}% - Critical!"
    ((CRITICAL_ISSUES++))
elif [ "$disk_usage" -gt 80 ]; then
    warning "Disk usage at ${disk_usage}% - Monitor closely"
    ((WARNING_ISSUES++))
else
    success "Disk usage at ${disk_usage}% - Normal"
    ((TESTS_PASSED++))
fi

# Check memory usage
info "Checking memory usage..."
memory_usage=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
if [ "$memory_usage" -gt 90 ]; then
    error "Memory usage at ${memory_usage}% - Critical!"
    ((CRITICAL_ISSUES++))
elif [ "$memory_usage" -gt 80 ]; then
    warning "Memory usage at ${memory_usage}% - Monitor closely"
    ((WARNING_ISSUES++))
else
    success "Memory usage at ${memory_usage}% - Normal"
    ((TESTS_PASSED++))
fi

# Phase 3: End-to-End Functionality Testing
echo -e "\n${BLUE}=== Phase 3: End-to-End Functionality Testing ===${NC}"

DB_CONTAINER="pgvector"
DB_USER="postgres"
DB_NAME="vector_db"

# Database connectivity
info "Testing database connectivity to $DB_NAME..."
if docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
    success "Database connection successful ($DB_NAME)"
    ((TESTS_PASSED++))

    # Check database content using new target DB
    db_stats=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c "
        SELECT 
            COALESCE((SELECT COUNT(*) FROM documents), 0) || ',' ||
            COALESCE((SELECT COUNT(*) FROM document_chunks), 0) || ',' ||
            COALESCE((SELECT COUNT(*) FROM search_events), 0);
    " 2>/dev/null | tr -d ' ')

    IFS=',' read -r doc_count chunk_count event_count <<< "$db_stats"
    info "Database content ($DB_NAME): $doc_count documents, $chunk_count chunks, $event_count search events"
else
    error "Database connection failed ($DB_NAME)"
    ((CRITICAL_ISSUES++))
    ((TESTS_FAILED++))
fi

# Test AI models availability
info "Testing AI model availability..."
models_available=0
for port in 11434 11435 11436 11437; do
    if curl -s --connect-timeout 5 "http://localhost:$port/api/tags" | grep -q "models"; then
        ((models_available++))
        success "Ollama instance on port $port has models available"
        ((TESTS_PASSED++))
    else
        error "Ollama instance on port $port not responding or no models"
        ((CRITICAL_ISSUES++))
        ((TESTS_FAILED++))
    fi
done

info "$models_available/4 Ollama instances available"

# Test core APIs
info "Testing core API endpoints..."
if curl -s --connect-timeout 10 "http://localhost:8008/api/data-dictionary/health" | grep -q "healthy\|ok"; then
    success "Data Dictionary API healthy"
    ((TESTS_PASSED++))
else
    error "Data Dictionary API not responding"
    ((CRITICAL_ISSUES++))
    ((TESTS_FAILED++))
fi

# Test intelligent routing
if curl -X POST -s --connect-timeout 10 "http://localhost:8008/api/intelligent-route" \
   -H "Content-Type: application/json" \
   -d '{"query":"test"}' | grep -q "selected_model\|model"; then
    success "Intelligent routing functional"
    ((TESTS_PASSED++))
else
    warning "Intelligent routing may have issues"
    ((WARNING_ISSUES++))
fi

# Phase 4: Performance & Resource Monitoring
echo -e "\n${BLUE}=== Phase 4: Performance & Resource Monitoring ===${NC}"

info "Collecting performance metrics..."

# Container resource usage
echo "Container Resource Usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | head -10

# Upload directory size
upload_size=$(du -sh uploads/ 2>/dev/null | cut -f1 || echo "0")
log_size=$(du -sh logs/ 2>/dev/null | cut -f1 || echo "0")
info "Directory sizes - uploads: $upload_size, logs: $log_size"

# Database integrity checks
echo -e "\n${BLUE}=== DATABASE INTEGRITY CHECKS ===${NC}"
info "Checking database integrity and orphan records..."

INTEGRITY_CHECK=$(docker exec -it "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c "
SELECT 
    COALESCE(SUM(CASE WHEN d.id IS NULL THEN 1 ELSE 0 END), 0) as orphan_chunks,
    COALESCE(COUNT(DISTINCT CASE WHEN NOT EXISTS(SELECT 1 FROM document_chunks dc WHERE dc.document_id = d.id) THEN d.id END), 0) as empty_documents,
    COALESCE(SUM(CASE WHEN dc.embedding IS NULL THEN 1 ELSE 0 END), 0) as chunks_missing_embeddings,
    COUNT(DISTINCT d.id) as total_documents,
    COUNT(dc.id) as total_chunks
FROM documents d
FULL OUTER JOIN document_chunks dc ON d.id = dc.document_id;
" 2>/dev/null | tr -d ' \t' | head -1)

if [ ! -z "$INTEGRITY_CHECK" ] && [ "$INTEGRITY_CHECK" != "" ]; then
    IFS='|' read -r ORPHAN_CHUNKS EMPTY_DOCS MISSING_EMBEDDINGS TOTAL_DOCS TOTAL_CHUNKS <<< "$INTEGRITY_CHECK"
    
    # Clean up any whitespace/newlines
    ORPHAN_CHUNKS=$(echo "$ORPHAN_CHUNKS" | tr -d ' \t\n\r')
    EMPTY_DOCS=$(echo "$EMPTY_DOCS" | tr -d ' \t\n\r')
    MISSING_EMBEDDINGS=$(echo "$MISSING_EMBEDDINGS" | tr -d ' \t\n\r')
    TOTAL_DOCS=$(echo "$TOTAL_DOCS" | tr -d ' \t\n\r')
    TOTAL_CHUNKS=$(echo "$TOTAL_CHUNKS" | tr -d ' \t\n\r')
    
    info "Database status: $TOTAL_DOCS documents, $TOTAL_CHUNKS chunks"
    
    if [ "${ORPHAN_CHUNKS:-0}" -gt 0 ]; then
        error "Found $ORPHAN_CHUNKS orphan chunks (chunks without documents)"
        ((CRITICAL_ISSUES++))
    else
        success "No orphan chunks found"
        ((TESTS_PASSED++))
    fi
    
    if [ "${EMPTY_DOCS:-0}" -gt 0 ]; then
        warning "Found $EMPTY_DOCS empty documents (documents without chunks)"
        ((WARNING_ISSUES++))
    else
        success "No empty documents found"
        ((TESTS_PASSED++))
    fi
    
    if [ "${MISSING_EMBEDDINGS:-0}" -gt 0 ]; then
        error "Found $MISSING_EMBEDDINGS chunks missing embeddings"
        ((CRITICAL_ISSUES++))
    else
        success "All chunks have embeddings"
        ((TESTS_PASSED++))
    fi
    
    log "Database integrity: ${ORPHAN_CHUNKS:-0} orphans, ${EMPTY_DOCS:-0} empty docs, ${MISSING_EMBEDDINGS:-0} missing embeddings"
else
    warning "Could not perform database integrity checks"
    ((WARNING_ISSUES++))
fi

# Generate Issue Recommendations
echo -e "\n${BLUE}=== ISSUE RECOMMENDATIONS ===${NC}"

if [ "$NETWORK_ISSUES" -gt 0 ]; then
    echo -e "${RED}🚨 CRITICAL: Network Connectivity Issues${NC}"
    echo "  Problem: PDF processor cannot resolve Ollama container hostnames"
    echo "  Impact: Document ingestion completely broken"
    echo "  Fix: docker compose restart pdf_processor && docker network inspect technical-service-assistant_default"
    echo "  Also try: docker compose down && docker compose up -d"
    echo ""
fi

if [ "$MODEL_LOADING_ISSUES" -gt 0 ]; then
    echo -e "${RED}🚨 CRITICAL: AI Model Loading Issues${NC}"
    echo "  Problem: Ollama instances missing required models"
    echo "  Impact: Embedding generation and AI classification failing"
    echo "  Fix: Pull missing models on all instances:"
    echo "    docker exec ollama-server-1 ollama pull nomic-embed-text:v1.5"
    echo "    docker exec ollama-server-1 ollama pull mistral:7b"
    echo "  Repeat for servers 2, 3, 4"
    echo ""
fi

if [ "$DATABASE_ERRORS" -gt 2 ]; then
    echo -e "${YELLOW}⚠️  WARNING: Database Schema Issues${NC}"
    echo "  Problem: Missing columns or constraint violations"
    echo "  Impact: Data dictionary functionality affected"
    echo "  Fix: Check schema integrity:"
    echo "    docker exec -it pgvector psql -U postgres -d vector_db -c \"\\d+ schema_change_log;\""
    echo "    Consider running: make recreate-db (DESTRUCTIVE - backup first!)"
    echo ""
fi

if [ "${ORPHAN_CHUNKS:-0}" -gt 0 ]; then
    echo -e "${RED}🚨 CRITICAL: Database Orphan Chunks${NC}"
    echo "  Problem: $ORPHAN_CHUNKS chunks exist without corresponding documents"
    echo "  Impact: Database inconsistency, potential search issues"
    echo "  Fix: Clean up orphan chunks:"
    echo "    docker exec -it pgvector psql -U postgres -d vector_db -c \"DELETE FROM document_chunks WHERE document_id NOT IN (SELECT id FROM documents);\""
    echo ""
fi

if [ "${EMPTY_DOCS:-0}" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  WARNING: Empty Documents${NC}"
    echo "  Problem: $EMPTY_DOCS documents exist without any chunks"
    echo "  Impact: Failed document processing, storage waste"
    echo "  Fix: Remove empty documents:"
    echo "    docker exec -it pgvector psql -U postgres -d vector_db -c \"DELETE FROM documents WHERE NOT EXISTS (SELECT 1 FROM document_chunks WHERE document_id = documents.id);\""
    echo "  Or reprocess from archive if needed"
    echo ""
fi

if [ "${MISSING_EMBEDDINGS:-0}" -gt 0 ]; then
    echo -e "${RED}🚨 CRITICAL: Missing Embeddings${NC}"
    echo "  Problem: $MISSING_EMBEDDINGS chunks lack vector embeddings"
    echo "  Impact: Search functionality broken for these chunks"
    echo "  Fix: Reprocess documents with missing embeddings"
    echo "    Check PDF processor API endpoints and restart processing"
    echo ""
fi

if [ "$REDIS_WARNINGS" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  WARNING: Redis Memory Configuration${NC}"
    echo "  Problem: Memory overcommit disabled"
    echo "  Impact: Performance degradation, potential save failures"
    echo "  Fix: On host system run:"
    echo "    sudo sysctl vm.overcommit_memory=1"
    echo "    Add 'vm.overcommit_memory = 1' to /etc/sysctl.conf for persistence"
    echo ""
fi

if [ "$PDF_PROCESSOR_ERRORS" -gt 100 ]; then
    echo -e "${RED}🚨 CRITICAL: PDF Processing System Failure${NC}"
    echo "  Problem: $PDF_PROCESSOR_ERRORS errors indicate system failure"
    echo "  Impact: No document processing possible"
    echo "  Fix: Comprehensive restart required:"
    echo "    docker compose restart pdf_processor ollama-server-1 ollama-server-2 ollama-server-3 ollama-server-4"
    echo "    Wait 30 seconds then check: curl http://localhost:11434/api/tags"
    echo ""
fi

# Database Integrity Checks
echo -e "\n${BLUE}=== 🗄️ Database Integrity Validation ===${NC}"
info "Running comprehensive database integrity checks..."

# Run the Makefile database check command
DB_CHECK_OUTPUT=$(cd /home/kmccullor/Projects/Technical-Service-Assistant && make check-db 2>/dev/null)

# Parse the results
ORPHAN_CHUNKS=$(echo "$DB_CHECK_OUTPUT" | grep "Orphan Chunks" | awk '{print $3}' || echo "0")
EMPTY_DOCS=$(echo "$DB_CHECK_OUTPUT" | grep "Empty Documents" | awk '{print $3}' || echo "0")
MISSING_EMBEDDINGS=$(echo "$DB_CHECK_OUTPUT" | grep "Missing Embeddings" | awk '{print $3}' || echo "0")

# Report results
if [ "$ORPHAN_CHUNKS" -gt 0 ]; then
    error "Found $ORPHAN_CHUNKS orphan chunks (no parent document)"
    echo "  Fix: docker exec pgvector psql -U postgres -d vector_db -c \"DELETE FROM document_chunks WHERE NOT EXISTS (SELECT 1 FROM documents d WHERE d.id = document_id);\""
    ((CRITICAL_ISSUES++))
else
    success "No orphan chunks found"
fi

if [ "$EMPTY_DOCS" -gt 0 ]; then
    warning "Found $EMPTY_DOCS empty documents (no chunks)"
    echo "  Fix: docker exec pgvector psql -U postgres -d vector_db -c \"DELETE FROM documents WHERE NOT EXISTS (SELECT 1 FROM document_chunks dc WHERE dc.document_id = id);\""
    ((WARNING_ISSUES++))
else
    success "No empty documents found"
fi

if [ "$MISSING_EMBEDDINGS" -gt 0 ]; then
    error "Found $MISSING_EMBEDDINGS chunks without embeddings"
    echo "  Fix: Move failed documents from archive/ to uploads/ for reprocessing"
    ((CRITICAL_ISSUES++))
else
    success "All chunks have embeddings"
fi

# System Cleanup and Maintenance
echo -e "\n${BLUE}=== 🧹 System Cleanup and Maintenance ===${NC}"
info "Running daily cleanup tasks..."

# Check for backup files (.bak with timestamps)
BACKUP_FILES=$(find /home/kmccullor/Projects/Technical-Service-Assistant -name "*.bak*" -type f 2>/dev/null | wc -l)
if [ "$BACKUP_FILES" -gt 10 ]; then
    warning "Found $BACKUP_FILES backup files - consider cleanup"
    echo "  Fix: find /home/kmccullor/Projects/Technical-Service-Assistant -name \"*.bak*\" -type f -mtime +7 -delete"
    ((WARNING_ISSUES++))
else
    success "Backup files under control ($BACKUP_FILES files)"
fi

# Check log directory size
LOG_SIZE=$(du -sm /home/kmccullor/Projects/Technical-Service-Assistant/logs 2>/dev/null | cut -f1)
if [ "$LOG_SIZE" -gt 500 ]; then
    warning "Log directory is ${LOG_SIZE}MB - consider cleanup"
    echo "  Fix: find /home/kmccullor/Projects/Technical-Service-Assistant/logs -type f -mtime +7 -delete"
    ((WARNING_ISSUES++))
else
    success "Log directory size acceptable (${LOG_SIZE}MB)"
fi

# Clean up Python cache files
PYCACHE_COUNT=$(find /home/kmccullor/Projects/Technical-Service-Assistant -name "__pycache__" -type d 2>/dev/null | wc -l)
if [ "$PYCACHE_COUNT" -gt 20 ]; then
    warning "Found $PYCACHE_COUNT Python cache directories - cleaning up"
    find /home/kmccullor/Projects/Technical-Service-Assistant -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
    success "Cleaned up Python cache files"
else
    success "Python cache files under control ($PYCACHE_COUNT directories)"
fi

# Check Docker system usage (only if docker is available)
if command -v docker >/dev/null 2>&1; then
    DOCKER_RECLAIMABLE=$(docker system df --format "table {{.Reclaimable}}" 2>/dev/null | tail -n +2 | head -1 | grep -o '[0-9.]*GB' | cut -d'G' -f1 || echo "0")
    if [ "$(echo "$DOCKER_RECLAIMABLE > 50" | bc -l 2>/dev/null || echo "0")" -eq 1 ]; then
        warning "Docker has ${DOCKER_RECLAIMABLE}GB reclaimable space"
        echo "  Fix: docker system prune -f --volumes"
        ((WARNING_ISSUES++))
    else
        success "Docker system space usage acceptable"
    fi
fi

# Performance and Data Quality Monitoring
echo -e "\n${BLUE}=== 📊 Performance & Data Quality Monitoring ===${NC}"
info "Checking system performance and data quality..."

# Database performance check
DB_PERFORMANCE=$(docker exec pgvector psql -U postgres -d vector_db -t -c "SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'active';" 2>/dev/null | xargs)
if [ "$DB_PERFORMANCE" -gt 10 ]; then
    warning "High database activity: $DB_PERFORMANCE active connections"
    ((WARNING_ISSUES++))
else
    success "Database activity normal ($DB_PERFORMANCE active connections)"
fi

# Document processing success rate (last 24 hours)
TOTAL_DOCUMENTS=$(docker exec pgvector psql -U postgres -d vector_db -t -c "SELECT COUNT(*) FROM documents;" 2>/dev/null | xargs)
DOCUMENTS_WITH_CHUNKS=$(docker exec pgvector psql -U postgres -d vector_db -t -c "SELECT COUNT(DISTINCT document_id) FROM document_chunks;" 2>/dev/null | xargs)
if [ "$TOTAL_DOCUMENTS" -gt 0 ]; then
    SUCCESS_RATE=$(echo "scale=1; $DOCUMENTS_WITH_CHUNKS * 100 / $TOTAL_DOCUMENTS" | bc -l 2>/dev/null || echo "0")
    if [ "$(echo "$SUCCESS_RATE < 95" | bc -l 2>/dev/null || echo "1")" -eq 1 ]; then
        warning "Document processing success rate: ${SUCCESS_RATE}% ($DOCUMENTS_WITH_CHUNKS/$TOTAL_DOCUMENTS)"
        echo "  Check: docker logs pdf_processor --tail 50 | grep ERROR"
        ((WARNING_ISSUES++))
    else
        success "Document processing success rate: ${SUCCESS_RATE}% ($DOCUMENTS_WITH_CHUNKS/$TOTAL_DOCUMENTS)"
    fi
fi

# API endpoint response time check
API_HEALTH_TIME=$(timeout 10 curl -w "%{time_total}" -s -o /dev/null http://localhost:8008/health 2>/dev/null || echo "999")
if [ "$(echo "$API_HEALTH_TIME > 2.0" | bc -l 2>/dev/null || echo "1")" -eq 1 ]; then
    warning "API response time slow: ${API_HEALTH_TIME}s (health endpoint)"
    ((WARNING_ISSUES++))
else
    success "API response time healthy: ${API_HEALTH_TIME}s"
fi

# System resource monitoring
MEMORY_PERCENT=$(free | awk '/^Mem:/ {printf "%.1f", $3/$2 * 100}')
if [ "$(echo "$MEMORY_PERCENT > 80" | bc -l 2>/dev/null || echo "0")" -eq 1 ]; then
    warning "High memory usage: ${MEMORY_PERCENT}%"
    ((WARNING_ISSUES++))
else
    success "Memory usage acceptable: ${MEMORY_PERCENT}%"
fi

# Security and Configuration Monitoring  
echo -e "\n${BLUE}=== 🔒 Security & Configuration Monitoring ===${NC}"
info "Checking security and configuration status..."

# Check for uncommitted changes in git repository
if [ -d ".git" ]; then
    GIT_STATUS=$(git status --porcelain 2>/dev/null | wc -l)
    if [ "$GIT_STATUS" -gt 5 ]; then
        warning "Many uncommitted changes: $GIT_STATUS files modified"
        echo "  Review: git status"
        ((WARNING_ISSUES++))
    else
        success "Git repository status clean ($GIT_STATUS modified files)"
    fi
fi

# Check critical configuration files exist
CRITICAL_FILES=("config.py" "docker-compose.yml" ".env" "requirements.txt")
MISSING_FILES=0
for file in "${CRITICAL_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        ((MISSING_FILES++))
    fi
done
if [ "$MISSING_FILES" -gt 0 ]; then
    error "Missing critical configuration files: $MISSING_FILES"
    ((CRITICAL_ISSUES++))
else
    success "All critical configuration files present"
fi

# Network connectivity to external services
OLLAMA_CONNECTIVITY=0
for port in 11434 11435 11436 11437; do
    if timeout 5 curl -s http://localhost:$port/api/tags >/dev/null 2>&1; then
        ((OLLAMA_CONNECTIVITY++))
    fi
done
if [ "$OLLAMA_CONNECTIVITY" -lt 3 ]; then
    warning "Limited Ollama connectivity: $OLLAMA_CONNECTIVITY/4 instances responding"
    ((WARNING_ISSUES++))
else
    success "Ollama connectivity healthy: $OLLAMA_CONNECTIVITY/4 instances responding"
fi

# Final Summary
echo -e "\n${BLUE}=== Daily Checklist Summary ===${NC}"
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Tests Passed: $TESTS_PASSED"
echo "Tests Failed: $TESTS_FAILED"
echo "Critical Issues: $CRITICAL_ISSUES"
echo "Warning Issues: $WARNING_ISSUES"
echo ""
echo "Issue Breakdown:"
echo "  Network Issues: $NETWORK_ISSUES"
echo "  Model Loading Issues: $MODEL_LOADING_ISSUES"
echo "  PDF Processor Errors: $PDF_PROCESSOR_ERRORS"
echo "  Database Errors: $DATABASE_ERRORS"
echo "  Redis Warnings: $REDIS_WARNINGS"
echo "  Orphan Chunks: ${ORPHAN_CHUNKS:-0}"
echo "  Empty Documents: ${EMPTY_DOCS:-0}"
echo "  Missing Embeddings: ${MISSING_EMBEDDINGS:-0}"

# Determine system status with specific recommendations
if [ "$NETWORK_ISSUES" -gt 0 ] || [ "$MODEL_LOADING_ISSUES" -gt 0 ] || [ "$PDF_PROCESSOR_ERRORS" -gt 100 ] || [ "${ORPHAN_CHUNKS:-0}" -gt 0 ] || [ "${MISSING_EMBEDDINGS:-0}" -gt 0 ]; then
    echo -e "\n${RED}🔴 SYSTEM STATUS: CRITICAL ISSUES - DO NOT PROCEED WITH DEVELOPMENT${NC}"
    echo -e "${RED}ACTION REQUIRED: Fix critical database and processing issues immediately${NC}"
    error "System has $CRITICAL_ISSUES critical issues that prevent proper operation"
    exit 1
elif [ "$WARNING_ISSUES" -gt 2 ] || [ "$DATABASE_ERRORS" -gt 2 ]; then
    echo -e "\n${YELLOW}🟡 SYSTEM STATUS: CAUTION - MONITOR CLOSELY${NC}"
    echo -e "${YELLOW}RECOMMENDATION: Address warning issues before major development work${NC}"
    warning "System has $WARNING_ISSUES warning issues"
    exit 2
else
    echo -e "\n${GREEN}🟢 SYSTEM STATUS: READY FOR DEVELOPMENT${NC}"
    success "All critical systems operational"
    exit 0
fi