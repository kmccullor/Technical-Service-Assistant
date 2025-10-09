FROM python:3.10-slim
WORKDIR /app
COPY reranker/app.py /app/app.py
COPY config.py /app/config.py
COPY utils/ /app/utils/
COPY reranker/intelligent_router.py /app/intelligent_router.py
COPY reranker/cache.py /app/cache.py
COPY reranker/query_classifier.py /app/query_classifier.py
COPY reranker/rag_chat.py /app/rag_chat.py
COPY reranker/temp_document_processor.py /app/temp_document_processor.py
COPY reranker/data_dictionary_api.py /app/data_dictionary_api.py
COPY reranker/database_schema_extractor.py /app/database_schema_extractor.py
COPY reranker/schema_extraction_utils.py /app/schema_extraction_utils.py
COPY reranker/knowledge_corrections.py /app/knowledge_corrections.py
COPY reranker/rbac_endpoints.py /app/rbac_endpoints.py
COPY reranker/admin_endpoints.py /app/admin_endpoints.py
COPY reranker/requirements.txt /app/requirements.txt
COPY reranker/healthcheck.sh /app/healthcheck.sh
# Copy reasoning engine
COPY reranker/reasoning_engine/ /app/reasoning_engine/
RUN chmod +x /app/healthcheck.sh
RUN apt-get update && apt-get install -y curl tesseract-ocr tesseract-ocr-eng \
    unixodbc unixodbc-dev && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 8008
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8008"]
