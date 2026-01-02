# RAG Hybrid Retrieval Pipeline

Pipeline de recuperação híbrida com **Dense + Sparse + RRF + Rerank** para chatbots RAG.

## Features

- **Dense Retrieval**: Busca vetorial em Qdrant usando embeddings
- **Sparse Retrieval**: BM25 com tokenização PT-BR
- **RRF Fusion**: Reciprocal Rank Fusion para combinar resultados
- **CrossEncoder Rerank**: Reranking do shortlist com CrossEncoder
- **Diversity Control**: Max chunks por documento
- **Filtros**: tenant_id, tags, source_id, date range
- **Observabilidade**: Timings, contagens, e debug detalhado
- **LangChain Integration**: Factories para LLM + Embeddings via LM Studio

## Quick Start

### 1. Subir Qdrant

```bash
cd rag_retrieval
docker-compose up -d qdrant
```

Acesse o dashboard: http://localhost:6333/dashboard

### 2. Instalar Dependências

```bash
pip install -e ".[dev]"
```

### 3. Configurar .env

```bash
cp .env.example .env
# Edite .env com suas configurações
```

### 4. Indexar Documentos de Exemplo

```python
from rag_retrieval.qdrant_store import QdrantStore

store = QdrantStore()

chunks = [
    {
        "id": "doc1_0",
        "doc_id": "doc1",
        "chunk_id": 0,
        "text": "Python é uma linguagem de programação popular...",
        "source_id": "manual",
        "title": "Introdução Python",
        "tags": ["python", "intro"],
    },
    {
        "id": "doc1_1",
        "doc_id": "doc1",
        "chunk_id": 1,
        "text": "NumPy é a biblioteca fundamental para arrays...",
        "source_id": "manual",
        "title": "NumPy Basics",
        "tags": ["python", "numpy"],
    },
    # ... mais chunks
]

store.upsert_chunks(chunks)
print(f"Indexed {store.count()} chunks")
```

### 5. Fazer Busca Híbrida

```python
from rag_retrieval import retrieve_and_rerank

chunks, debug = retrieve_and_rerank(
    query="Como usar Python para machine learning?",
    topk={"dense": 60, "sparse": 60, "fused": 80, "rerank": 12},
    diversity={"max_per_doc": 3, "min_docs": 3}
)

# Resultados
for chunk in chunks:
    print(f"[{chunk.rank}] {chunk.title}: {chunk.text[:100]}...")
    print(f"    Score: {chunk.score:.3f} | {chunk.why_picked}")

# Debug
print(f"\nTimings: {debug.timings}")
print(f"Counts: {debug.counts}")
```

### 6. Rodar API (Opcional)

```bash
uvicorn rag_retrieval.api:app --host 0.0.0.0 --port 8001 --reload
```

Endpoints:
- `POST /retrieve` - Busca híbrida
- `GET /health` - Health check
- `POST /index/rebuild` - Rebuild BM25

### 7. Rodar Testes

```bash
pytest tests/ -v
```

## Estrutura do Projeto

```
rag_retrieval/
├── rag_retrieval/
│   ├── __init__.py          # Exports
│   ├── types.py              # SearchHit, ContextChunk, DebugInfo
│   ├── config.py             # Settings (env vars)
│   ├── text_utils.py         # Tokenizer PT-BR, query extraction
│   ├── qdrant_store.py       # Qdrant client wrapper
│   ├── bm25_index.py         # BM25 sparse index
│   ├── rrf.py                # RRF fusion
│   ├── rerank.py             # CrossEncoder reranker
│   ├── lmstudio.py           # LangChain + LM Studio
│   ├── retriever.py          # Main hybrid retriever
│   └── api.py                # FastAPI endpoints
├── tests/
│   └── test_retriever.py     # Unit tests
├── docker-compose.yml        # Qdrant container
├── pyproject.toml            # Dependencies
├── .env.example              # Env template
└── README.md
```

## Pipeline de Retrieval

```
Query
  ↓
┌─────────────────────────────────────────┐
│  1. Extract Queries                      │
│     - dense_query (natural language)     │
│     - sparse_query (keywords, acronyms)  │
│     - must_have_terms (specific terms)   │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│  2. Dense Search (Qdrant)                │
│     - Embed query → vector              │
│     - Search top 60                      │
│     - Apply filters                      │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│  3. Sparse Search (BM25)                 │
│     - Tokenize query                     │
│     - BM25 score all docs               │
│     - Filter + top 60                    │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│  4. RRF Fusion                           │
│     - Score = Σ 1/(k + rank)            │
│     - Deduplicate (doc_id, chunk_id)    │
│     - Take top 80                        │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│  5. Rerank (CrossEncoder)                │
│     - ONLY rerank the 80 fused!         │
│     - Use query-passage pairs           │
│     - Take top 12                        │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│  6. Apply Diversity                      │
│     - Max 3 chunks per doc              │
│     - Min 3 different docs              │
│     - Generate why_picked               │
└─────────────────────────────────────────┘
  ↓
Final Context Chunks + DebugInfo
```

## Integração com LM Studio

```python
from rag_retrieval.lmstudio import build_llm, check_lmstudio_connection

# Verificar conexão
status = check_lmstudio_connection()
print(status)

# Usar LLM
llm = build_llm(temperature=0.7)
response = llm.invoke("Explique RAG em 2 frases")
print(response.content)
```

## Configuração via ENV

| Variável | Default | Descrição |
|----------|---------|-----------|
| `LMSTUDIO_BASE_URL` | `http://localhost:1234/v1` | URL do LM Studio |
| `QDRANT_URL` | `http://localhost:6333` | URL do Qdrant |
| `QDRANT_COLLECTION` | `rag_chunks` | Nome da coleção |
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Modelo de embedding |
| `CROSS_ENCODER_MODEL` | `ms-marco-MiniLM-L-6-v2` | Modelo de rerank |
| `INDEX_PATH` | `./.bm25_index` | Path do índice BM25 |

## License

MIT
