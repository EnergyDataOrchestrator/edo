FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Ontology is mounted read-only (see the root docker-compose.yml, profile 'semantic')
VOLUME /app/ontology

EXPOSE 8090
CMD ["uvicorn", "socket_ux.api:app", "--host", "0.0.0.0", "--port", "8090"]
