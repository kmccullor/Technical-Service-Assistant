#!/bin/bash

# Enhanced Ollama health check script
# Reports: server:idle, server:<model>, server:starting, server:loading

set -e

OLLAMA_HOST="http://localhost:11434"

# Function to check if Ollama API is responding
check_api() {
    curl -s -f "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1
    return $?
}

# Function to get running processes/models
get_status() {
    local response
    response=$(curl -s "${OLLAMA_HOST}/api/ps" 2>/dev/null || echo '{"models":[]}')
    echo "$response"
}

# Function to get server version (indicates server is fully started)
get_version() {
    curl -s "${OLLAMA_HOST}/api/version" >/dev/null 2>&1
    return $?
}

# Main health check logic
main() {
    # Check if API is responding at all
    if ! check_api; then
        echo "server:starting"
        exit 1
    fi

    # Check if version endpoint is available (server fully initialized)
    if ! get_version; then
        echo "server:loading"
        exit 1
    fi

    # Get current processes/models
    local status_response
    status_response=$(get_status)

    # Check if any models are currently loaded
    local model_count
    model_count=$(echo "$status_response" | grep -o '"name"' | wc -l 2>/dev/null || echo "0")

    if [ "$model_count" -gt 0 ]; then
        # Extract model name if available
        local model_name
        model_name=$(echo "$status_response" | sed -n 's/.*"name":"\([^"]*\)".*/\1/p' | head -1 2>/dev/null || echo "unknown")
        echo "server:$model_name"
    else
        echo "server:idle"
    fi

    exit 0
}

main "$@"
