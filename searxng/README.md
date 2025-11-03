# SearXNG Setup for Technical Service Assistant

This directory contains the configuration for SearXNG, a privacy-respecting metasearch engine used for web search functionality in the Technical Service Assistant.

## Overview

SearXNG provides web search capabilities for the RAG system, allowing it to retrieve relevant information from the web when internal knowledge is insufficient.

## Configuration

The `settings.yml` file contains the SearXNG configuration with:

- **Privacy-focused settings**: No tracking, safe search disabled for technical content
- **Multiple search engines**: DuckDuckGo, Google, Startpage, Wikipedia, Bing
- **Performance optimizations**: HTTP/2, connection pooling
- **Security**: Custom secret key (change in production)

## Usage

### Starting SearXNG

```bash
# Using docker-compose
docker-compose up searxng

# Or with the full stack
docker-compose up
```

### Accessing SearXNG

- **Internal**: http://searxng:8080 (from other containers)
- **External**: http://localhost:8888 (when running locally)

### Health Check

```bash
curl http://localhost:8888/healthz
```

## Integration

The RAG system in `reranker/rag_chat.py` uses SearXNG for:

1. **Sensus Training Search**: Prioritized search on sensus-training.com
2. **Broad Web Search**: General web search for technical queries

## Security Notes

- Change the `secret_key` in `settings.yml` for production
- Consider enabling authentication if exposing externally
- Monitor search logs for abuse

## Troubleshooting

- **Container won't start**: Check settings.yml syntax
- **No search results**: Verify network connectivity and engine configurations
- **Slow responses**: Adjust timeouts in settings.yml

## References

- [SearXNG Documentation](https://docs.searxng.org/)
- [SearXNG GitHub](https://github.com/searxng/searxng)