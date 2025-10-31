# System Maintenance Guide

## Daily Cleanup (Automated)

The daily morning checklist (`make morning`) now includes automated cleanup checks:

### 🔍 **Automated Monitoring**
- **Backup Files**: Warns if >10 `.bak*` files detected
- **Log Directory**: Warns if logs exceed 500MB
- **Python Cache**: Automatically cleans up excessive `__pycache__` directories (>20)
- **Docker Space**: Warns if >50GB reclaimable space available

### ✅ **Daily Actions Taken**
- Removes Python cache files when excessive
- Provides specific commands for manual cleanup when needed
- Reports current status for all cleanup metrics

## Weekly Cleanup (Manual)

Run weekly maintenance with:
```bash
make cleanup
```

### 🧹 **Weekly Cleanup Actions**
- **Old Backup Files**: Removes `.bak*` files older than 7 days
- **Old Log Files**: Removes log files older than 7 days
- **Python Cache**: Removes all `__pycache__` directories
- **Temporary Files**: Removes `.pyc`, `.tmp`, `.DS_Store` files
- **Docker System**: Prunes unused images, containers, and build cache

## Manual Cleanup Commands

### Individual Cleanup Tasks
```bash
# Database integrity check
make check-db

# Remove specific file types
find . -name "*.bak*" -type f -mtime +7 -delete
find logs/ -type f -mtime +7 -delete
find . -name "__pycache__" -type d -exec rm -rf {} +

# Docker cleanup
docker system prune -f --volumes
```

### Emergency Cleanup
If the system becomes cluttered:
```bash
# Full cleanup sequence
make cleanup
make check-db
make health-check
```

## Prevention

### .gitignore Protection
The project `.gitignore` prevents these file types from being committed:
- `*.bak`, `*.bak.*`, `*.orig` - Backup files
- `__pycache__/`, `*.pyc` - Python cache
- `*.tmp`, `*.temp` - Temporary files
- `logs/*.log`, `logs/*.html` - Log files

### Best Practices
1. **Run `make morning` daily** - Automated monitoring and cleanup
2. **Run `make cleanup` weekly** - Comprehensive system maintenance
3. **Monitor disk usage** - Watch for unusual growth patterns
4. **Keep Docker pruned** - Prevents excessive space usage
5. **Review logs regularly** - Archive important logs before cleanup

## Troubleshooting

### Cleanup Issues
- **Permission errors**: Some files may require `sudo` for removal
- **Docker not available**: Cleanup skips Docker operations gracefully
- **Large log files**: Consider archiving important logs before cleanup

### Recovery
- **Logs**: Docker containers maintain their own logs, only file-based logs are cleaned
- **Database**: Cleanup never touches database data
- **Configuration**: All config files are preserved
- **Active code**: Only cache and temporary files are removed

## Monitoring Integration

The morning checklist reports cleanup metrics in the daily summary:
- Backup file count
- Log directory size
- Python cache directory count
- Docker reclaimable space

These metrics help track system health and maintenance needs over time.
