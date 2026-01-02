# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS base
ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# Runtime deps (OCR + utils)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    git \
    tesseract-ocr \
    tesseract-ocr-por \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

FROM base AS deps
# Build deps (só aqui)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 1) instala dependências base
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install -U pip && \
    python -m pip install -r requirements.txt

# 2) instala dependências GPU (torch) separadamente
COPY requirements-gpu.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install -r requirements-gpu.txt

FROM base AS app
COPY --from=deps /usr/local /usr/local

# Copia o código
COPY . .

# Diretórios necessários + permissões do start
RUN mkdir -p docs db memory && \
    sed -i 's/\r$//' /app/start.sh && chmod +x /app/start.sh

EXPOSE 7860 8000

ENV PYTHONUNBUFFERED=1
ENV EMBEDDING_DEVICE=cuda
ENV OVERRIDES_DISABLE=1

CMD ["/app/start.sh"]
