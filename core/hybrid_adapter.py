"""
Hybrid Retrieval Adapter for Chat Module
Bridges rag_retrieval pipeline with existing chat.py interface
"""
import os
from typing import Optional

# Flag to enable hybrid retrieval (off by default)
USE_HYBRID_RETRIEVAL = os.getenv("USE_HYBRID_RETRIEVAL", "false").lower() == "true"

# Global instances (lazy loaded)
_hybrid_retriever = None
_qdrant_store = None
_bm25_index = None


def is_hybrid_enabled() -> bool:
    """Check if hybrid retrieval is enabled"""
    return USE_HYBRID_RETRIEVAL


def get_hybrid_retriever():
    """Get or create HybridRetriever instance"""
    global _hybrid_retriever
    
    if _hybrid_retriever is None:
        try:
            from rag_retrieval.retriever import HybridRetriever
            _hybrid_retriever = HybridRetriever()
            print("✅ [HYBRID] HybridRetriever inicializado")
        except Exception as e:
            print(f"⚠️ [HYBRID] Falha ao inicializar: {e}")
            return None
    
    return _hybrid_retriever


def hybrid_search(
    query: str,
    k_docs: int = 5,
    k_memory: int = 5,
    filters: Optional[dict] = None,
) -> dict:
    """
    Perform hybrid search (dense + sparse + RRF + rerank)
    
    Returns dict compatible with existing build_chat_context:
    {
        "doc_snips": [...],
        "mem_snips": [...],
        "debug": DebugInfo
    }
    """
    retriever = get_hybrid_retriever()
    
    if retriever is None:
        return {"doc_snips": [], "mem_snips": [], "debug": None}
    
    try:
        from rag_retrieval.types import RetrievalFilters
        
        # Convert filters if provided
        rf = RetrievalFilters(**filters) if filters else None
        
        # Run hybrid retrieval
        chunks, debug = retriever.retrieve_and_rerank(
            query=query,
            filters=rf,
            topk={
                "dense": max(k_docs, k_memory) * 4,
                "sparse": max(k_docs, k_memory) * 4,
                "fused": max(k_docs, k_memory) * 6,
                "rerank": k_docs + k_memory
            },
            diversity={
                "max_per_doc": 3,
                "min_docs": 2
            }
        )
        
        # Split into doc and memory snips based on source_id
        doc_snips = []
        mem_snips = []
        
        for chunk in chunks:
            snip = {
                "text": chunk.text,
                "source": chunk.source_id,
                "score": chunk.score,
                "doc_id": chunk.doc_id,
                "chunk_id": chunk.chunk_id,
                "title": chunk.title,
                "why_picked": chunk.why_picked
            }
            
            # Classify: if source_id contains "memory" or role in payload, it's memory
            if "memory" in chunk.source_id.lower():
                mem_snips.append(snip)
            else:
                doc_snips.append(snip)
        
        # Limit results
        doc_snips = doc_snips[:k_docs]
        mem_snips = mem_snips[:k_memory]
        
        print(f"🔍 [HYBRID] Query: '{query[:50]}...' → {len(doc_snips)} docs, {len(mem_snips)} mem, {debug.timings['total_ms']:.0f}ms")
        
        return {
            "doc_snips": doc_snips,
            "mem_snips": mem_snips,
            "debug": debug
        }
        
    except Exception as e:
        print(f"❌ [HYBRID] Erro na busca: {e}")
        import traceback
        traceback.print_exc()
        return {"doc_snips": [], "mem_snips": [], "debug": None}


def format_hybrid_snips_for_context(doc_snips: list, mem_snips: list) -> tuple[str, str]:
    """
    Format hybrid search results for chat context
    
    Returns:
        (doc_text, mem_text) formatted strings
    """
    # Format documents
    if doc_snips:
        doc_parts = []
        for s in doc_snips:
            title = s.get("title", s.get("source", "Documento"))
            doc_parts.append(f"📄 {title}:\n{s['text']}\n(score={s['score']:.3f}, {s.get('why_picked', '')})")
        doc_text = "\n\n".join(doc_parts)
    else:
        doc_text = ""
    
    # Format memory
    if mem_snips:
        mem_parts = []
        for s in mem_snips:
            role = s.get("source", "unknown")
            role_display = "[USUÁRIO]" if role == "user" else "[ASSISTENTE]"
            mem_parts.append(f"{role_display}: {s['text']}")
        mem_text = "\n".join(mem_parts)
    else:
        mem_text = "(Memória vazia)"
    
    return doc_text, mem_text


def index_message_to_qdrant(role: str, content: str, user_id: str = "default"):
    """
    Index a chat message to Qdrant for hybrid retrieval
    Called after saving to SQLite for sync
    """
    if not is_hybrid_enabled():
        return
    
    try:
        from rag_retrieval.qdrant_store import QdrantStore
        from datetime import datetime
        
        global _qdrant_store
        if _qdrant_store is None:
            _qdrant_store = QdrantStore()
        
        chunk = {
            "id": f"memory_{user_id}_{datetime.now().isoformat()}",
            "doc_id": f"memory_{user_id}",
            "chunk_id": hash(content) % 10000,
            "text": content,
            "source_id": f"memory_{role}",
            "title": f"Chat {role}",
            "tags": ["memory", role],
            "tenant_id": user_id,
            "created_at": datetime.now().isoformat(),
        }
        
        _qdrant_store.upsert_chunks([chunk])
        
    except Exception as e:
        print(f"⚠️ [HYBRID] Erro ao indexar mensagem: {e}")

def get_available_documents() -> list[str]:
    """
    Get list of unique document titles indexed in Qdrant
    """
    if not is_hybrid_enabled():
        return []
        
    try:
        from rag_retrieval.qdrant_store import QdrantStore
        global _qdrant_store
        
        if _qdrant_store is None:
            _qdrant_store = QdrantStore()
            
        # Get all payloads (limit 500 to invoke less overhead)
        # Ideal: use specialized Qdrant scroll/grouping API
        payloads = _qdrant_store.get_all_payloads(limit=1000)
        
        doc_titles = set()
        for p in payloads:
            source = p.get('source_id', '')
            # Filter only documents (not memory)
            if 'memory' not in source.lower():
                title = p.get('title', p.get('source_id', ''))
                if title:
                    doc_titles.add(title)
                    
        return sorted(list(doc_titles))
        
    except Exception as e:
        print(f"⚠️ [HYBRID] Erro ao listar documentos: {e}")
        return []
