# Next.js RAG Application

A production-ready RAG (Retrieval Augmented Generation) web application built with Next.js 14, featuring hybrid search, reranking, and web fallback capabilities.

## Features

- **Hybrid Retrieval**: Dense vector search (pgvector) + lexical search (tsvector) with weighted fusion
- **Reranking**: Pluggable second-stage reranker (Cohere Rerank v3 or OSS alternatives)
- **Multi-turn Chat**: Persistent conversation history with citations
- **File Ingestion**: PDF, TXT, MD, HTML upload with chunking and embedding
- **Web Fallback**: Auto-fallback to web search when confidence is low
- **Real-time UI**: Streaming responses, citations panel, conversation management
- **Observability**: Request tracing, logging, optional Langfuse integration

## Quick Start

1. **Setup Environment**
```bash
cp .env.example .env.local
# Edit .env.local with your API keys and database URL
```

2. **Install Dependencies**
```bash
pnpm install
```

3. **Setup Database**
```bash
# Start PostgreSQL with pgvector (Docker)
docker-compose up -d db

# Run migrations
pnpm db:migrate

# Seed with sample data
pnpm db:seed
```

4. **Start Development Server**
```bash
pnpm dev
```

Open [http://rni-llm-01.lab.sensus.net:3000](http://rni-llm-01.lab.sensus.net:3000) with your browser.

## Architecture

### Stack
- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui
- **Backend**: Next.js API routes (Edge runtime where possible)
- **Database**: PostgreSQL with pgvector extension
- **State Management**: Zustand
- **Form Handling**: react-hook-form + zod validation
- **Styling**: Tailwind CSS + shadcn/ui components

### Data Flow
1. **Ingestion**: Files → Chunking → Embeddings → Store in DB
2. **Search**: Query → Embed → Hybrid search (vector + lexical) → Rerank → Context
3. **Generation**: Context + Query → LLM → Streaming response with citations
4. **Fallback**: Low confidence → Web search → Blended answer

## Database Schema

```sql
-- Documents table
documents (
  id UUID PRIMARY KEY,
  title TEXT NOT NULL,
  source TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  meta JSONB
);

-- Chunks table with vector embeddings
chunks (
  id UUID PRIMARY KEY,
  document_id UUID REFERENCES documents(id),
  content TEXT NOT NULL,
  content_tsv TSVECTOR,
  embedding VECTOR(1536),
  meta JSONB
);

-- Conversations
conversations (
  id UUID PRIMARY KEY,
  title TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Messages with citations
messages (
  id UUID PRIMARY KEY,
  conversation_id UUID REFERENCES conversations(id),
  role TEXT CHECK (role IN ('user', 'assistant', 'system')),
  content TEXT NOT NULL,
  citations JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## API Routes

### Chat & Search
- `POST /api/chat` - Multi-turn chat with streaming
- `POST /api/search/hybrid` - Hybrid search endpoint
- `POST /api/search/web` - Web search fallback

### Document Management
- `POST /api/ingest/upload` - File upload and processing
- `POST /api/ingest/urls` - URL ingestion
- `GET /api/documents` - List documents
- `DELETE /api/documents/[id]` - Delete document

### Conversations
- `GET /api/conversations` - List conversations
- `POST /api/conversations` - Create conversation
- `DELETE /api/conversations/[id]` - Delete conversation

## Environment Variables

Required variables for `.env.local`:

```bash
# Database
DATABASE_URL="postgresql://user:password@localhost:5432/rag_db"

# OpenAI
OPENAI_API_KEY="sk-your-openai-api-key-here"

# Cohere (optional - for reranking)
COHERE_API_KEY="..."

# Web Search (optional)
TAVILY_API_KEY="..."
# or
SERP_API_KEY="..."

# Langfuse (optional - for observability)
LANGFUSE_PUBLIC_KEY="..."
LANGFUSE_SECRET_KEY="..."
LANGFUSE_BASEURL="https://cloud.langfuse.com"

# App Configuration
NEXT_PUBLIC_APP_URL="http://localhost:3000"
RERANKER_ENABLED="true"
CONFIDENCE_THRESHOLD="0.7"
```

## Scripts

```bash
# Development
pnpm dev              # Start dev server
pnpm build            # Build for production
pnpm start            # Start production server

# Database
pnpm db:migrate       # Run database migrations
pnpm db:seed          # Seed with sample data
pnpm db:studio        # Open Drizzle Studio

# Testing
pnpm test             # Run unit tests
pnpm test:watch       # Run tests in watch mode
pnpm test:e2e         # Run E2E tests with Playwright

# Code Quality
pnpm lint             # ESLint
pnpm typecheck        # TypeScript check
```

## Testing

### Unit Tests
```bash
pnpm test
```

Tests cover:
- Chunking algorithms
- Hybrid search fusion
- Reranker adapters
- API route handlers

### Integration Tests
```bash
pnpm test -- --testPathPattern=integration
```

### E2E Tests
```bash
pnpm test:e2e
```

E2E scenarios:
- File upload → chat → citations
- Web fallback toggle
- Conversation persistence

## Deployment

### Docker
```bash
docker-compose up -d
```

### Vercel
1. Connect your repository to Vercel
2. Set environment variables in Vercel dashboard
3. Use Vercel Postgres or external PostgreSQL with pgvector

### Manual
```bash
pnpm build
pnpm start
```

## Configuration

### Hybrid Search Weights
Adjust in `/settings` page or via environment:
```bash
VECTOR_WEIGHT="0.7"
LEXICAL_WEIGHT="0.3"
```

### Reranking
Toggle reranking in settings or:
```bash
RERANKER_ENABLED="true"
RERANKER_MODEL="cohere"  # or "bge-reranker-large"
```

### Chunking Strategy
Configure in `lib/chunking.ts`:
- Chunk size: 512 tokens (default)
- Overlap: 50 tokens (default)
- Strategy: Recursive character splitting

# Docker-Only Execution & Auth Proxy Routes

**IMPORTANT:** This application is designed to run *exclusively* inside Docker containers. All backend services (auth, reranker, database, Ollama) are networked via Docker Compose and use container hostnames (e.g., `reranker`, `pgvector`).

- Do **not** run locally outside Docker; network hostnames will not resolve and login/auth will fail.
- All `/api/auth/*` routes are explicitly proxied via Next.js API routes (see `app/api/auth/*/route.ts`).
- No rewrites are used; each route forwards requests to the backend using Docker network hostnames.
- Health check and login flows are hardened for Docker-only execution.
- If you encounter a white screen or login failure, ensure you are running via `docker compose up -d` and all containers are healthy.

## Auth Proxy Route Coverage
- `/api/auth/health` → backend health check
- `/api/auth/login` → backend login
- `/api/auth/register` → backend registration
- `/api/auth/me` → backend user info
- `/api/auth/refresh` → backend token refresh
- `/api/auth/verify-email` → backend email verification

All proxy routes are implemented in `app/api/auth/*/route.ts` and forward requests to the backend using Docker network hostnames.

---

## Acceptance Criteria ✅

1. **✅ Basic RAG Flow**: Upload PDF → Ask question → See streaming answer with citations
2. **✅ Hybrid Search**: Vector + lexical search with fusion
3. **✅ Reranking**: Improves retrieval quality (demonstrated in eval script)
4. **✅ Web Fallback**: Clear (web) source labeling when enabled
5. **✅ Persistence**: Conversations and documents persist across sessions
6. **✅ Security**: All API keys are server-only, no client leaks

## Project Structure

```
next-rag-app/
├── app/                    # Next.js 14 App Router
│   ├── api/               # API routes
│   ├── (chat)/            # Chat pages
│   ├── data/              # Data management
│   └── settings/          # Settings page
├── components/            # Reusable UI components
│   ├── ui/               # shadcn/ui components
│   ├── chat/             # Chat-specific components
│   └── upload/           # File upload components
├── lib/                   # Core business logic
│   ├── db/               # Database connection and schema
│   ├── rag/              # RAG pipeline implementation
│   ├── search/           # Search and retrieval
│   └── utils/            # Utilities
├── scripts/              # Database and utility scripts
├── tests/                # Test suites
└── tools/                # MCP-style tools (optional)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

## License

MIT License - see LICENSE file for details.