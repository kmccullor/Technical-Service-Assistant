#!/bin/bash

# Compare Docker Compose Services vs Running Containers
# This script validates that all defined services are actually running

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get expected services from docker-compose.yml
mapfile -t EXPECTED_SERVICES < <(grep -E "container_name:" docker-compose.yml | awk '{print $2}' | sort)

# Get running containers
mapfile -t RUNNING_CONTAINERS < <(docker ps --format "{{.Names}}" | sort)

# Get all containers (including stopped)
mapfile -t ALL_CONTAINERS < <(docker ps -a --format "{{.Names}}" | sort)

echo -e "${BLUE}📋 Expected Services (from docker-compose.yml):${NC}"
printf '%s\n' "${EXPECTED_SERVICES[@]}" | sed 's/^/  - /'

echo -e "\n${GREEN}✅ Currently Running:${NC}"
if [ ${#RUNNING_CONTAINERS[@]} -eq 0 ]; then
    echo "  - No containers running"
else
    printf '%s\n' "${RUNNING_CONTAINERS[@]}" | sed 's/^/  - /'
fi

echo -e "\n${YELLOW}📊 Service Status Comparison:${NC}"

MISSING_SERVICES=()
RUNNING_COUNT=0
TOTAL_EXPECTED=${#EXPECTED_SERVICES[@]}

for service in "${EXPECTED_SERVICES[@]}"; do
    # Clean service name (remove any extra characters)
    clean_service=$(echo "$service" | tr -d ' \t\r\n')

    # Check if container is running
    if docker ps --filter "name=^${clean_service}$" --filter "status=running" -q | grep -q .; then
        echo -e "  ✅ ${GREEN}${clean_service}${NC} - Running"
        ((RUNNING_COUNT++))
    # Check if container exists but is stopped
    elif docker ps -a --filter "name=^${clean_service}$" -q | grep -q .; then
        echo -e "  🟡 ${YELLOW}${clean_service}${NC} - Stopped (exists but not running)"
        MISSING_SERVICES+=("$clean_service")
    else
        echo -e "  ❌ ${RED}${clean_service}${NC} - Not found"
        MISSING_SERVICES+=("$clean_service")
    fi
done

echo -e "\n${BLUE}📈 Summary:${NC}"
echo "  Expected Services: $TOTAL_EXPECTED"
echo "  Running Services: $RUNNING_COUNT"
echo "  Missing/Stopped: ${#MISSING_SERVICES[@]}"

# Health percentage
HEALTH_PERCENT=$((RUNNING_COUNT * 100 / TOTAL_EXPECTED))
if [ $HEALTH_PERCENT -eq 100 ]; then
    echo -e "  ${GREEN}🟢 System Health: ${HEALTH_PERCENT}% - All services running${NC}"
elif [ $HEALTH_PERCENT -ge 80 ]; then
    echo -e "  ${YELLOW}🟡 System Health: ${HEALTH_PERCENT}% - Minor issues${NC}"
else
    echo -e "  ${RED}🔴 System Health: ${HEALTH_PERCENT}% - Critical issues${NC}"
fi

# Show services that need attention
if [ ${#MISSING_SERVICES[@]} -gt 0 ]; then
    echo -e "\n${RED}🚨 Services needing attention:${NC}"
    for service in "${MISSING_SERVICES[@]}"; do
        echo "  - $service"
    done

    echo -e "\n${BLUE}💡 Quick fix:${NC}"
    echo "  docker compose up -d"
    echo "  # Or start specific services:"
    printf '  docker compose start %s\n' "${MISSING_SERVICES[@]}"
fi

# Extra containers not in compose file
EXTRA_CONTAINERS=()
for container in "${RUNNING_CONTAINERS[@]}"; do
    if [[ ! " ${EXPECTED_SERVICES[*]} " =~ " ${container} " ]]; then
        EXTRA_CONTAINERS+=("$container")
    fi
done

if [ ${#EXTRA_CONTAINERS[@]} -gt 0 ]; then
    echo -e "\n${YELLOW}⚠️  Extra containers running (not in docker-compose.yml):${NC}"
    printf '%s\n' "${EXTRA_CONTAINERS[@]}" | sed 's/^/  - /'
fi

# Exit code based on health
if [ $HEALTH_PERCENT -eq 100 ]; then
    exit 0
elif [ $HEALTH_PERCENT -ge 80 ]; then
    exit 1
else
    exit 2
fi
