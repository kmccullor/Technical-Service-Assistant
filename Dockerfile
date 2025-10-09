# Use the official Python 3.9 slim image as a base
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements files into the container
COPY requirements.txt .
COPY requirements-dev.txt .

# Install dependencies
# We install both regular and dev requirements to ensure all tools are available.
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-dev.txt

# Copy the entire project source code into the container
COPY . .

# Set environment variables for the database and embedding models
# These can be overridden at runtime (e.g., with `docker run -e ...`)
ENV DB_HOST=db
ENV DB_PORT=5432
ENV DB_NAME=vector_db
ENV DB_USER=postgres
ENV DB_PASSWORD=postgres
ENV OLLAMA_URL="http://ollama:11434/api/embeddings"
ENV EMBEDDING_MODEL="nomic-embed-text:v1.5"
ENV LOG_DIR="/app/logs"

# Expose any ports if the container were to run a web service (optional)
# EXPOSE 8000

# The default command to run when the container starts.
# This entrypoint is a placeholder; you can run specific scripts using
# `docker run <image_name> python pdf_processor/process_pdfs.py ...`
ENTRYPOINT ["/bin/bash"]
