#!/bin/bash
set -e

# Prewarm opcional do modelo (usa o cache HF do volume)
# Controle via variável PREWARM_MODEL (default: 1)
PREWARM_MODEL="${PREWARM_MODEL:-1}"
EMBED_MODEL="${EMBED_MODEL:-sentence-transformers/all-MiniLM-L6-v2}"

if [ "$PREWARM_MODEL" = "1" ]; then
  echo "📦 Prewarm embeddings: $EMBED_MODEL (cache: ${HF_HOME:-/opt/hf_cache})"
  python - <<'PY'
import os
from sentence_transformers import SentenceTransformer

model = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
SentenceTransformer(model)
print("✅ Modelo carregado/cacheado com sucesso.")
PY
fi

echo "🚀 Iniciando API FastAPI na porta 8000..."
exec uvicorn api:app --host 0.0.0.0 --port 8000
