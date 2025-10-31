FROM python:3.10-slim
WORKDIR /app/reranker
COPY reranker/ /app/reranker/
COPY config.py /app/config.py
COPY utils/ /app/utils/
COPY scripts/ /app/scripts/
ENV PYTHONPATH=/app
RUN chmod +x /app/reranker/healthcheck.sh
RUN apt-get update && apt-get install -y curl \
    unixodbc unixodbc-dev tesseract-ocr && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r /app/reranker/requirements.txt
EXPOSE 8008
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8008"]
