"""
Example: Index sample documents and test retrieval
"""
from rag_retrieval.qdrant_store import QdrantStore
from rag_retrieval.bm25_index import BM25Index
from rag_retrieval import retrieve_and_rerank


# Sample documents to index
SAMPLE_DOCS = [
    {
        "id": "python_intro_0",
        "doc_id": "python_intro",
        "chunk_id": 0,
        "text": """Python é uma linguagem de programação de alto nível, interpretada e de propósito geral.
        Criada por Guido van Rossum e lançada em 1991, Python enfatiza a legibilidade do código
        e permite expressar conceitos em menos linhas de código do que seria possível em linguagens
        como C++ ou Java. Python suporta múltiplos paradigmas de programação, incluindo programação
        estruturada, orientada a objetos e funcional.""",
        "source_id": "manual_python",
        "title": "Introdução ao Python",
        "tags": ["python", "programacao", "intro"],
    },
    {
        "id": "python_intro_1",
        "doc_id": "python_intro",
        "chunk_id": 1,
        "text": """NumPy é a biblioteca fundamental para computação numérica em Python. Ela fornece
        suporte para arrays multidimensionais, junto com uma grande coleção de funções matemáticas
        de alto nível para operar nesses arrays. NumPy é a base de muitas outras bibliotecas
        científicas em Python, como SciPy, Pandas e scikit-learn.""",
        "source_id": "manual_python",
        "title": "NumPy e Computação Numérica",
        "tags": ["python", "numpy", "ciencia_dados"],
    },
    {
        "id": "rag_intro_0",
        "doc_id": "rag_intro",
        "chunk_id": 0,
        "text": """RAG (Retrieval-Augmented Generation) é uma técnica que combina recuperação de
        informação com geração de texto usando Large Language Models (LLMs). Em vez de depender
        apenas do conhecimento paramétrico do modelo, RAG busca documentos relevantes em uma base
        de conhecimento e os usa como contexto para gerar respostas mais precisas e atualizadas.""",
        "source_id": "blog_ia",
        "title": "O que é RAG",
        "tags": ["rag", "llm", "ia"],
    },
    {
        "id": "rag_intro_1",
        "doc_id": "rag_intro",
        "chunk_id": 1,
        "text": """A busca híbrida combina recuperação densa (baseada em vetores) com recuperação
        esparsa (baseada em palavras-chave, como BM25). Isso proporciona melhor recall do que
        usar apenas um método. Reciprocal Rank Fusion (RRF) é uma técnica popular para combinar
        os rankings de múltiplos métodos de recuperação.""",
        "source_id": "blog_ia",
        "title": "Busca Híbrida em RAG",
        "tags": ["rag", "search", "bm25"],
    },
    {
        "id": "fastapi_0",
        "doc_id": "fastapi",
        "chunk_id": 0,
        "text": """FastAPI é um framework web moderno e de alto desempenho para criar APIs em Python.
        Ele é baseado em type hints do Python e usa Pydantic para validação de dados. FastAPI
        gera automaticamente documentação OpenAPI (Swagger) e suporta operações assíncronas
        nativamente, tornando-o ideal para aplicações de alta performance.""",
        "source_id": "docs_tech",
        "title": "FastAPI - Framework Web Python",
        "tags": ["python", "api", "web"],
    },
    {
        "id": "lmstudio_0",
        "doc_id": "lmstudio",
        "chunk_id": 0,
        "text": """LM Studio é uma aplicação desktop que permite rodar Large Language Models (LLMs)
        localmente no seu computador. Ele suporta modelos no formato GGUF e expõe uma API
        compatível com OpenAI, facilitando a integração com bibliotecas como LangChain.
        Modelos populares incluem Llama, Mistral, e Phi.""",
        "source_id": "docs_tech",
        "title": "LM Studio - LLMs Locais",
        "tags": ["llm", "lmstudio", "local"],
    },
]


def main():
    print("=" * 60)
    print("RAG Hybrid Retrieval - Example")
    print("=" * 60)
    
    # 1. Index documents
    print("\n📦 Indexing documents in Qdrant...")
    store = QdrantStore()
    store.upsert_chunks(SAMPLE_DOCS)
    print(f"✅ Total in Qdrant: {store.count()} chunks")
    
    # 2. Build BM25 index
    print("\n📊 Building BM25 index...")
    payloads = store.get_all_payloads()
    bm25 = BM25Index()
    bm25.build_from_payloads(payloads)
    print(f"✅ BM25 index: {bm25.count()} documents")
    
    # 3. Test retrieval
    queries = [
        "O que é Python e para que serve?",
        "Como funciona a busca híbrida em RAG?",
        "Como rodar LLMs localmente?",
    ]
    
    for query in queries:
        print("\n" + "=" * 60)
        print(f"🔍 Query: {query}")
        print("=" * 60)
        
        chunks, debug = retrieve_and_rerank(
            query=query,
            topk={"dense": 20, "sparse": 20, "fused": 30, "rerank": 5},
            diversity={"max_per_doc": 2, "min_docs": 2}
        )
        
        print(f"\n📊 Results: {len(chunks)} chunks")
        print(f"⏱️  Timings: embed={debug.timings['embed_ms']:.1f}ms, "
              f"dense={debug.timings['dense_ms']:.1f}ms, "
              f"sparse={debug.timings['sparse_ms']:.1f}ms, "
              f"rerank={debug.timings['rerank_ms']:.1f}ms, "
              f"total={debug.timings['total_ms']:.1f}ms")
        
        for chunk in chunks:
            print(f"\n[{chunk.rank}] {chunk.title}")
            print(f"    Doc: {chunk.doc_id} | Chunk: {chunk.chunk_id}")
            print(f"    Score: {chunk.score:.4f}")
            print(f"    Why: {chunk.why_picked}")
            print(f"    Text: {chunk.text[:150]}...")
        
        if debug.notes:
            print(f"\n📝 Notes: {debug.notes}")


if __name__ == "__main__":
    main()
