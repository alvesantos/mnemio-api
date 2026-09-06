#!/usr/bin/env bash
set -e

# Aplica migrations pendentes antes de subir a API.
# Se falhar, o container morre e o deploy do Cloud Run é revertido (fail loud).
alembic upgrade head

# Cloud Run injeta PORT; 8080 é o default da plataforma.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
