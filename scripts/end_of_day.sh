#!/bin/bash
# End of Day Automation Script for Technical Service Assistant
# This script generates comprehensive end-of-day reports and system snapshots
# Designed to run from crontab at end of business day
# 
# Usage: ./scripts/end_of_day.sh [--no-git] [--no-backup]
# Crontab example: 0 17 * * 1-5 /path/to/Technical-Service-Assistant/scripts/end_of_day.sh

# Set script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs"
DATE_STAMP=$(date +%Y%m%d)
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

# Color definitions for output formatting (disabled in cron)
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    PURPLE='\033[0;35m'
    CYAN='\033[0;36m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    PURPLE=''
    CYAN=''
    NC=''
fi

# Configuration
BACKUP_DIR="$PROJECT_ROOT/backup/$(date '+%Y%m%d_%H%M%S')_end_of_day"
REPORT_FILE="$LOG_DIR/daily_report_${DATE_STAMP}.md"
EOD_LOG="$LOG_DIR/end_of_day_automation_$DATE_STAMP.log"

# Parse command line arguments
NO_GIT=false
NO_BACKUP=false
for arg in "$@"; do
    case $arg in
        --no-git) NO_GIT=true ;;
        --no-backup) NO_BACKUP=true ;;
    esac
done

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Helper functions
info() { echo -e "${BLUE}ℹ️  INFO: $1${NC}" | tee -a "$EOD_LOG"; }
success() { echo -e "${GREEN}✅ SUCCESS: $1${NC}" | tee -a "$EOD_LOG"; }
warning() { echo -e "${YELLOW}⚠️  WARNING: $1${NC}" | tee -a "$EOD_LOG"; }
error() { echo -e "${RED}❌ ERROR: $1${NC}" | tee -a "$EOD_LOG"; }
section() { echo -e "\n${PURPLE}=== $1 ===${NC}" | tee -a "$EOD_LOG"; }

# Log function for cron-friendly output
log_message() {
    echo "[$TIMESTAMP] $1" | tee -a "$EOD_LOG"
}

# Environment check function
check_environment() {
    cd "$PROJECT_ROOT" || { error "Cannot change to project root: $PROJECT_ROOT"; exit 1; }
    
    if [[ ! -f "docker-compose.yml" ]]; then
        error "Not in Technical Service Assistant project root"
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        error "Docker not available"
        exit 1
    fi
}

# Health check function for cron automation
run_automated_health_checks() {
    section "🔍 Automated Health Checks"
    
    local health_status="HEALTHY"
    local health_log="$LOG_DIR/health_check_$DATE_STAMP.log"
    
    echo "=== AUTOMATED HEALTH CHECK - $TIMESTAMP ===" > "$health_log"
    
    # Test reranker service
    if curl -sf http://localhost:8008/health > /dev/null 2>&1; then
        success "Reranker service responding"
        echo "✅ Reranker service: HEALTHY" >> "$health_log"
    else
        warning "Reranker service not responding"
        echo "❌ Reranker service: UNAVAILABLE" >> "$health_log"
        health_status="DEGRADED"
    fi
    
    # Test database
    if docker exec pgvector pg_isready -U postgres > /dev/null 2>&1; then
        success "PostgreSQL database healthy"
        echo "✅ PostgreSQL database: HEALTHY" >> "$health_log"
    else
        warning "PostgreSQL database issues"
        echo "❌ PostgreSQL database: UNAVAILABLE" >> "$health_log"
        health_status="DEGRADED"
    fi
    
    # Test Ollama instances
    local ollama_healthy=0
    for port in 11434 11435 11436 11437; do
        if curl -sf http://localhost:$port/api/tags > /dev/null 2>&1; then
            echo "✅ Ollama instance (port $port): HEALTHY" >> "$health_log"
            ((ollama_healthy++))
        else
            echo "❌ Ollama instance (port $port): UNAVAILABLE" >> "$health_log"
        fi
    done
    
    if [[ $ollama_healthy -lt 2 ]]; then
        health_status="CRITICAL"
        error "Only $ollama_healthy Ollama instances healthy"
    else
        success "$ollama_healthy Ollama instances healthy"
    fi
    
    echo "$health_status" > "$LOG_DIR/system_health_status.txt"
    return $([[ "$health_status" == "HEALTHY" ]] && echo 0 || echo 1)
}

# Performance validation for cron
run_automated_performance_tests() {
    section "⚡ Performance Validation"
    
    local perf_log="$LOG_DIR/performance_test_$DATE_STAMP.log"
    echo "=== AUTOMATED PERFORMANCE TEST - $TIMESTAMP ===" > "$perf_log"
    
    # Test RAG validation if available
    if [[ -f "rag_validation_framework.py" ]]; then
        info "Running RAG performance benchmark..."
        timeout 180 python rag_validation_framework.py --performance-benchmark >> "$perf_log" 2>&1
        if [[ $? -eq 0 ]]; then
            success "RAG performance test completed"
        else
            warning "RAG performance test failed or timed out"
        fi
    fi
    
    # Basic API response time
    if command -v curl &> /dev/null; then
        local response_time
        response_time=$(curl -w "%{time_total}" -s -o /dev/null http://localhost:8008/health 2>/dev/null || echo "failed")
        echo "API Response Time: ${response_time}s" >> "$perf_log"
        info "API response time: ${response_time}s"
    fi
}

# Send notifications if configured
send_eod_notification() {
    local status="$1"
    local summary="$2"
    
    # Slack/Teams webhook notification
    if [[ -n "${EOD_WEBHOOK_URL:-}" ]]; then
        curl -X POST "$EOD_WEBHOOK_URL" \
             -H "Content-Type: application/json" \
             -d "{\"text\":\"🤖 **Technical Service Assistant - End of Day Report**\\n**Status**: $status\\n**Summary**: $summary\\n**Time**: $(date)\\n**Reports**: View at logs/daily_report_$DATE_STAMP.md\"}" \
             >> "$EOD_LOG" 2>&1
        info "Notification sent to webhook"
    fi
    
    # Email notification with Python fallback
    if [[ -n "${EOD_EMAIL:-}" ]]; then
        # Try mailx/mail first
        if command -v mail &> /dev/null; then
            echo -e "Technical Service Assistant - End of Day Report\n\nStatus: $status\nSummary: $summary\nTime: $(date)\n\nDetailed report available at: logs/daily_report_$DATE_STAMP.md" | \
                mail -s "Technical Service Assistant - EOD Report ($status)" "$EOD_EMAIL"
            info "Email notification sent to $EOD_EMAIL (via mail command)"
        
        # Fallback to Python email script
        elif [[ -f "$PROJECT_ROOT/email_eod_report.py" ]]; then
            info "Using Python email script to send report..."
            if python "$PROJECT_ROOT/email_eod_report.py" "$EOD_EMAIL" "$REPORT_FILE" >> "$EOD_LOG" 2>&1; then
                info "Email report sent to $EOD_EMAIL (via Python script)"
            else
                warning "Failed to send email via Python script. Check $EOD_LOG for details."
            fi
        else
            warning "No email utility available. Install mailx or configure Python email script."
        fi
    fi
}

echo -e "${CYAN}🌅 End of Day Routine - $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo "Starting automated backup, commit, and reporting process..."

# Initialize report
mkdir -p "$LOG_DIR"
cat > "$REPORT_FILE" << EOF
# Daily Work Report - $(date '+%A, %B %d, %Y')

**Report Generated:** $(date '+%Y-%m-%d %H:%M:%S')  
**System:** Technical Service Assistant RAG Pipeline  
**Environment:** Development/Production Hybrid

---

EOF

section "📊 System Status Summary"

# Get current system metrics
CONTAINERS_RUNNING=$(docker ps --format "table {{.Names}}" | tail -n +2 | wc -l)
EXPECTED_CONTAINERS=$(grep -c 'container_name:' docker-compose.yml 2>/dev/null || echo 0)
TOTAL_DOCUMENTS=$(docker exec pgvector psql -U postgres -d vector_db -t -c "SELECT COUNT(*) FROM documents;" 2>/dev/null | xargs || echo "N/A")
TOTAL_CHUNKS=$(docker exec pgvector psql -U postgres -d vector_db -t -c "SELECT COUNT(*) FROM document_chunks;" 2>/dev/null | xargs || echo "N/A")
DISK_USAGE=$(df -h /home | tail -1 | awk '{print $5}')
MEMORY_USAGE=$(free | awk '/^Mem:/ {printf "%.1f", $3/$2 * 100}')%

# Monitoring snapshot (Prometheus + Alertmanager)
FIRING_ALERTS=$(curl -s --max-time 5 http://localhost:9091/api/v1/alerts 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin) if sys.stdin.read().strip() else {}; print(sum(1 for a in d.get('data',{}).get('alerts',[]) if a.get('state')=='firing'))" 2>/dev/null || echo "N/A")

FIRING_ALERT_NAMES=$(curl -s --max-time 5 http://localhost:9091/api/v1/alerts 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin) if sys.stdin.read().strip() else {}; names=[a.get('labels',{}).get('alertname') for a in d.get('data',{}).get('alerts',[]) if a.get('state')=='firing']; names=[n for n in names if n]; print(', '.join(names[:5]) if names else 'None')" 2>/dev/null || echo "N/A")

REFRESH_AGE=$(curl -s --max-time 5 "http://localhost:9091/api/v1/query?query=ingestion:last_refresh_age_seconds" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin) if sys.stdin.read().strip() else {}; r=d.get('data',{}).get('result',[]); print(int(float(r[0]['value'][1])) if r else 'N/A')" 2>/dev/null || echo "N/A")

DOCS_PROCESSED_24H=$(curl -s --max-time 5 "http://localhost:9091/api/v1/query?query=increase(docling_documents_processed_total[24h])" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin) if sys.stdin.read().strip() else {}; r=d.get('data',{}).get('result',[]); print(int(float(r[0]['value'][1])) if r else 0)" 2>/dev/null || echo "0")

cat >> "$REPORT_FILE" << EOF
## 🎯 System Health Overview

| Metric | Value | Status |
|--------|-------|--------|
| Docker Containers Running | $CONTAINERS_RUNNING / $EXPECTED_CONTAINERS | $( [ "$CONTAINERS_RUNNING" -ge "$((EXPECTED_CONTAINERS-1))" ] && echo "✅ Healthy" || echo "⚠️ Check" ) |
| Total Documents Indexed | $TOTAL_DOCUMENTS | ✅ Active |
| Total Document Chunks | $TOTAL_CHUNKS | ✅ Processed |
| Disk Usage | $DISK_USAGE | $(DISK_NUM=$(echo "$DISK_USAGE" | grep -o '[0-9]*' | head -1); [ "${DISK_NUM:-100}" -lt 85 ] && echo "✅ Normal" || echo "⚠️ High") |
| Memory Usage | $MEMORY_USAGE | $(MEM_NUM=$(echo "$MEMORY_USAGE" | grep -o '[0-9]*' | head -1); [ "${MEM_NUM:-100}" -lt 80 ] && echo "✅ Normal" || echo "⚠️ High") |
| Firing Alerts | $FIRING_ALERTS | $( [ "$FIRING_ALERTS" = "0" ] && echo "✅ None" || echo "⚠️ Attention" ) |
| Alerts (Top) | $FIRING_ALERT_NAMES | — |
| Docs Proc (24h) | $DOCS_PROCESSED_24H | $( [ "$DOCS_PROCESSED_24H" -gt 0 ] && echo "✅ Active" || echo "ℹ️ Idle" ) |
| Perf Refresh Age (s) | $REFRESH_AGE | $( if [[ "$REFRESH_AGE" =~ ^[0-9]+$ ]] && [ "$REFRESH_AGE" -lt 900 ]; then echo "✅ Fresh"; else echo "⚠️ Stale"; fi ) |

EOF

info "System status captured"

section "📈 Daily Activity Analysis"

# Analyze git changes
GIT_CHANGES=$(git status --porcelain 2>/dev/null | wc -l)
GIT_COMMITS_TODAY=$(git log --since="$(date '+%Y-%m-%d 00:00:00')" --oneline 2>/dev/null | wc -l)
MODIFIED_FILES=$(git status --porcelain 2>/dev/null | head -10)

cat >> "$REPORT_FILE" << EOF
## 📝 Development Activity

### Git Repository Status
- **Uncommitted Changes:** $GIT_CHANGES files
- **Commits Today:** $GIT_COMMITS_TODAY commits
- **Repository Status:** $([ "$GIT_CHANGES" -eq 0 ] && echo "Clean ✅" || echo "Has Changes ⚠️")

EOF

if [ "$GIT_CHANGES" -gt 0 ]; then
    cat >> "$REPORT_FILE" << EOF
### Modified Files (Top 10)
\`\`\`
$MODIFIED_FILES
\`\`\`

EOF
fi

# Analyze recent commits
if [ "$GIT_COMMITS_TODAY" -gt 0 ]; then
    RECENT_COMMITS=$(git log --since="$(date '+%Y-%m-%d 00:00:00')" --pretty=format:"- %h: %s (%an)" 2>/dev/null)
    cat >> "$REPORT_FILE" << EOF
### Today's Commits
$RECENT_COMMITS

EOF
fi

section "🔍 Performance & Quality Metrics"

# Get performance metrics
API_RESPONSE_TIME=$(timeout 10 curl -w "%{time_total}" -s -o /dev/null http://localhost:8008/health 2>/dev/null || echo "timeout")
FAILED_EMBEDDINGS_TODAY=$(docker logs pdf_processor --since="24h" 2>/dev/null | grep -c "Failed to get embedding" || echo "0")
LOG_ERRORS_TODAY=$(find logs/ -name "*.log" -mtime -1 -exec grep -l "ERROR\|FATAL" {} \; 2>/dev/null | wc -l)

cat >> "$REPORT_FILE" << EOF
## ⚡ Performance Metrics

| Metric | Value | Trend |
|--------|-------|-------|
| API Response Time | ${API_RESPONSE_TIME}s | $(if [ "${API_RESPONSE_TIME}" != "timeout" ] && [ "${API_RESPONSE_TIME}" != "" ]; then echo "$(echo "$API_RESPONSE_TIME < 1.0" | bc -l 2>/dev/null || echo "1")" | grep -q "^1$" && echo "✅ Fast" || echo "⚠️ Slow"; else echo "⚠️ Slow"; fi) |
| Failed Embeddings (24h) | $FAILED_EMBEDDINGS_TODAY | $([ "${FAILED_EMBEDDINGS_TODAY:-0}" -lt 10 ] 2>/dev/null && echo "✅ Low" || echo "⚠️ High") |
| Log Files with Errors | $LOG_ERRORS_TODAY | $([ "${LOG_ERRORS_TODAY:-1}" -eq 0 ] 2>/dev/null && echo "✅ Clean" || echo "⚠️ Issues") |

EOF

section "💾 Creating Backup"

# Create backup directory
mkdir -p "$BACKUP_DIR"
info "Creating backup in $BACKUP_DIR"

# Backup critical files and directories
BACKUP_TARGETS=(
    "config.py"
    "docker-compose.yml" 
    "requirements.txt"
    "requirements-dev.txt"
    "Makefile"
    "scripts/"
    "reranker/"
    "pdf_processor/"
    "frontend/"
    "docs/"
    ".env"
)

BACKUP_SUCCESS=0
BACKUP_FAILED=0

for target in "${BACKUP_TARGETS[@]}"; do
    if [ -e "$target" ]; then
        if cp -r "$target" "$BACKUP_DIR/" 2>/dev/null; then
            ((BACKUP_SUCCESS++))
        else
            ((BACKUP_FAILED++))
            warning "Failed to backup $target"
        fi
    fi
done

# Backup database schema
docker exec pgvector pg_dump -U postgres -d vector_db --schema-only > "$BACKUP_DIR/database_schema.sql" 2>/dev/null && ((BACKUP_SUCCESS++)) || ((BACKUP_FAILED++))

# Create backup summary
BACKUP_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
success "Backup created: $BACKUP_SUCCESS items, $BACKUP_SIZE total size"

cat >> "$REPORT_FILE" << EOF
## 💾 Backup Summary

- **Backup Location:** \`$BACKUP_DIR\`
- **Items Backed Up:** $BACKUP_SUCCESS successful, $BACKUP_FAILED failed
- **Backup Size:** $BACKUP_SIZE
- **Database Schema:** $([ -f "$BACKUP_DIR/database_schema.sql" ] && echo "✅ Included" || echo "❌ Failed")

EOF

section "📋 Database Health Check"

# Run database integrity check
DB_CHECK_OUTPUT=$(cd /home/kmccullor/Projects/Technical-Service-Assistant && make check-db 2>/dev/null)
ORPHAN_CHUNKS=$(echo "$DB_CHECK_OUTPUT" | grep "Orphan Chunks" | awk '{print $3}' || echo "0")
EMPTY_DOCS=$(echo "$DB_CHECK_OUTPUT" | grep "Empty Documents" | awk '{print $3}' || echo "0")
MISSING_EMBEDDINGS=$(echo "$DB_CHECK_OUTPUT" | grep "Missing Embeddings" | awk '{print $3}' || echo "0")

cat >> "$REPORT_FILE" << EOF
## 🗄️ Database Integrity Status

| Check | Count | Status |
|-------|-------|--------|
| Orphan Chunks | $ORPHAN_CHUNKS | $(ORPHAN_NUM=$(echo "$ORPHAN_CHUNKS" | grep -o '[0-9]*' | head -1 2>/dev/null || echo "1"); [ "${ORPHAN_NUM:-1}" -eq 0 ] 2>/dev/null && echo "✅ Clean" || echo "❌ Needs Cleanup") |
| Empty Documents | $EMPTY_DOCS | $(EMPTY_NUM=$(echo "$EMPTY_DOCS" | grep -o '[0-9]*' | head -1 2>/dev/null || echo "1"); [ "${EMPTY_NUM:-1}" -eq 0 ] 2>/dev/null && echo "✅ Clean" || echo "⚠️ Needs Review") |
| Missing Embeddings | $MISSING_EMBEDDINGS | $([ "${MISSING_EMBEDDINGS:-1}" -eq 0 ] 2>/dev/null && echo "✅ Complete" || echo "❌ Needs Processing") |

EOF

section "🔄 Git Operations"

# Auto-commit if there are changes
if [ "$GIT_CHANGES" -gt 0 ]; then
    info "Committing changes..."
    
    # Add all changes
    git add . 2>/dev/null
    
    # Create commit message with summary
    COMMIT_MSG="End of day commit - $(date '+%Y-%m-%d')

- Modified files: $GIT_CHANGES
- System status: $CONTAINERS_RUNNING containers running
- Database: $TOTAL_DOCUMENTS documents, $TOTAL_CHUNKS chunks
- Backup created: $BACKUP_DIR"
    
    if git commit -m "$COMMIT_MSG" 2>/dev/null; then
        COMMIT_HASH=$(git rev-parse --short HEAD)
        success "Changes committed: $COMMIT_HASH"
        
        cat >> "$REPORT_FILE" << EOF
## 🔄 Git Operations

- **Auto-commit Status:** ✅ Successful
- **Commit Hash:** \`$COMMIT_HASH\`
- **Files Committed:** $GIT_CHANGES files
- **Commit Message:** End of day automated commit

EOF
    else
        error "Failed to commit changes"
        cat >> "$REPORT_FILE" << EOF
## 🔄 Git Operations

- **Auto-commit Status:** ❌ Failed
- **Files Pending:** $GIT_CHANGES uncommitted files
- **Action Required:** Manual commit needed

EOF
    fi
else
    success "No changes to commit"
    cat >> "$REPORT_FILE" << EOF
## 🔄 Git Operations

- **Repository Status:** ✅ Clean (no changes to commit)
- **Last Commit:** $(git log -1 --pretty=format:"%h: %s (%cr)" 2>/dev/null || echo "Unable to retrieve")

EOF
fi

section "📊 Resource Usage Trends"

# Analyze log file growth
LOG_SIZE_TODAY=$(find logs/ -name "*.log" -mtime -1 -exec du -ch {} + 2>/dev/null | tail -1 | cut -f1 || echo "0")
LOG_FILE_COUNT=$(find logs/ -name "*.log" | wc -l)

# Docker system usage
DOCKER_IMAGES=$(docker images --format "table {{.Repository}}" | tail -n +2 | wc -l)
DOCKER_VOLUMES=$(docker volume ls -q | wc -l)

cat >> "$REPORT_FILE" << EOF
## 📈 Resource Usage Trends

### Storage & Logs
- **Log Files Generated Today:** $LOG_SIZE_TODAY
- **Total Log Files:** $LOG_FILE_COUNT
- **Docker Images:** $DOCKER_IMAGES
- **Docker Volumes:** $DOCKER_VOLUMES

### System Resources
- **Peak Memory Usage:** $MEMORY_USAGE (current)
- **Disk Space Used:** $DISK_USAGE
- **Active Containers:** $CONTAINERS_RUNNING/9 expected

EOF

section "🎯 Daily Accomplishments & Issues"

# Analyze recent work based on git and logs
FEATURES_ADDED=$(git log --since="$(date '+%Y-%m-%d 00:00:00')" --grep="feat\|add\|implement" --oneline 2>/dev/null | wc -l)
BUGS_FIXED=$(git log --since="$(date '+%Y-%m-%d 00:00:00')" --grep="fix\|bug\|resolve" --oneline 2>/dev/null | wc -l)
DOCS_UPDATED=$(git log --since="$(date '+%Y-%m-%d 00:00:00')" --name-only --pretty=format: 2>/dev/null | grep -E "\\.md$|\\.txt$" | sort | uniq | wc -l)
# Documentation statistics
DOC_FILE_COUNT=$(find . -maxdepth 6 -type f -name '*.md' 2>/dev/null | wc -l)
DOC_RECENT_CHANGED=$(git log --since="$(date -d '-7 days' '+%Y-%m-%d')" --name-only --pretty=format: 2>/dev/null | grep -E '\\.md$' | sort | uniq | wc -l)
TOP_DOC_CHANGES=$(git log --since="$(date '+%Y-%m-%d 00:00:00')" --name-only --pretty=format: 2>/dev/null | grep -E '\\.md$' | sort | uniq | head -5)

cat >> "$REPORT_FILE" << EOF
## 🎯 Daily Accomplishments

### Development Activity
- **Features/Enhancements:** $FEATURES_ADDED commits
- **Bug Fixes:** $BUGS_FIXED commits  
- **Documentation Updates (files today):** $DOCS_UPDATED
- **Markdown Files (total):** $DOC_FILE_COUNT
- **Markdown Files Changed (7d):** $DOC_RECENT_CHANGED
- **Top Changed Docs Today:** $( [ -n "$TOP_DOC_CHANGES" ] && echo "$TOP_DOC_CHANGES" | tr '\n' ',' | sed 's/,$//' || echo 'None')
- **Total Development Activity:** $GIT_COMMITS_TODAY commits

### System Operations
- **Backup Operations:** ✅ Completed ($BACKUP_SIZE)
- **Database Maintenance:** $([ "${ORPHAN_CHUNKS:-1}" -eq 0 ] 2>/dev/null && [ "${EMPTY_DOCS:-1}" -eq 0 ] 2>/dev/null && [ "${MISSING_EMBEDDINGS:-1}" -eq 0 ] 2>/dev/null && echo "✅ Clean" || echo "⚠️ Issues Found")
- **System Health:** $([ "$CONTAINERS_RUNNING" -ge 8 ] && echo "✅ Healthy" || echo "⚠️ Degraded")

EOF

# Issues and recommendations
cat >> "$REPORT_FILE" << EOF
## ⚠️ Issues & Recommendations

EOF

if [ "${FAILED_EMBEDDINGS_TODAY:-0}" -gt 50 ] 2>/dev/null; then
    cat >> "$REPORT_FILE" << EOF
- **High Embedding Failures:** $FAILED_EMBEDDINGS_TODAY failures detected today - investigate Ollama instance health
EOF
fi

if [ "${DISK_USAGE%\%}" -gt 85 ] 2>/dev/null; then
    cat >> "$REPORT_FILE" << EOF
- **High Disk Usage:** $DISK_USAGE - consider running \`make cleanup\` or archiving old data
EOF
fi

if [ "$GIT_CHANGES" -gt 20 ]; then
    cat >> "$REPORT_FILE" << EOF
- **Many Uncommitted Changes:** $GIT_CHANGES files - consider more frequent commits
EOF
fi

if [ "$LOG_ERRORS_TODAY" -gt 5 ]; then
    cat >> "$REPORT_FILE" << EOF
- **Error Log Activity:** $LOG_ERRORS_TODAY log files contain errors - review with \`make check-logs\`
EOF
fi

if [ "$FIRING_ALERTS" != "0" ] && [ "$FIRING_ALERTS" != "N/A" ]; then
    cat >> "$REPORT_FILE" << EOF
- **Active Alerts:** $FIRING_ALERTS firing alerts require attention - check Prometheus/Alertmanager
EOF
fi

if [[ "$REFRESH_AGE" =~ ^[0-9]+$ ]] && [ "$REFRESH_AGE" -gt 900 ]; then
    cat >> "$REPORT_FILE" << EOF
- **Stale Performance Monitor:** Refresh age $REFRESH_AGE seconds - investigate exporter health
EOF
fi

# Add positive notes
cat >> "$REPORT_FILE" << EOF

## 🎉 Positive Highlights

EOF

if [ "$API_RESPONSE_TIME" != "timeout" ] && [ "$(echo "$API_RESPONSE_TIME < 0.5" | bc -l 2>/dev/null || echo "0")" -eq 1 ]; then
    cat >> "$REPORT_FILE" << EOF
- **Excellent API Performance:** ${API_RESPONSE_TIME}s response time
EOF
fi

if [ "${ORPHAN_CHUNKS:-1}" -eq 0 ] 2>/dev/null && [ "${EMPTY_DOCS:-1}" -eq 0 ] 2>/dev/null && [ "${MISSING_EMBEDDINGS:-1}" -eq 0 ] 2>/dev/null; then
    cat >> "$REPORT_FILE" << EOF
- **Perfect Database Integrity:** No orphans, empty documents, or missing embeddings
EOF
fi

if [ "${CONTAINERS_RUNNING:-0}" -eq 9 ] 2>/dev/null; then
    cat >> "$REPORT_FILE" << EOF
- **Full System Health:** All $CONTAINERS_RUNNING containers running healthy
EOF
fi

# Tomorrow's checklist
cat >> "$REPORT_FILE" << EOF

---

## 📋 Tomorrow's Checklist

- [ ] Run morning health check: \`make morning\`
- [ ] Review any pending issues identified above
- [ ] Continue development work on current features
$([ "$GIT_CHANGES" -gt 0 ] && echo "- [ ] Address any remaining uncommitted changes")
$([ "$FAILED_EMBEDDINGS_TODAY" -gt 20 ] && echo "- [ ] Investigate embedding generation issues")
$([ "${DISK_USAGE%\%}" -gt 80 ] && echo "- [ ] Consider system cleanup: \`make cleanup\`")

**Generated by:** End of Day Automation Script  
**Next Report:** $(date -d '+1 day' '+%Y-%m-%d')
EOF

# CRON-FRIENDLY AUTOMATION SECTION
# This section runs when called from crontab

# Main automated execution function
run_automated_eod() {
    log_message "🌅 Starting automated End of Day process..."
    
    # Change to project directory
    check_environment
    
    # Run automated health checks
    run_automated_health_checks
    local health_exit_code=$?
    
    # Run performance tests
    run_automated_performance_tests
    
    # Generate comprehensive daily report
    generate_automated_report
    
    # Create system snapshot
    create_system_snapshot
    
    # Cleanup old logs (keep last 30 days)
    cleanup_old_logs
    
    # Calculate summary metrics
    local total_containers=$(docker ps -q | wc -l)
    local healthy_services=$(grep -c "✅" "$LOG_DIR/health_check_$DATE_STAMP.log" 2>/dev/null || echo "0")
    local system_status
    
    if [[ $health_exit_code -eq 0 && $healthy_services -gt 5 ]]; then
        system_status="HEALTHY"
        status_emoji="✅"
    elif [[ $healthy_services -gt 3 ]]; then
        system_status="DEGRADED"
        status_emoji="⚠️"
    else
        system_status="CRITICAL"
        status_emoji="❌"
    fi
    
    # Send notifications
    send_eod_notification "$system_status" "$healthy_services services healthy, $total_containers containers running"
    
    log_message "$status_emoji Automated EOD completed - Status: $system_status"
    
    # Final summary for cron logs
    echo ""
    echo "🎯 AUTOMATED END OF DAY SUMMARY:"
    echo "   Status: $status_emoji $system_status"
    echo "   Containers: $total_containers running"
    echo "   Healthy services: $healthy_services"
    echo "   Reports: $LOG_DIR/daily_report_$DATE_STAMP.md"
    echo "   Logs: $EOD_LOG"
    echo ""
    
    return $([[ "$system_status" == "HEALTHY" ]] && echo 0 || echo 1)
}

# Generate comprehensive automated report
generate_automated_report() {
    log_message "📊 Generating automated daily report..."
    
    cat > "$REPORT_FILE" << EOF
# 🌅 Automated End of Day Report - $(date +"%B %d, %Y")

**Report Generated**: $(date +"%B %d, %Y at %I:%M %p %Z")  
**System Status**: $(docker ps -q | wc -l) containers running  
**Automation**: Generated via crontab scheduled task

---

## 📊 **System Health Summary**

### **Container Status**
$(docker ps --format "- **{{.Names}}**: {{.Status}} {{.Health}}" 2>/dev/null)

### **Resource Utilization**
\`\`\`
$(df -h | grep -E "/$|/var")
$(free -h)
\`\`\`

### **Database Status**
$(if ls "$PROJECT_ROOT"/*.db &> /dev/null; then ls -lh "$PROJECT_ROOT"/*.db | awk '{print "- " $9 ": " $5}'; else echo "- No validation databases found"; fi)

---

## 🔍 **Health Check Results**

$(if [[ -f "$LOG_DIR/health_check_$DATE_STAMP.log" ]]; then cat "$LOG_DIR/health_check_$DATE_STAMP.log" | sed 's/^/- /'; else echo "- Health check not completed"; fi)

---

## ⚡ **Performance Summary**

$(if [[ -f "$LOG_DIR/performance_test_$DATE_STAMP.log" ]]; then echo "Performance tests executed - see performance_test_$DATE_STAMP.log for details"; else echo "Performance tests not completed"; fi)

---

## 📝 **Log Files Generated**
- End of day automation: \`end_of_day_automation_$DATE_STAMP.log\`
- Health check results: \`health_check_$DATE_STAMP.log\`
- Performance test results: \`performance_test_$DATE_STAMP.log\`
- Daily summary: \`daily_report_$DATE_STAMP.md\`
- System snapshot: \`system_snapshot_$DATE_STAMP.json\`

---

## 🎯 **Action Items**
- Review any failed health checks
- Monitor performance trends
- Check container logs for any issues
- Verify backup and monitoring systems

---

**Next automated report**: Tomorrow at scheduled time  
**Manual reports**: Run \`./scripts/end_of_day.sh\` anytime  
**System monitoring**: Available at http://localhost:3001 (Grafana)

EOF

    log_message "✅ Automated daily report generated: $REPORT_FILE"
}

# Create system snapshot
create_system_snapshot() {
    log_message "📸 Creating system snapshot..."
    
    local snapshot_file="$LOG_DIR/system_snapshot_$DATE_STAMP.json"
    
    cat > "$snapshot_file" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "date": "$DATE_STAMP",
  "system": {
    "hostname": "$(hostname)",
    "uptime": "$(uptime -p)",
    "load_average": "$(uptime | awk -F'load average:' '{print $2}')"
  },
  "containers": {
    "total_running": $(docker ps -q | wc -l),
    "total_all": $(docker ps -aq | wc -l),
    "services": [
$(docker ps --format '      {"name": "{{.Names}}", "status": "{{.Status}}", "health": "{{.Health}}"},' | sed '$s/,$//')
    ]
  },
  "storage": {
    "databases": [
$(if ls "$PROJECT_ROOT"/*.db &> /dev/null; then ls -l "$PROJECT_ROOT"/*.db | awk '{print "      {\"name\": \"" $9 "\", \"size\": \"" $5 "\", \"modified\": \"" $6 " " $7 " " $8 "\"},"}' | sed '$s/,$//'; else echo '      {"note": "No databases found"}'; fi)
    ]
  },
  "logs": {
    "total_size": "$(du -sh "$LOG_DIR" 2>/dev/null | cut -f1)",
    "file_count": $(find "$LOG_DIR" -type f | wc -l)
  }
}
EOF

    log_message "✅ System snapshot saved: $snapshot_file"
}

# Cleanup old logs (keep last 30 days)
cleanup_old_logs() {
    log_message "🧹 Cleaning up old log files..."
    
    find "$LOG_DIR" -name "*.log" -type f -mtime +30 -delete 2>/dev/null
    find "$LOG_DIR" -name "*.md" -type f -mtime +30 -delete 2>/dev/null
    find "$LOG_DIR" -name "*.json" -type f -mtime +30 -delete 2>/dev/null
    
    log_message "✅ Log cleanup completed"
}

# Main execution logic
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Check if running in cron environment (no terminal)
    if [[ ! -t 1 ]]; then
        # Running from cron - use automated mode
        run_automated_eod
        exit $?
    else
        # Running interactively - check for automation flag
        if [[ "$1" == "--automated" ]] || [[ "$1" == "--cron" ]]; then
            run_automated_eod
            exit $?
        else
            # Original interactive mode continues below...
            echo -e "${CYAN}🌅 End of Day Routine - $(date '+%Y-%m-%d %H:%M:%S')${NC}"
            echo "For automated/cron mode, use: $0 --automated"
            echo "Starting interactive mode..."
        fi
    fi
fi

# Original interactive end-of-day routine continues here...
# (The existing interactive code remains for manual execution)

# Final summary for interactive mode
if [[ -t 1 ]]; then
    section "📋 End of Day Summary"
    
    success "Daily report generated: $REPORT_FILE"
    if [[ "$NO_BACKUP" == false ]]; then
        success "Backup completed: $BACKUP_DIR"
    fi
    
    echo -e "\n${GREEN}🎉 End of day routine completed successfully!${NC}"
    echo -e "${BLUE}📖 Full report available at: $REPORT_FILE${NC}"
    echo -e "\n${CYAN}Have a great evening! 🌙${NC}"
fi