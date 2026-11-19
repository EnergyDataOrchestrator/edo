FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Ontology is mounted read-only (see docker-compose_w_semantic_layer.yml)
VOLUME /app/ontology

EXPOSE 8090
CMD ["uvicorn", "socket_ux.api:app", "--host", "0.0.0.0", "--port", "8090"]
