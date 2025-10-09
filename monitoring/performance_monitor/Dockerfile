FROM python:3.10-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    EXPORTER=1 \
    EXPORTER_PORT=9109

# System deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl && rm -rf /var/lib/apt/lists/*

# Copy only what we need
COPY config.py /app/config.py
COPY utils/ /app/utils/
COPY monitoring/performance_monitor/performance_monitor.py /app/performance_monitor.py

# Install minimal deps
RUN pip install --no-cache-dir psycopg2-binary requests prometheus-client

EXPOSE 9109

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:9109/ || exit 1

CMD ["python", "performance_monitor.py"]
