FROM python:3.9-slim

# Install system dependencies required for Docling (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONPATH=/app
ENV JWT_SECRET=${JWT_SECRET:-dev-local-secret}

# Copy necessary application modules
COPY config.py /app/config.py
COPY utils/ /app/utils/
COPY pdf_processor/ /app/pdf_processor/
COPY docling_processor/ /app/docling_processor/

RUN pip install --no-cache-dir -r docling_processor/requirements.txt

CMD ["python", "docling_processor/docling_processor.py"]
