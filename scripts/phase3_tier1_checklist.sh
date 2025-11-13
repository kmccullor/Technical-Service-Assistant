#!/bin/bash
# Phase 3 Tier 1 - Pre-Deployment Checklist

echo "════════════════════════════════════════════════════════════"
echo "  Phase 3 Tier 1 - Pre-Deployment Checklist"
echo "════════════════════════════════════════════════════════════"
echo

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Counters
CHECKS_PASSED=0
CHECKS_FAILED=0
WARNINGS=0

check_status() {
  if [ $1 -eq 0 ]; then
    echo -e "${GREEN}✓${NC} $2"
    ((CHECKS_PASSED++))
  else
    echo -e "${RED}✗${NC} $2"
    ((CHECKS_FAILED++))
  fi
}

warning() {
  echo -e "${YELLOW}⚠${NC} $1"
  ((WARNINGS++))
}

echo "=== CODE STRUCTURE CHECKS ==="
echo

# Check load_balancer.py exists
if [ -f "reranker/load_balancer.py" ]; then
  check_status 0 "Load balancer module exists"
  python -m py_compile reranker/load_balancer.py 2>/dev/null
  check_status $? "Load balancer syntax valid"
else
  check_status 1 "Load balancer module missing"
fi

# Check advanced_cache.py exists
if [ -f "reranker/advanced_cache.py" ]; then
  check_status 0 "Advanced cache module exists"
  python -m py_compile reranker/advanced_cache.py 2>/dev/null
  check_status $? "Advanced cache syntax valid"
else
  check_status 1 "Advanced cache module missing"
fi

# Check dashboards exist
echo
echo "=== GRAFANA DASHBOARDS ==="
echo
[ -f "monitoring/phase3_performance_dashboard.json" ] && check_status 0 "Performance dashboard exists" || check_status 1 "Performance dashboard missing"
[ -f "monitoring/phase3_health_dashboard.json" ] && check_status 0 "Health dashboard exists" || check_status 1 "Health dashboard missing"
[ -f "monitoring/phase3_business_dashboard.json" ] && check_status 0 "Business dashboard exists" || check_status 1 "Business dashboard missing"

# Check documentation
echo
echo "=== DOCUMENTATION ==="
echo
[ -f "PHASE3_TIER1_IMPLEMENTATION.md" ] && check_status 0 "Implementation guide exists" || check_status 1 "Implementation guide missing"
[ -f "PHASE3_TIER1_DEPLOYMENT.md" ] && check_status 0 "Deployment guide exists" || check_status 1 "Deployment guide missing"
[ -f "PHASE3_TIER1_COMPLETE.md" ] && check_status 0 "Completion summary exists" || check_status 1 "Completion summary missing"

# Check imports work
echo
echo "=== IMPORT VERIFICATION ==="
echo
python -c "from reranker.load_balancer import get_load_balancer, RequestType" 2>/dev/null
check_status $? "Load balancer imports work"

python -c "from reranker.advanced_cache import get_advanced_cache" 2>/dev/null
check_status $? "Advanced cache imports work"

# Check app.py has endpoints
echo
echo "=== API ENDPOINT VERIFICATION ==="
echo
grep -q "def load_balancer_stats" reranker/app.py && check_status 0 "load_balancer_stats endpoint defined" || check_status 1 "load_balancer_stats endpoint missing"
grep -q "def advanced_cache_stats" reranker/app.py && check_status 0 "advanced_cache_stats endpoint defined" || check_status 1 "advanced_cache_stats endpoint missing"

# Check rag_chat.py integration
echo
echo "=== RAG_CHAT INTEGRATION ==="
echo
grep -q "from reranker.load_balancer import" reranker/rag_chat.py && check_status 0 "Load balancer imported in rag_chat" || check_status 1 "Load balancer not imported in rag_chat"
grep -q "from reranker.advanced_cache import" reranker/rag_chat.py && check_status 0 "Advanced cache imported in rag_chat" || check_status 1 "Advanced cache not imported in rag_chat"
grep -q "self.load_balancer = get_load_balancer" reranker/rag_chat.py && check_status 0 "Load balancer initialized in RAGChatService" || check_status 1 "Load balancer not initialized"
grep -q "self.advanced_cache = get_advanced_cache" reranker/rag_chat.py && check_status 0 "Advanced cache initialized in RAGChatService" || check_status 1 "Advanced cache not initialized"

# Runtime checks
echo
echo "=== RUNTIME ENVIRONMENT ==="
echo

# Check Python version
python_version=$(python --version 2>&1 | awk '{print $2}')
check_status 0 "Python version: $python_version"

# Check required packages (may not be in local env, that's OK - they're in Docker)
echo -n "Checking required packages... "
python -c "import redis; import httpx; import pydantic" 2>/dev/null && {
  check_status 0 "Core dependencies available (local)"
} || {
  warning "Core dependencies not in local env (OK - they're in Docker)"
}

# Summary
echo
echo "════════════════════════════════════════════════════════════"
echo "                    SUMMARY"
echo "════════════════════════════════════════════════════════════"
echo -e "✓ Passed:  ${GREEN}$CHECKS_PASSED${NC}"
echo -e "✗ Failed:  ${RED}$CHECKS_FAILED${NC}"
if [ $WARNINGS -gt 0 ]; then
  echo -e "⚠ Warnings: ${YELLOW}$WARNINGS${NC}"
fi
echo

if [ $CHECKS_FAILED -eq 0 ]; then
  echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
  echo -e "${GREEN}✅  ALL CHECKS PASSED - READY FOR DEPLOYMENT${NC}"
  echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
  echo
  echo "Next steps:"
  echo "  1. Build reranker image:   docker compose build reranker"
  echo "  2. Deploy stack:           docker compose up -d"
  echo "  3. Verify health:          curl http://localhost:8008/health"
  echo "  4. Check metrics:          curl http://localhost:8008/api/load-balancer-stats"
  echo
  exit 0
else
  echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
  echo -e "${RED}❌  CHECKS FAILED - PLEASE RESOLVE ABOVE ISSUES${NC}"
  echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
  exit 1
fi
