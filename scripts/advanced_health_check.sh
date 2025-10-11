#!/bin/bash

# Advanced System Health Monitor
# Provides detailed system health analysis beyond daily checklist

# Color definitions for output formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== 🔍 Advanced System Health Analysis ===${NC}"
echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Detailed Performance Analysis
echo -e "${BLUE}=== ⚡ Detailed Performance Analysis ===${NC}"

# Database query performance
echo "📊 Database Query Performance:"
SLOW_QUERIES=$(docker exec pgvector psql -U postgres -d vector_db -t -c "
SELECT COUNT(*) FROM pg_stat_statements 
WHERE mean_time > 1000 AND calls > 10;" 2>/dev/null | xargs || echo "0")
echo "  Slow queries (>1s, >10 calls): $SLOW_QUERIES"

# Vector search performance
echo "🔍 Vector Search Performance:"
API_URL="${RERANKER_URL:-http://localhost:8008}"
VECTOR_SEARCH_TIME=$(timeout 15 curl -X POST "${API_URL%/}/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "performance test query", "passages": ["test passage"], "k": 5}' \
  -w "%{time_total}" -s -o /dev/null 2>/dev/null || echo "timeout")
echo "  Vector search response time: ${VECTOR_SEARCH_TIME}s"

# System load analysis
echo "💻 System Load Analysis:"
LOAD_1MIN=$(uptime | awk -F'load average:' '{print $2}' | awk -F, '{print $1}' | xargs)
LOAD_5MIN=$(uptime | awk -F'load average:' '{print $2}' | awk -F, '{print $2}' | xargs)
LOAD_15MIN=$(uptime | awk -F'load average:' '{print $2}' | awk -F, '{print $3}' | xargs)
echo "  Load averages: 1min=$LOAD_1MIN, 5min=$LOAD_5MIN, 15min=$LOAD_15MIN"

# Data Quality Deep Dive
echo -e "\n${BLUE}=== 📈 Data Quality Deep Dive ===${NC}"

# Embedding quality check
echo "🧠 Embedding Quality Analysis:"
NULL_EMBEDDINGS=$(docker exec pgvector psql -U postgres -d vector_db -t -c "
SELECT COUNT(*) FROM document_chunks WHERE embedding IS NULL;" 2>/dev/null | xargs)
EMPTY_CONTENT=$(docker exec pgvector psql -U postgres -d vector_db -t -c "
SELECT COUNT(*) FROM document_chunks WHERE LENGTH(content) < 10;" 2>/dev/null | xargs)
echo "  Null embeddings: $NULL_EMBEDDINGS"
echo "  Very short content chunks: $EMPTY_CONTENT"

# Document processing trends
echo "📄 Document Processing Trends:"
RECENT_DOCS=$(docker exec pgvector psql -U postgres -d vector_db -t -c "
SELECT COUNT(*) FROM documents WHERE created_at > NOW() - INTERVAL '24 hours';" 2>/dev/null | xargs || echo "0")
FAILED_CHUNKS=$(docker logs pdf_processor --since="24h" 2>/dev/null | grep -c "Failed to get embedding" || echo "0")
echo "  Documents added (24h): $RECENT_DOCS"
echo "  Failed embedding attempts (24h): $FAILED_CHUNKS"

# Advanced Security Analysis
echo -e "\n${BLUE}=== 🛡️ Advanced Security Analysis ===${NC}"

# Network security
echo "🌐 Network Security Status:"
LISTENING_PORTS=$(ss -tuln | grep LISTEN | wc -l)
EXTERNAL_CONNECTIONS=$(ss -tun | grep -v '127.0.0.1\|::1' | wc -l)
echo "  Listening ports: $LISTENING_PORTS"
echo "  External connections: $EXTERNAL_CONNECTIONS"

# File system security
echo "📁 File System Security:"
WORLD_WRITABLE=$(find /home/kmccullor/Projects/Technical-Service-Assistant -type f -perm -002 2>/dev/null | wc -l)
RECENT_MODIFICATIONS=$(find /home/kmccullor/Projects/Technical-Service-Assistant -type f -mtime -1 -not -path "*/logs/*" -not -path "*/.git/*" | wc -l)
echo "  World-writable files: $WORLD_WRITABLE"
echo "  Files modified (24h): $RECENT_MODIFICATIONS"

# Infrastructure Health
echo -e "\n${BLUE}=== 🏗️ Infrastructure Health ===${NC}"

# Storage analysis
echo "💾 Storage Analysis:"
DISK_USAGE=$(df -h /home | tail -1 | awk '{print $5}' | sed 's/%//')
INODE_USAGE=$(df -i /home | tail -1 | awk '{print $5}' | sed 's/%//')
echo "  Disk usage: ${DISK_USAGE}%"
echo "  Inode usage: ${INODE_USAGE}%"

# Docker health deep dive
echo "🐳 Docker Health Deep Dive:"
if command -v docker >/dev/null 2>&1; then
    RUNNING_CONTAINERS=$(docker ps --format "table {{.Names}}" | tail -n +2 | wc -l)
    UNHEALTHY_CONTAINERS=$(docker ps --filter "health=unhealthy" --format "table {{.Names}}" | tail -n +2 | wc -l)
    IMAGE_VULNERABILITIES=$(docker scout quickview 2>/dev/null | grep -c "vulnerabilities" || echo "scout unavailable")
    echo "  Running containers: $RUNNING_CONTAINERS"
    echo "  Unhealthy containers: $UNHEALTHY_CONTAINERS"
    echo "  Security scan: $IMAGE_VULNERABILITIES"
fi

# Service dependency health
echo "🔗 Service Dependency Health:"
REDIS_LATENCY=$(timeout 5 redis-cli -h localhost -p 6379 ping 2>/dev/null | grep -o PONG | wc -l || echo "0")
DB_CONNECTION_TIME=$(timeout 10 docker exec pgvector psql -U postgres -d vector_db -c "SELECT 1;" 2>/dev/null | grep -c "1 row" || echo "0")
echo "  Redis connectivity: $([ "$REDIS_LATENCY" -eq 1 ] && echo "✅ OK" || echo "❌ FAILED")"
echo "  Database connectivity: $([ "$DB_CONNECTION_TIME" -eq 1 ] && echo "✅ OK" || echo "❌ FAILED")"

# Recommendations
echo -e "\n${BLUE}=== 💡 Health Recommendations ===${NC}"

# Performance recommendations
if [ "$(echo "$LOAD_1MIN > 4.0" | bc -l 2>/dev/null || echo "0")" -eq 1 ]; then
    echo "⚠️  High system load detected - consider resource scaling"
fi

if [ "$FAILED_CHUNKS" -gt 50 ]; then
    echo "⚠️  High embedding failure rate - check Ollama instance health"
fi

if [ "$DISK_USAGE" -gt 85 ]; then
    echo "⚠️  High disk usage - run 'make cleanup' or archive old data"
fi

if [ "$WORLD_WRITABLE" -gt 0 ]; then
    echo "🔒 Security: Found $WORLD_WRITABLE world-writable files - review permissions"
fi

if [ "$UNHEALTHY_CONTAINERS" -gt 0 ]; then
    echo "🐳 Docker: $UNHEALTHY_CONTAINERS unhealthy containers detected"
fi

echo -e "\n${GREEN}✅ Advanced health analysis complete${NC}"