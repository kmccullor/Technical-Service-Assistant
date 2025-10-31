FROM python:3.10-slim
WORKDIR /app
COPY reasoning_engine/requirements.txt /app/requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
COPY reasoning_engine/ /app/reasoning_engine/
COPY config.py /app/config.py
COPY utils/ /app/utils/

# Simple ASGI bootstrap exposing orchestrator later (placeholder health endpoint)
RUN echo "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/health')\nasync def health():\n    return {'status':'ok'}\n" > /app/main.py

EXPOSE 8050
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8050"]
