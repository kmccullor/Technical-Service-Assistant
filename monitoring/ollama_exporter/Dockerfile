FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl \
	&& rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY ollama_exporter.py ./
EXPOSE 9105
ENV OLLAMA_TARGETS="http://ollama-server-1:11434,http://ollama-server-2:11434,http://ollama-server-3:11434,http://ollama-server-4:11434"
ENTRYPOINT ["python", "ollama_exporter.py"]
