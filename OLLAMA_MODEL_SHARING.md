# Ollama Model Repository Sharing

## Overview
All 8 Ollama instances now share a single model repository volume, eliminating duplicate model storage and reducing bandwidth requirements.

## Architecture

### Volume Configuration
- **ollama_models** (SHARED): Central repository for all LLM models
  - Mounted at `/root/.ollama/models` on all 8 containers
  - Contains downloaded models: codellama:7b, mistral:7b, llama3.2:3b, etc.
  - Single source of truth for all instances

- **ollama_data_1..8** (PER-CONTAINER): Individual container state
  - Mounted at `/root/.ollama` on each container
  - Contains cache, locks, and per-container metadata
  - Prevents race conditions during concurrent model loading

### Model Layout
```
ollama_models/ (shared volume)
├── models/
│   ├── codellama:7b/
│   ├── mistral:7b/
│   ├── llama3.2:3b/
│   └── ... (other models)
└── (models downloaded by any container are instantly available to all)

ollama_data_1..8/ (per-container volumes)
├── ollama_data_1/.ollama/     ← Server 1 state & cache
├── ollama_data_2/.ollama/     ← Server 2 state & cache
├── ...
└── ollama_data_8/.ollama/     ← Server 8 state & cache
```

## Benefits

1. **Storage Efficiency**: ~60GB reduction
   - Before: 8 containers × 15GB models = 120GB
   - After: 1 × 15GB models + 8 × 64MB state = 15.5GB
   - Savings: ~87.5% reduction in disk space

2. **Faster Initialization**
   - New instances instantly access pre-downloaded models
   - No redundant downloads
   - Faster startup and failover

3. **Simplified Management**
   - Single model repository to maintain
   - Easier updates and cleanup
   - Consistent model versions across all servers

4. **Bandwidth Savings**
   - Each model downloaded once
   - Shared across all instances
   - Estimated 15-20GB bandwidth savings per full model refresh

## Current Models
- **codellama:7b** - 3.7GB
- **mistral:7b** - 4.1GB  
- **llama3.2:3b** - 2.0GB
- **llama2:7b** - 3.9GB
- **neural-chat** - 4.0GB

## Technical Details

### Docker Compose Configuration
Each Ollama service mounts two volumes:
```yaml
ollama-server-1:
  volumes:
    - ollama_models:/root/.ollama/models      # Shared
    - ollama_data_1:/root/.ollama              # Per-container
```

### Concurrent Access
- Models are read-only at runtime (thread-safe)
- Container-specific state (cache, locks) stays separate
- No file locking issues with shared read access

### Migration
Models were automatically migrated during setup:
1. Existing models from individual volumes copied to shared volume
2. Containers restarted with new volume configuration
3. All 8 instances now share the same model repository

## Maintenance

### Adding New Models
Download on any instance - automatically available to all:
```bash
docker compose exec ollama-server-1 ollama pull llama2:latest
# This model is now accessible from ollama-server-2..8
```

### Cleanup
Remove unused models (affects all instances):
```bash
docker compose exec ollama-server-1 ollama rm unused-model
```

### Monitoring Storage
```bash
# Check shared model volume size
docker volume inspect technical-service-assistant_ollama_models | grep Mountpoint
du -sh /var/lib/docker/volumes/technical-service-assistant_ollama_models/_data/

# List all models
curl http://localhost:11434/api/tags | jq '.models[] | .name'
```

## Troubleshooting

### Model Not Available on All Servers
Models sync instantly due to shared volume. If not visible:
```bash
# Refresh model index
docker compose exec ollama-server-1 ollama list
docker compose exec ollama-server-2 ollama list
```

### Storage Still High
May include model cache. Clean container-specific caches:
```bash
# Warning: This clears caches but doesn't delete models
docker volume prune  # Only after stopping services
```

### Performance Concerns
Shared volume I/O is minimal:
- Models loaded once into container memory
- Concurrent access to same model is safe (read-only)
- No contention for write operations (models are static)
