# Production Test Infrastructure Docker Image
FROM python:3.9-slim

LABEL maintainer="Technical Service Assistant Team"
LABEL version="1.0.0"
LABEL description="Enterprise Test Infrastructure with AI-powered automation"

# Security: Create non-root user
RUN groupadd -r testinfra && useradd -r -g testinfra testinfra

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    sqlite3 \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/uploads /app/reports \
    && chown -R testinfra:testinfra /app

# Copy configuration files
COPY deployment/nginx.conf /etc/nginx/nginx.conf
COPY deployment/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose ports
EXPOSE 8080 8090 8008

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8090/api/suite-health || exit 1

# Switch to non-root user
USER testinfra

# Start services using supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
