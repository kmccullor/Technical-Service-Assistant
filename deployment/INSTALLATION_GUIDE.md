# Technical Service Assistant - Installation Guide
# ==============================================

This guide will help you install the Technical Service Assistant on a new server.

## System Requirements

### Minimum Requirements
- **OS**: Linux (Ubuntu 20.04+, CentOS 8+, or similar)
- **Architecture**: x86_64 (AMD64)
- **Memory**: 8GB RAM (16GB recommended)
- **Storage**: 50GB free disk space (SSD recommended)
- **Network**: Internet connection for downloading models and dependencies

### Recommended Requirements
- **Memory**: 16GB+ RAM for optimal performance
- **Storage**: 100GB+ SSD storage
- **CPU**: 8+ cores for concurrent processing
- **GPU**: NVIDIA GPU with 8GB+ VRAM (optional, for faster inference)

## Quick Installation

### Option 1: Automated Installation (Recommended)

```bash
# Download the installer
curl -fsSL https://raw.githubusercontent.com/technical-service-assistant/technical-service-assistant/main/install.sh -o install.sh

# Make executable and run
chmod +x install.sh
sudo ./install.sh
```

### Option 2: Manual Installation

#### Step 1: Clone Repository
```bash
git clone https://github.com/technical-service-assistant/technical-service-assistant.git
cd technical-service-assistant
```

#### Step 2: Install Dependencies
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y docker.io docker-compose python3 python3-pip nginx

# CentOS/RHEL
sudo yum install -y docker docker-compose python3 python3-pip nginx
```

#### Step 3: Configure Environment
```bash
# Copy environment template
cp .env.production .env

# Edit configuration
nano .env
```

#### Step 4: Start Services
```bash
# Build and start containers
docker-compose -f docker-compose.production.yml up -d

# Run post-installation setup
python3 scripts/install.py
```

## Configuration

### Environment Variables

The system is configured through environment variables in the `.env` file:

```bash
# Database
DB_PASSWORD=your_secure_password_here
DATABASE_URL=postgresql://postgres:your_password@pgvector:5432/vector_db

# API Security
API_KEY=your_api_key_here
JWT_SECRET_KEY=your_jwt_secret_here

# File Processing
UPLOADS_DIR=/opt/technical-service-assistant/uploads
MAX_FILE_SIZE=100MB

# AI Models
EMBEDDING_MODEL=nomic-embed-text:v1.5
DEFAULT_CHAT_MODEL=llama2

# Monitoring
ENABLE_MONITORING=true
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
```

### Network Configuration

By default, the system exposes these ports:
- **80**: Web interface (HTTP)
- **443**: Web interface (HTTPS, if SSL enabled)
- **8008**: API endpoints
- **3000**: Grafana monitoring dashboard
- **9090**: Prometheus metrics

### SSL Configuration (Optional)

To enable HTTPS:

1. Obtain SSL certificates
2. Place certificates in `deployment/nginx/ssl/`
3. Set `ENABLE_SSL=true` in `.env`
4. Restart services: `docker-compose -f docker-compose.production.yml restart nginx`

## Post-Installation Setup

### 1. Download AI Models

The system will automatically download required models on first startup:
- `nomic-embed-text:v1.5` (embedding model)
- `llama2` (default chat model)
- `mistral:7b` (technical questions)
- `codellama` (code generation)

To manually download models:
```bash
python3 scripts/install.py --skip-monitoring
```

### 2. Create Admin User

1. Navigate to `http://your-server-ip/`
2. Create your first admin account
3. Configure user permissions as needed

### 3. Upload Test Documents

1. Access the web interface
2. Upload some PDF documents
3. Wait for processing to complete
4. Test search functionality

### 4. Configure Monitoring (Optional)

1. Access Grafana at `http://your-server-ip:3000`
2. Login with admin/admin (change password)
3. Import pre-configured dashboards
4. Set up alerts if needed

## Service Management

### Systemd Service

The installer creates a systemd service for easy management:

```bash
# Check status
sudo systemctl status technical-service-assistant

# Start/stop/restart
sudo systemctl start technical-service-assistant
sudo systemctl stop technical-service-assistant
sudo systemctl restart technical-service-assistant

# View logs
journalctl -u technical-service-assistant -f
```

### Docker Commands

```bash
# View running containers
docker ps

# Check logs
docker-compose -f docker-compose.production.yml logs -f

# Restart specific service
docker-compose -f docker-compose.production.yml restart reranker

# Update containers
docker-compose -f docker-compose.production.yml pull
docker-compose -f docker-compose.production.yml up -d
```

## Maintenance

### Backup

Regular backups are essential:

```bash
# Database backup
docker exec tsa-pgvector pg_dump -U postgres vector_db > backup_$(date +%Y%m%d).sql

# Configuration backup
tar -czf config_backup_$(date +%Y%m%d).tar.gz .env docker-compose.production.yml

# Document backup
tar -czf uploads_backup_$(date +%Y%m%d).tar.gz uploads/
```

### Updates

To update the system:

```bash
# Pull latest code
git pull origin main

# Update containers
docker-compose -f docker-compose.production.yml pull
docker-compose -f docker-compose.production.yml up -d

# Run any migrations
python3 scripts/install.py --health-check-only
```

### Monitoring

Monitor system health through:
- Grafana dashboard: `http://your-server-ip:3000`
- Prometheus metrics: `http://your-server-ip:9090`
- Application logs: `journalctl -u technical-service-assistant -f`

## Troubleshooting

### Common Issues

1. **Services won't start**
   - Check Docker daemon: `sudo systemctl status docker`
   - Verify environment variables in `.env`
   - Check disk space: `df -h`

2. **Models not downloading**
   - Verify internet connection
   - Check Ollama containers: `docker logs tsa-ollama-1`
   - Manually pull models: `docker exec tsa-ollama-1 ollama pull llama2`

3. **Database connection errors**
   - Verify PostgreSQL is running: `docker logs tsa-pgvector`
   - Check database credentials in `.env`
   - Ensure database has been initialized

4. **Web interface not accessible**
   - Check nginx configuration
   - Verify frontend container: `docker logs tsa-frontend`
   - Check firewall settings

### Log Locations

- Application logs: `/opt/technical-service-assistant/logs/`
- System logs: `journalctl -u technical-service-assistant`
- Container logs: `docker-compose logs`

### Getting Help

- Documentation: `/opt/technical-service-assistant/app/README.md`
- Troubleshooting: `/opt/technical-service-assistant/app/TROUBLESHOOTING.md`
- GitHub Issues: https://github.com/technical-service-assistant/issues

## Security Considerations

1. **Change default passwords** in `.env`
2. **Use strong API keys** (32+ characters)
3. **Enable firewall** and restrict access to necessary ports
4. **Regular updates** of system and container images
5. **Monitor access logs** for suspicious activity
6. **Backup encryption** for sensitive documents

## Performance Tuning

### Resource Allocation

Adjust Docker resource limits in `docker-compose.production.yml`:

```yaml
deploy:
  resources:
    limits:
      memory: 4g
      cpus: '2.0'
```

### Database Optimization

For large document collections:

```sql
-- Create additional indexes
CREATE INDEX CONCURRENTLY idx_document_chunks_embedding_cosine
ON document_chunks USING ivfflat (embedding vector_cosine_ops);

-- Adjust PostgreSQL settings
shared_buffers = 1GB
effective_cache_size = 4GB
work_mem = 256MB
```

### Model Optimization

- Use quantized models for faster inference
- Adjust `CHUNK_SIZE` and `MAX_CONTEXT_CHUNKS` for your use case
- Consider GPU acceleration for heavy workloads

## Advanced Configuration

### Custom Models

To use custom or alternative models:

1. Pull model to Ollama container:
   ```bash
   docker exec tsa-ollama-1 ollama pull your-custom-model
   ```

2. Update environment variables:
   ```bash
   DEFAULT_CHAT_MODEL=your-custom-model
   ```

3. Restart services:
   ```bash
   docker-compose -f docker-compose.production.yml restart
   ```

### High Availability Setup

For production deployments:

1. **Load Balancer**: Use nginx or HAProxy for multiple instances
2. **Database Clustering**: PostgreSQL with streaming replication
3. **Shared Storage**: NFS or distributed filesystem for uploads
4. **Container Orchestration**: Consider Kubernetes for large scale

### Integration with External Systems

The system provides REST APIs for integration:

```bash
# Health check
curl http://your-server/health

# Search API
curl -X POST http://your-server/api/search \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"query": "your search terms"}'

# Chat API
curl -X POST http://your-server/api/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'
```

## License and Support

The Technical Service Assistant is open source software. For commercial support and enterprise features, please contact the development team.

---

For more detailed information, see the full documentation in the `docs/` directory.
