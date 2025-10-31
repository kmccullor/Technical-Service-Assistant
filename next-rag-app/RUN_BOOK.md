# 🚀 Next.js RAG Application - Run Book

**✅ PRODUCTION VALIDATED** - Docker deployment with load balancing and high confidence scores (September 24, 2025)

## Quick Start Commands

### 1. Environment Setup (UPDATED FOR DOCKER)
```bash
# For Docker deployment (RECOMMENDED)
# .env.local is already configured for container networking

# For local development only
cp .env.example .env.local
nano .env.local
```

**⚠️ IMPORTANT:** Docker deployment uses container names (`pgvector`, `ollama-server-1-4`) while local development uses `localhost`. The `.env.local` file is now configured for Docker deployment.

### 2. Docker Production Deployment (VALIDATED SETUP)
```bash
# Build and start all services with load balancing
docker compose up -d technical-service-assistant --build

# Verify load balancer is working
docker logs technical-service-assistant | grep "Selected instance"

# Test high confidence RAG
curl -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is load balancing?"}]}'
```

### 2B. Local Development Setup (Alternative)
```bash
# Start PostgreSQL with pgvector
docker-compose up -d db

# Wait for database to be ready
docker-compose logs -f db

# Run migrations
pnpm db:migrate

# Seed with sample data
pnpm db:seed
```

### 3. Development
```bash
# Install dependencies
pnpm install

# Start development server
pnpm dev

# Open browser to http://localhost:3000
```

## Complete Docker Setup
```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

## Verification Steps

### 1. Test Database Connection
```bash
# Connect to database
psql postgresql://postgres:postgres@localhost:5432/rag_db

# Check tables
\dt

# Check pgvector extension
SELECT * FROM pg_extension WHERE extname = 'vector';

# Exit psql
\q
```

### 2. Test RAG Pipeline
```bash
# Run evaluation suite
pnpm run scripts/eval.ts

# Check specific components
pnpm typecheck
pnpm lint
```

### 3. Test Chat Interface
1. Open http://localhost:3000
2. Upload a PDF or use sample data
3. Ask: "What is RAG and how does it work?"
4. Verify streaming response with citations
5. Check context panel shows relevant sources

## Production Deployment

### Vercel (Recommended)
```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel

# Set environment variables in Vercel dashboard
# Add Vercel Postgres addon or external PostgreSQL
```

### Docker Production
```bash
# Build production image
docker build -t rag-app .

# Run with production database
docker run -p 3000:3000 \
  -e DATABASE_URL="your-production-db-url" \
  -e OPENAI_API_KEY="sk-your-openai-api-key-here" \
  rag-app
```

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   ```bash
   # Check if PostgreSQL is running
   docker-compose ps db

   # Reset database
   docker-compose down -v
   docker-compose up -d db
   pnpm db:migrate
   ```

2. **Embeddings Not Working**
   - Verify OPENAI_API_KEY in .env.local
   - Check API quota and billing
   - Test with smaller chunks

3. **Search Returns No Results**
   ```bash
   # Check if data exists
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM chunks;"

   # Re-seed database
   pnpm db:seed
   ```

4. **TypeScript Errors**
   ```bash
   # Install missing types
   pnpm add -D @types/node @types/react @types/react-dom

   # Check configuration
   pnpm typecheck
   ```

## Performance Optimization

### Database Tuning
```sql
-- Optimize HNSW index
ALTER INDEX embedding_idx SET (m = 16, ef_construction = 64);

-- Update statistics
ANALYZE chunks;

-- Check index usage
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM chunks
ORDER BY embedding <=> '[0.1,0.2,...]'::vector
LIMIT 10;
```

### Application Tuning
- Enable Next.js static generation where possible
- Use Edge runtime for API routes
- Implement request caching for embeddings
- Optimize chunk sizes based on your content

## Monitoring

### Health Checks
```bash
# API health
curl http://localhost:3000/api/health

# Database health
curl http://localhost:3000/api/db/health

# Check logs
docker-compose logs app
```

### Performance Metrics
- Response time: < 5 seconds target
- Embedding generation: < 2 seconds
- Database queries: < 500ms
- Memory usage: Monitor for embedding cache

## API Documentation

### Chat Endpoint
```bash
curl -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is RAG?"}],
    "useWebFallback": true
  }'
```

### Upload Endpoint
```bash
curl -X POST http://localhost:3000/api/ingest/upload \
  -F "file=@document.pdf"
```

## TODOs & Enhancements

### High Priority
- [ ] Implement reranking with Cohere API
- [ ] Add web search fallback (Tavily integration)
- [ ] Implement conversation persistence
- [ ] Add file upload UI with progress

### Medium Priority
- [ ] Add user authentication
- [ ] Implement rate limiting
- [ ] Add Langfuse tracing integration
- [ ] Create admin dashboard for document management

### Low Priority
- [ ] Add dark mode theme
- [ ] Implement keyboard shortcuts
- [ ] Add export/import functionality
- [ ] Create mobile-responsive design

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review logs: `docker-compose logs -f`
3. Test individual components with the eval script
4. Check database connectivity and content

Remember to:
- Keep API keys secure and never commit them
- Monitor token usage and costs
- Regular database maintenance and backups
- Update dependencies for security patches
