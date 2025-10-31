#!/bin/bash

# AI PDF Vector Stack - Model Specialization Script
# Date: September 20, 2025
# Purpose: Redistribute models across 4 Ollama instances for optimal performance

set -e

echo "🚀 Starting Model Specialization for AI PDF Vector Stack"
echo "========================================================="

# Configuration
INSTANCE_1="http://localhost:11434"  # General Chat & Document QA
INSTANCE_2="http://localhost:11435"  # Code & Technical Analysis
INSTANCE_3="http://localhost:11436"  # Advanced Reasoning & Math
INSTANCE_4="http://localhost:11437"  # Embeddings & Search Optimization

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check if Ollama instance is healthy
check_instance_health() {
    local instance_url=$1
    local instance_name=$2

    log "Checking health of $instance_name ($instance_url)"

    if curl -s "$instance_url/api/tags" > /dev/null 2>&1; then
        success "$instance_name is healthy"
        return 0
    else
        error "$instance_name is not responding"
        return 1
    fi
}

# Function to get current models on an instance
get_current_models() {
    local instance_url=$1
    curl -s "$instance_url/api/tags" | jq -r '.models[].name' 2>/dev/null || echo ""
}

# Function to remove a model from an instance
remove_model() {
    local instance_url=$1
    local model_name=$2
    local instance_name=$3

    log "Removing $model_name from $instance_name"

    # Use docker exec to remove model to avoid API limitations
    local container_name=""
    case $instance_url in
        *:11434) container_name="ollama-server-1" ;;
        *:11435) container_name="ollama-server-2" ;;
        *:11436) container_name="ollama-server-3" ;;
        *:11437) container_name="ollama-server-4" ;;
    esac

    if docker exec "$container_name" ollama rm "$model_name" > /dev/null 2>&1; then
        success "Removed $model_name from $instance_name"
    else
        warning "Could not remove $model_name from $instance_name (may not exist)"
    fi
}

# Function to pull a model to an instance
pull_model() {
    local instance_url=$1
    local model_name=$2
    local instance_name=$3

    log "Pulling $model_name to $instance_name"

    # Use docker exec to pull model
    local container_name=""
    case $instance_url in
        *:11434) container_name="ollama-server-1" ;;
        *:11435) container_name="ollama-server-2" ;;
        *:11436) container_name="ollama-server-3" ;;
        *:11437) container_name="ollama-server-4" ;;
    esac

    if docker exec "$container_name" ollama pull "$model_name"; then
        success "Successfully pulled $model_name to $instance_name"
    else
        error "Failed to pull $model_name to $instance_name"
        return 1
    fi
}

# Function to specialize an instance
specialize_instance() {
    local instance_url=$1
    local instance_name=$2
    shift 2
    local target_models=("$@")

    log "Specializing $instance_name with ${#target_models[@]} models"

    # Get current models
    local current_models=($(get_current_models "$instance_url"))

    # Remove models not in target list
    for model in "${current_models[@]}"; do
        local keep_model=false
        for target in "${target_models[@]}"; do
            if [[ "$model" == "$target" ]]; then
                keep_model=true
                break
            fi
        done

        if [[ "$keep_model" == false ]]; then
            remove_model "$instance_url" "$model" "$instance_name"
        fi
    done

    # Ensure all target models are present
    for target in "${target_models[@]}"; do
        local has_model=false
        for current in "${current_models[@]}"; do
            if [[ "$current" == "$target" ]]; then
                has_model=true
                break
            fi
        done

        if [[ "$has_model" == false ]]; then
            pull_model "$instance_url" "$target" "$instance_name"
        else
            log "$target already present in $instance_name"
        fi
    done

    success "Completed specialization of $instance_name"
}

# Main execution
main() {
    log "Starting Model Specialization Process"

    # Check all instances are healthy
    log "Step 1: Health Check"
    check_instance_health "$INSTANCE_1" "Instance 1 (General)" || exit 1
    check_instance_health "$INSTANCE_2" "Instance 2 (Code)" || exit 1
    check_instance_health "$INSTANCE_3" "Instance 3 (Reasoning)" || exit 1
    check_instance_health "$INSTANCE_4" "Instance 4 (Embeddings)" || exit 1

    log "All instances are healthy. Proceeding with specialization..."
    sleep 2

    # Define specialized model sets
    log "Step 2: Define Model Specialization"

    # Instance 1: General Chat & Document QA
    INSTANCE_1_MODELS=(
        "mistral:7b"
        "llama3.1:8b"
        "nomic-embed-text:v1.5"
    )

    # Instance 2: Code & Technical Analysis
    INSTANCE_2_MODELS=(
        "gemma2:2b"
        "phi3:mini"
        "mistral:7b"
    )

    # Instance 3: Advanced Reasoning & Math
    INSTANCE_3_MODELS=(
        "llama3.2:3b"
        "llama3.1:8b"
    )

    # Instance 4: Embeddings & Search Optimization
    INSTANCE_4_MODELS=(
        "nomic-embed-text:v1.5"
        "llama3.2:1b"
        "gemma2:2b"
    )

    # Execute specialization
    log "Step 3: Execute Specialization"

    specialize_instance "$INSTANCE_1" "Instance 1 (General)" "${INSTANCE_1_MODELS[@]}"
    specialize_instance "$INSTANCE_2" "Instance 2 (Code)" "${INSTANCE_2_MODELS[@]}"
    specialize_instance "$INSTANCE_3" "Instance 3 (Reasoning)" "${INSTANCE_3_MODELS[@]}"
    specialize_instance "$INSTANCE_4" "Instance 4 (Embeddings)" "${INSTANCE_4_MODELS[@]}"

    # Verification
    log "Step 4: Verification"
    echo ""
    echo "🔍 Final Model Distribution:"
    echo "=========================="

    echo ""
    echo "Instance 1 (General Chat & Document QA):"
    get_current_models "$INSTANCE_1" | sed 's/^/  - /'

    echo ""
    echo "Instance 2 (Code & Technical Analysis):"
    get_current_models "$INSTANCE_2" | sed 's/^/  - /'

    echo ""
    echo "Instance 3 (Advanced Reasoning & Math):"
    get_current_models "$INSTANCE_3" | sed 's/^/  - /'

    echo ""
    echo "Instance 4 (Embeddings & Search Optimization):"
    get_current_models "$INSTANCE_4" | sed 's/^/  - /'

    echo ""
    success "Model Specialization Complete!"
    echo ""

    # Next steps guidance
    log "Next Steps:"
    echo "  1. Update intelligent routing logic in reranker/app.py"
    echo "  2. Test specialized model performance"
    echo "  3. Update documentation with new model distribution"
    echo "  4. Implement monitoring for specialized instances"

    # Save specialization record
    log "Saving specialization record to data/model_specialization_$(date +%Y%m%d_%H%M%S).json"

    cat > "data/model_specialization_$(date +%Y%m%d_%H%M%S).json" << EOF
{
  "specialization_date": "$(date -Iseconds)",
  "instances": {
    "instance_1": {
      "url": "$INSTANCE_1",
      "purpose": "General Chat & Document QA",
      "models": $(printf '%s\n' "${INSTANCE_1_MODELS[@]}" | jq -R . | jq -s .)
    },
    "instance_2": {
      "url": "$INSTANCE_2",
      "purpose": "Code & Technical Analysis",
      "models": $(printf '%s\n' "${INSTANCE_2_MODELS[@]}" | jq -R . | jq -s .)
    },
    "instance_3": {
      "url": "$INSTANCE_3",
      "purpose": "Advanced Reasoning & Math",
      "models": $(printf '%s\n' "${INSTANCE_3_MODELS[@]}" | jq -R . | jq -s .)
    },
    "instance_4": {
      "url": "$INSTANCE_4",
      "purpose": "Embeddings & Search Optimization",
      "models": $(printf '%s\n' "${INSTANCE_4_MODELS[@]}" | jq -R . | jq -s .)
    }
  }
}
EOF

    success "Specialization record saved!"
}

# Check dependencies
if ! command -v jq &> /dev/null; then
    error "jq is required but not installed. Please install jq first."
    exit 1
fi

if ! command -v docker &> /dev/null; then
    error "docker is required but not installed. Please install docker first."
    exit 1
fi

# Run main function
main "$@"
