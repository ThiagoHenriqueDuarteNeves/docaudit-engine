"""
Tests for Hybrid Retrieval Pipeline
"""
import pytest
from rag_retrieval.types import SearchHit, DebugInfo, RetrievalFilters
from rag_retrieval.rrf import rrf_fuse
from rag_retrieval.text_utils import tokenize_ptbr, extract_sparse_query, must_have_terms


# Sample data for testing
SAMPLE_CHUNKS = [
    {
        "id": 1,
        "doc_id": "doc_1",
        "chunk_id": 0,
        "text": "Python é uma linguagem de programação popular para machine learning e IA.",
        "source_id": "manual",
        "title": "Introdução Python",
        "tags": ["python", "ml"],
    },
    {
        "id": 2,
        "doc_id": "doc_1",
        "chunk_id": 1,
        "text": "O NumPy é a biblioteca fundamental para computação numérica em Python.",
        "source_id": "manual",
        "title": "NumPy Basics",
        "tags": ["python", "numpy"],
    },
    {
        "id": 3,
        "doc_id": "doc_2",
        "chunk_id": 0,
        "text": "RAG combina recuperação de documentos com geração de texto usando LLMs.",
        "source_id": "blog",
        "title": "O que é RAG",
        "tags": ["rag", "llm"],
    },
    {
        "id": 4,
        "doc_id": "doc_2",
        "chunk_id": 1,
        "text": "A busca híbrida usa vetores densos e esparsos para melhor recall.",
        "source_id": "blog",
        "title": "Busca Híbrida",
        "tags": ["rag", "search"],
    },
    {
        "id": 5,
        "doc_id": "doc_3",
        "chunk_id": 0,
        "text": "FastAPI é um framework web moderno e rápido para APIs em Python.",
        "source_id": "docs",
        "title": "FastAPI Intro",
        "tags": ["python", "api"],
    },
    {
        "id": 6,
        "doc_id": "doc_3",
        "chunk_id": 1,
        "text": "Uvicorn é o servidor ASGI recomendado para rodar FastAPI em produção.",
        "source_id": "docs",
        "title": "Deploy FastAPI",
        "tags": ["python", "deploy"],
    },
]


def make_hit(chunk: dict, score: float, source: str) -> SearchHit:
    """Helper to create SearchHit from chunk dict"""
    return SearchHit(
        id=chunk["id"],
        doc_id=chunk["doc_id"],
        chunk_id=chunk["chunk_id"],
        text=chunk["text"],
        score=score,
        source=source,
        payload=chunk
    )


class TestTokenizer:
    """Test PT-BR tokenizer"""
    
    def test_basic_tokenization(self):
        text = "Python é uma linguagem de programação!"
        tokens = tokenize_ptbr(text)
        
        assert "python" in tokens
        assert "linguagem" in tokens
        assert "programação" in tokens or "programacao" in tokens
        # Stopwords should be removed
        assert "é" not in tokens and "e" not in tokens
        assert "uma" not in tokens
        assert "de" not in tokens
    
    def test_numbers_preserved(self):
        text = "O modelo GPT-4 tem 175 bilhões de parâmetros."
        tokens = tokenize_ptbr(text, remove_stopwords=False)
        
        assert any("175" in t for t in tokens)
        assert any("gpt" in t.lower() for t in tokens)
    
    def test_extract_sparse_query(self):
        query = "Como usar o RAG para busca de documentos?"
        sparse = extract_sparse_query(query)
        
        assert "rag" in sparse.lower()
        assert "busca" in sparse.lower()
        assert "documentos" in sparse.lower()
    
    def test_must_have_terms(self):
        query = "O que é o CPF 123.456.789-00?"
        terms = must_have_terms(query)
        
        # CPF number should be detected as must-have
        assert any("123" in t for t in terms)


class TestRRFFusion:
    """Test RRF fusion algorithm"""
    
    def test_basic_fusion(self):
        # Create dense hits
        dense_hits = [
            make_hit(SAMPLE_CHUNKS[0], 0.9, "dense"),
            make_hit(SAMPLE_CHUNKS[1], 0.8, "dense"),
            make_hit(SAMPLE_CHUNKS[2], 0.7, "dense"),
        ]
        
        # Create sparse hits (different order)
        sparse_hits = [
            make_hit(SAMPLE_CHUNKS[2], 5.0, "sparse"),  # Same as dense #3
            make_hit(SAMPLE_CHUNKS[4], 4.5, "sparse"),  # New
            make_hit(SAMPLE_CHUNKS[0], 4.0, "sparse"),  # Same as dense #1
        ]
        
        fused = rrf_fuse(dense_hits, sparse_hits, rrf_k=60, top_k_fused=10)
        
        # Should have results
        assert len(fused) > 0
        
        # Items appearing in both should have higher RRF score
        doc_ids = [h.doc_id for h in fused]
        assert "doc_1" in doc_ids  # Appeared in both
        assert "doc_2" in doc_ids  # Appeared in both
        assert "doc_3" in doc_ids  # Only in sparse
    
    def test_rrf_includes_sparse_only_items(self):
        """Items only in sparse should still appear in fused results"""
        dense_hits = [
            make_hit(SAMPLE_CHUNKS[0], 0.9, "dense"),
        ]
        
        sparse_hits = [
            make_hit(SAMPLE_CHUNKS[4], 5.0, "sparse"),  # Only in sparse
        ]
        
        fused = rrf_fuse(dense_hits, sparse_hits, rrf_k=60, top_k_fused=10)
        
        doc_ids = [h.doc_id for h in fused]
        assert "doc_1" in doc_ids  # From dense
        assert "doc_3" in doc_ids  # From sparse only
    
    def test_deduplication(self):
        """Same doc/chunk should not appear twice"""
        dense_hits = [
            make_hit(SAMPLE_CHUNKS[0], 0.9, "dense"),
        ]
        
        sparse_hits = [
            make_hit(SAMPLE_CHUNKS[0], 5.0, "sparse"),  # Same as dense
        ]
        
        fused = rrf_fuse(dense_hits, sparse_hits, rrf_k=60, top_k_fused=10, dedupe=True)
        
        # Should have only 1 result (deduplicated)
        assert len(fused) == 1
        assert fused[0].doc_id == "doc_1"
        assert fused[0].chunk_id == 0


class TestDiversity:
    """Test diversity constraints (max_per_doc)"""
    
    def test_max_per_doc_respected(self):
        from rag_retrieval.retriever import HybridRetriever
        
        # Create hits from same doc
        hits = [
            make_hit(SAMPLE_CHUNKS[0], 0.9, "reranked"),  # doc_1, chunk 0
            make_hit(SAMPLE_CHUNKS[1], 0.8, "reranked"),  # doc_1, chunk 1
            make_hit(SAMPLE_CHUNKS[2], 0.7, "reranked"),  # doc_2, chunk 0
        ]
        
        retriever = HybridRetriever()
        
        # Apply diversity with max_per_doc=1
        result = retriever._apply_diversity(
            hits=hits,
            max_per_doc=1,
            min_docs=1,
            max_chars_per_chunk=1600,
            query="test"
        )
        
        # Should have only 1 chunk per doc
        doc_ids = [c.doc_id for c in result]
        assert doc_ids.count("doc_1") <= 1
        assert doc_ids.count("doc_2") <= 1


class TestFilters:
    """Test filter application"""
    
    def test_filter_dataclass(self):
        filters = RetrievalFilters(
            tenant_id="tenant_1",
            tags=["python", "ml"],
            source_id="manual"
        )
        
        d = filters.to_dict()
        
        assert d["tenant_id"] == "tenant_1"
        assert d["tags"] == ["python", "ml"]
        assert d["source_id"] == "manual"
        assert "date_from" not in d  # None values should not be in dict
    
    def test_empty_filter(self):
        filters = RetrievalFilters()
        
        assert filters.is_empty() == True
        assert filters.to_dict() == {}


class TestDebugInfo:
    """Test debug info structure"""
    
    def test_debug_info_creation(self):
        debug = DebugInfo()
        
        debug.timings["dense_ms"] = 50.5
        debug.counts["dense_n"] = 60
        debug.params["topk"] = {"dense": 60}
        debug.add_note("Test note")
        
        d = debug.to_dict()
        
        assert d["timings"]["dense_ms"] == 50.5
        assert d["counts"]["dense_n"] == 60
        assert d["params"]["topk"]["dense"] == 60
        assert "Test note" in d["notes"]


# Integration test (requires Qdrant running)
@pytest.mark.skip(reason="Requires Qdrant server")
class TestIntegration:
    """Integration tests requiring Qdrant"""
    
    def test_full_pipeline(self):
        from rag_retrieval.retriever import retrieve_and_rerank
        
        chunks, debug = retrieve_and_rerank(
            query="Como usar Python para machine learning?",
            topk={"dense": 10, "sparse": 10, "fused": 15, "rerank": 5}
        )
        
        assert len(chunks) > 0
        assert debug.timings["total_ms"] > 0
        assert debug.counts["final_n"] > 0
